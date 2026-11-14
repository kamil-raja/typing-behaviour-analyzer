/* typing-engine.js — client-side test state, rendering and provisional stats.
 *
 * Layer responsibility: own the idle → running → finished/cancelled attempt
 * state, render the reference text with character states and a caret, and show
 * clearly-labelled provisional live numbers. It never computes final metrics;
 * every stored statistic is produced server-side (AGENTS.md §3).
 *
 * Rules implemented from docs/EVENT_SCHEMA.md §2–§5:
 * - time-mode events with t >= duration_limit_ms are not recorded;
 * - completion requires the buffer to equal the text exactly;
 * - a full buffer with mistakes blocks printable keys and shows the fix message;
 * - Backspace removes one character but never changes accepted-keystroke counts.
 */

export const IDLE = "idle";
export const RUNNING = "running";
export const FINISHED = "finished";

const LIVE_TICK_MS = 100;
const LIVE_MIN_ELAPSED_MS = 1000;
const FIX_MESSAGE = "Fix the highlighted characters to finish";

/**
 * @param {{
 *   viewport: HTMLElement,
 *   track: HTMLElement,
 *   textEl: HTMLElement,
 *   caretEl: HTMLElement,
 *   timerEl: HTMLElement,
 *   timerLabelEl: HTMLElement,
 *   wpmEl: HTMLElement,
 *   accuracyEl: HTMLElement,
 *   liveRow: HTMLElement,
 *   onStateChange?: (state: string) => void,
 *   onMessage?: (message: string, kind: string) => void,
 *   onFinish?: (result: object) => void,
 * }} options
 */
export function createTypingEngine({
  viewport,
  track,
  textEl,
  caretEl,
  timerEl,
  timerLabelEl,
  wpmEl,
  accuracyEl,
  liveRow,
  onStateChange = () => {},
  onMessage = () => {},
  onFinish = () => {},
}) {
  let state = IDLE;
  let text = "";
  let buffer = "";
  let spans = [];
  let config = { mode: "time", durationLimitMs: 30000 };
  let startTimestamp = null;
  let startedAt = null;
  let elapsedMs = 0;
  let tickTimer = null;
  let pressedCount = 0;
  let correctCount = 0;
  let incorrectCount = 0;
  let messageText = "";
  let messageKind = "";
  let lineHeight = 0;

  function setMessage(nextText, kind = "info") {
    if (nextText === messageText && kind === messageKind) {
      return;
    }
    messageText = nextText;
    messageKind = nextText ? kind : "";
    onMessage(messageText, messageKind);
  }

  function setState(nextState) {
    state = nextState;
    viewport.dataset.state = nextState;
    onStateChange(nextState);
  }

  function measureLineHeight() {
    const computed = getComputedStyle(textEl);
    const parsed = Number.parseFloat(computed.lineHeight);
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
    const fontSize = Number.parseFloat(computed.fontSize);
    return Number.isFinite(fontSize) ? fontSize * 1.75 : 40;
  }

  function clearSpans() {
    for (const span of spans) {
      span.classList.remove("is-correct", "is-incorrect");
    }
  }

  function renderText() {
    const fragment = document.createDocumentFragment();
    spans = [];

    for (const character of text) {
      const span = document.createElement("span");
      span.className = "char";
      span.textContent = character;
      fragment.appendChild(span);
    }

    textEl.replaceChildren(fragment);
    spans = Array.from(textEl.children);
    lineHeight = measureLineHeight();
    updateCaret();
  }

  function updateCaret() {
    if (spans.length === 0) {
      caretEl.hidden = true;
      return;
    }

    caretEl.hidden = false;
    const caretIndex = buffer.length;
    let left;
    let top;

    if (caretIndex < spans.length) {
      const span = spans[caretIndex];
      left = span.offsetLeft;
      top = span.offsetTop;
    } else {
      const span = spans[spans.length - 1];
      left = span.offsetLeft + span.offsetWidth;
      top = span.offsetTop;
    }

    const safeLineHeight = lineHeight || measureLineHeight();
    // Inline spans report the top of their content box, which sits inside the
    // taller line box. Anchor the caret to the line box itself so it matches
    // the row of text exactly and does not overhang the following line.
    const lineIndex = Math.max(
      0,
      Math.round((top - spans[0].offsetTop) / safeLineHeight),
    );
    const lineTop = lineIndex * safeLineHeight;

    caretEl.style.transform = `translate(${left}px, ${lineTop}px)`;
    caretEl.style.height = `${safeLineHeight}px`;

    const shift = Math.max(0, lineIndex - 1) * safeLineHeight;
    track.style.transform = `translateY(-${shift}px)`;
  }

  function currentElapsedMs() {
    if (state === FINISHED) {
      return elapsedMs;
    }
    if (state !== RUNNING || startTimestamp === null) {
      return 0;
    }

    let elapsed = performance.now() - startTimestamp;
    if (config.mode === "time") {
      elapsed = Math.min(elapsed, config.durationLimitMs);
    }
    return Math.max(0, elapsed);
  }

  function formatTimer(elapsed) {
    if (config.mode === "time") {
      const remaining = Math.max(0, config.durationLimitMs - elapsed);
      return `${Math.ceil(remaining / 1000)}s`;
    }
    return `${(elapsed / 1000).toFixed(1)}s`;
  }

  function updateStats() {
    const elapsed = currentElapsedMs();
    const minutes = Math.max(elapsed, LIVE_MIN_ELAPSED_MS) / 60000;
    let correctChars = 0;

    for (let index = 0; index < buffer.length; index += 1) {
      if (buffer[index] === text[index]) {
        correctChars += 1;
      }
    }

    const netWpm = Math.max(0, correctChars / 5 / minutes);
    const accuracy = pressedCount > 0
      ? (correctCount / pressedCount) * 100
      : 100;

    timerEl.textContent = formatTimer(elapsed);
    wpmEl.textContent = String(Math.round(netWpm));
    accuracyEl.textContent = `${Number(accuracy.toFixed(1))}%`;
  }

  function stopTick() {
    if (tickTimer !== null) {
      window.clearInterval(tickTimer);
      tickTimer = null;
    }
  }

  function tick() {
    if (state !== RUNNING) {
      return;
    }

    const elapsed = currentElapsedMs();
    if (config.mode === "time" && elapsed >= config.durationLimitMs) {
      finish("time_up", config.durationLimitMs);
      return;
    }

    updateStats();
  }

  function finish(reason, endedAtMs = null) {
    if (state !== RUNNING) {
      return;
    }

    stopTick();
    elapsedMs = Math.max(
      0,
      endedAtMs === null ? currentElapsedMs() : endedAtMs,
    );
    setState(FINISHED);
    updateStats();

    if (reason === "completed") {
      setMessage("Test finished. Press Escape to restart.", "finished");
    } else {
      setMessage("Time's up. Press Escape to restart.", "finished");
    }

    onFinish({
      reason,
      startedAt,
      elapsedMs,
      pressed: pressedCount,
      correct: correctCount,
      incorrect: incorrectCount,
      buffer,
      text,
      textLength: text.length,
    });
  }

  function loadText(nextText, nextConfig) {
    stopTick();
    text = nextText;
    buffer = "";
    pressedCount = 0;
    correctCount = 0;
    incorrectCount = 0;
    startTimestamp = null;
    startedAt = null;
    elapsedMs = 0;
    config = {
      mode: nextConfig.mode,
      durationLimitMs: nextConfig.durationLimitMs ?? null,
    };

    liveRow.hidden = true;
    timerLabelEl.textContent = config.mode === "time" ? "time left" : "elapsed";
    timerEl.textContent = formatTimer(0);
    wpmEl.textContent = "0";
    accuracyEl.textContent = "100%";
    track.style.transform = "translateY(0)";

    setState(IDLE);
    renderText();
    updateStats();
    setMessage("", "");
  }

  function start(info) {
    stopTick();
    startTimestamp = info.firstTimestamp;
    startedAt = info.startedAt;
    elapsedMs = 0;
    liveRow.hidden = false;
    setState(RUNNING);
    setMessage("", "");
    updateStats();
    tickTimer = window.setInterval(tick, LIVE_TICK_MS);
  }

  function handlePrintable(event) {
    if (state !== RUNNING) {
      return false;
    }

    if (
      config.mode === "time"
      && config.durationLimitMs !== null
      && event.t >= config.durationLimitMs
    ) {
      finish("time_up", config.durationLimitMs);
      return false;
    }

    if (buffer.length >= text.length) {
      setMessage(FIX_MESSAGE, "fix");
      return false;
    }

    const index = buffer.length;
    const correct = event.key === text[index];
    buffer += event.key;
    pressedCount += 1;
    if (correct) {
      correctCount += 1;
    } else {
      incorrectCount += 1;
    }

    const span = spans[index];
    if (span) {
      span.classList.add(correct ? "is-correct" : "is-incorrect");
    }

    updateCaret();
    updateStats();

    if (buffer.length === text.length) {
      if (buffer === text) {
        finish("completed", currentElapsedMs());
      } else {
        setMessage(FIX_MESSAGE, "fix");
      }
    }

    return true;
  }

  function handleBackspace(event) {
    if (state !== RUNNING) {
      return false;
    }

    if (
      config.mode === "time"
      && config.durationLimitMs !== null
      && event.t >= config.durationLimitMs
    ) {
      finish("time_up", config.durationLimitMs);
      return false;
    }

    if (buffer.length === 0) {
      return true;
    }

    const index = buffer.length - 1;
    buffer = buffer.slice(0, -1);
    const span = spans[index];
    if (span) {
      span.classList.remove("is-correct", "is-incorrect");
    }

    if (messageText === FIX_MESSAGE) {
      setMessage("", "");
    }

    updateCaret();
    updateStats();
    return true;
  }

  function handleKeyUp() {
    // Keyup pairing is owned by capture.js; the client stores no final events
    // until the submission milestone.
  }

  function resetAttempt() {
    stopTick();
    buffer = "";
    pressedCount = 0;
    correctCount = 0;
    incorrectCount = 0;
    startTimestamp = null;
    startedAt = null;
    elapsedMs = 0;
    clearSpans();
    track.style.transform = "translateY(0)";
    liveRow.hidden = true;
    setState(IDLE);
    updateCaret();
    updateStats();
    setMessage("", "");
  }

  function cancel(reason) {
    if (state !== RUNNING) {
      return false;
    }
    resetAttempt();
    onFinish({ reason: "cancelled", cancelReason: reason, elapsedMs: 0 });
    return true;
  }

  return {
    loadText,
    start,
    handlePrintable,
    handleBackspace,
    handleKeyUp,
    resetAttempt,
    cancel,
    isBufferFull: () => text.length > 0 && buffer.length >= text.length,
    getState: () => state,
    getText: () => text,
    getBufferLength: () => buffer.length,
    getConfig: () => ({ ...config }),
  };
}
