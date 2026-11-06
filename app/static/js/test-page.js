/* test-page.js — page controller for the typing test.
 *
 * Layer responsibility: own configuration state, fetch the chosen text from
 * the JSON API, wire the capture adapter to the typing engine, and manage
 * focus, restart and status messages. No metric math and no session
 * submission live here.
 */

import { createCapture } from "./capture.js";
import { createTypingEngine } from "./typing-engine.js";

const shell = document.querySelector("#test-shell");
const viewport = document.querySelector("#passage-viewport");
const track = document.querySelector("#passage-track");
const textEl = document.querySelector("#passage-text");
const caretEl = document.querySelector("#caret");
const timerEl = document.querySelector("#timer-value");
const timerLabelEl = document.querySelector("#timer-label");
const wpmEl = document.querySelector("#wpm-value");
const accuracyEl = document.querySelector("#accuracy-value");
const liveRow = document.querySelector("#live-row");
const statusEl = document.querySelector("#test-status");
const headerEl = document.querySelector(".site-header");
const siteMainEl = document.querySelector("#main");
const modeButtons = Array.from(document.querySelectorAll("[data-mode]"));
const durationButtons = Array.from(document.querySelectorAll("[data-duration]"));
const durationGroup = document.querySelector("#duration-group");
const passageGroup = document.querySelector("#passage-group");
const passageSelect = document.querySelector("#passage-select");

const wordCounts = JSON.parse(shell.dataset.wordCounts || "{}");
const SCHEMA_VERSION = 1;

const config = {
  mode: "time",
  durationMs: 30000,
  passageId: null,
};

let passages = [];
let passagesLoaded = false;
let currentTextRef = null;
let statusKind = "none";
let loadToken = 0;
let abortController = null;
let capture = null;
let submitted = false;
let submitting = false;

function setStatus(message, kind = "info") {
  statusEl.textContent = message;
  statusKind = message ? kind : "none";

  if (message) {
    statusEl.dataset.kind = kind;
  } else {
    delete statusEl.dataset.kind;
  }
}

function maybeShowFocusHint() {
  if (engine.getState() === "running") {
    return;
  }
  if (document.activeElement === viewport) {
    return;
  }
  if (statusKind !== "none") {
    return;
  }
  setStatus("Click the typing area or press Tab to focus.", "hint");
}

function focusViewport() {
  try {
    viewport.focus({ preventScroll: true });
  } catch (error) {
    viewport.focus();
  }
}

const engine = createTypingEngine({
  viewport,
  track,
  textEl,
  caretEl,
  timerEl,
  timerLabelEl,
  wpmEl,
  accuracyEl,
  liveRow,
  onStateChange(state) {
    headerEl.classList.toggle("is-running", state === "running");
    siteMainEl.classList.toggle("is-running", state === "running");

    if (state === "running") {
      setStatus("");
    }

    if (state === "finished" && capture !== null) {
      capture.stop();
    }
  },
  onMessage(message, kind) {
    if (!message) {
      setStatus("");
      maybeShowFocusHint();
      return;
    }
    setStatus(message, kind);
  },
  onFinish(result) {
    if (result.reason === "cancelled") {
      return;
    }
    console.debug("[TBA] provisional attempt finished", {
      reason: result.reason,
      elapsedMs: result.elapsedMs,
      pressed: result.pressed,
      correct: result.correct,
    });
    // Passage mode finishes from inside the completing keydown handler. Defer
    // submission to a microtask so capture.js can record that final accepted
    // event before submitAttempt() builds the payload; otherwise the server
    // replays an incomplete buffer and rejects the session.
    queueMicrotask(submitAttempt);
  },
});

function handleCaptureCancel(reason) {
  const cancelled = engine.cancel(reason);
  if (!cancelled) {
    return;
  }

  capture.stop();
  capture.reset();
  capture.attach();
  submitted = false;
  submitting = false;
  setStatus("Test cancelled. The window lost focus.", "warning");
}

capture = createCapture({
  viewport,
  isBufferFull: () => engine.isBufferFull(),
  onStart: (info) => engine.start(info),
  onPrintable: (event) => engine.handlePrintable(event),
  onBackspace: (event) => engine.handleBackspace(event),
  onKeyUp: (event) => engine.handleKeyUp(event),
  onCancel: (reason) => handleCaptureCancel(reason),
});

function clientPlatform() {
  const reported = navigator.userAgentData?.platform;
  if (typeof reported === "string" && reported) {
    return reported;
  }
  return navigator.platform || "unknown";
}

function buildSubmission() {
  return {
    schema_version: SCHEMA_VERSION,
    mode: config.mode,
    duration_limit_ms: config.mode === "time" ? config.durationMs : null,
    text_ref: currentTextRef,
    started_at: capture.getStartedAt() ?? new Date().toISOString(),
    client: {
      user_agent: navigator.userAgent || "unknown",
      platform: clientPlatform(),
      layout_hint: "unknown",
    },
    ignored: capture.getIgnored(),
    events: capture.getEvents(),
  };
}

async function submitAttempt() {
  if (submitted || submitting) {
    return;
  }
  if (!currentTextRef) {
    setStatus("The result could not be saved because no text reference is available.", "error");
    return;
  }

  submitted = true;
  submitting = true;
  setStatus("Saving result…", "info");

  try {
    const response = await fetch("/api/sessions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(buildSubmission()),
    });

    let body = null;
    try {
      body = await response.json();
    } catch (error) {
      body = null;
    }

    if (!response.ok) {
      const message = body?.error?.message
        || `Could not save the result (${response.status}).`;
      setStatus(message, "error");
      submitting = false;
      return;
    }

    const resultsUrl = body?.links?.results;
    if (typeof resultsUrl !== "string" || !resultsUrl) {
      setStatus("The result was saved but the results link was missing.", "error");
      submitting = false;
      return;
    }

    window.location.assign(resultsUrl);
  } catch (error) {
    setStatus("Could not save the result. Check the server and try again.", "error");
    submitting = false;
  }
}

async function fetchJson(url, signal) {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      if (body?.error?.message) {
        message = body.error.message;
      }
    } catch (error) {
      // Keep the status-based message when the body is not JSON.
    }
    throw new Error(message);
  }

  return response.json();
}

function populatePassageSelect() {
  passageSelect.replaceChildren();
  for (const passage of passages) {
    const option = document.createElement("option");
    option.value = passage.text_ref.id;
    option.textContent = passage.label;
    passageSelect.appendChild(option);
  }

  if (passages.length === 0) {
    throw new Error("No passages are available.");
  }

  const selectedExists = passages.some(
    (passage) => passage.text_ref.id === config.passageId,
  );
  if (!config.passageId || !selectedExists) {
    config.passageId = passages[0].text_ref.id;
  }
  passageSelect.value = config.passageId;
  passageSelect.disabled = false;
}

async function ensurePassages(signal) {
  if (passagesLoaded) {
    return;
  }

  const data = await fetchJson("/api/texts/passages", signal);
  passages = Array.isArray(data.passages) ? data.passages : [];
  populatePassageSelect();
  passagesLoaded = true;
}

function updateConfigUi() {
  for (const button of modeButtons) {
    const active = button.dataset.mode === config.mode;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  }

  for (const button of durationButtons) {
    const active = Number(button.dataset.duration) * 1000 === config.durationMs;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  }

  durationGroup.hidden = config.mode !== "time";
  passageGroup.hidden = config.mode !== "passage";
}

async function loadCurrentText({ focus = true } = {}) {
  const token = loadToken + 1;
  loadToken = token;

  if (abortController !== null) {
    abortController.abort();
  }
  abortController = new AbortController();
  const { signal } = abortController;

  capture.stop();
  capture.reset();
  engine.loadText("", {
    mode: config.mode,
    durationLimitMs: config.mode === "time" ? config.durationMs : null,
  });
  currentTextRef = null;
  submitted = false;
  submitting = false;
  viewport.setAttribute("aria-busy", "true");
  setStatus("Loading text…", "info");

  try {
    let data;

    if (config.mode === "time") {
      const count = wordCounts[String(config.durationMs)];
      if (!Number.isInteger(count)) {
        throw new Error("No word count is configured for this duration.");
      }
      data = await fetchJson(`/api/texts/words?count=${count}`, signal);
    } else {
      await ensurePassages(signal);
      if (!config.passageId) {
        throw new Error("No passage is selected.");
      }
      data = await fetchJson(
        `/api/texts/passages/${encodeURIComponent(config.passageId)}`,
        signal,
      );
      passageSelect.value = config.passageId;
    }

    if (token !== loadToken) {
      return;
    }

    currentTextRef = data.text_ref;
    engine.loadText(data.text, {
      mode: config.mode,
      durationLimitMs: config.mode === "time" ? config.durationMs : null,
    });
    capture.reset();
    capture.attach();
    setStatus("");
    if (focus) {
      focusViewport();
      if (document.activeElement !== viewport) {
        maybeShowFocusHint();
      }
    } else {
      maybeShowFocusHint();
    }
  } catch (error) {
    if (error.name === "AbortError" || token !== loadToken) {
      return;
    }
    setStatus("Could not load text. Check the server and try again.", "error");
  } finally {
    if (token === loadToken) {
      viewport.removeAttribute("aria-busy");
    }
  }
}

function restart() {
  if (submitting) {
    return;
  }
  if (!engine.getText()) {
    loadCurrentText();
    return;
  }

  if (engine.getState() === "running") {
    engine.cancel("escape");
  } else {
    engine.resetAttempt();
  }

  capture.stop();
  capture.reset();
  capture.attach();
  submitted = false;
  setStatus("");
  focusViewport();
}

for (const button of modeButtons) {
  button.addEventListener("click", () => {
    const nextMode = button.dataset.mode;
    if (nextMode === config.mode) {
      return;
    }
    config.mode = nextMode;
    updateConfigUi();
    loadCurrentText();
  });
}

for (const button of durationButtons) {
  button.addEventListener("click", () => {
    if (config.mode !== "time") {
      return;
    }
    const nextDuration = Number(button.dataset.duration) * 1000;
    if (nextDuration === config.durationMs) {
      return;
    }
    config.durationMs = nextDuration;
    updateConfigUi();
    loadCurrentText();
  });
}

passageSelect.addEventListener("change", () => {
  config.passageId = passageSelect.value;
  loadCurrentText();
});

viewport.addEventListener("focus", () => {
  if (statusKind === "hint") {
    setStatus("");
  }
});

viewport.addEventListener("blur", () => {
  maybeShowFocusHint();
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || event.isComposing) {
    return;
  }
  restart();
});

updateConfigUi();
loadCurrentText();
