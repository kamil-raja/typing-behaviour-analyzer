/* keyboard-heatmap.js — keyboard heatmap screen.
 *
 * Layer responsibility: presentation only. The per-key counts, error rates,
 * Wilson bounds and classifications come from GET /api/analytics/keys?scope=.
 * This module lays the tracked keys out on a US QWERTY board, formats the
 * stored values and pins one key in the inspector. It never recomputes a
 * statistic and never re-derives a classification.
 */

const root = document.querySelector("[data-keyboard-root]");

if (root) {
  const statusLine = root.querySelector("[data-keyboard-status]");
  const emptyState = root.querySelector("[data-keyboard-empty]");
  const content = root.querySelector("[data-keyboard-content]");
  const contextLine = root.querySelector("[data-keyboard-context]");
  const board = root.querySelector("[data-keyboard-board]");
  const scopeButtons = Array.from(root.querySelectorAll("[data-scope-option]"));
  const inspectorEmpty = root.querySelector("[data-keyboard-inspector-empty]");
  const inspectorBody = root.querySelector("[data-keyboard-inspector-body]");
  const inspectorLabel = root.querySelector("[data-keyboard-inspector-label]");
  const inspectorClass = root.querySelector("[data-keyboard-inspector-class]");
  const inspectorFacts = root.querySelector("[data-keyboard-inspector-facts]");
  const inspectorReason = root.querySelector("[data-keyboard-inspector-reason]");
  const weakList = root.querySelector("[data-keyboard-weak-list]");
  const weakEmpty = root.querySelector("[data-keyboard-weak-empty]");
  const needsList = root.querySelector("[data-keyboard-needs-list]");
  const needsEmpty = root.querySelector("[data-keyboard-needs-empty]");

  const DASH = "—";
  const BACKSPACE = "Backspace";
  const GLYPHS = { weak: "▲", average: "■", strong: "●" };
  const CLASS_TEXT = {
    weak: "Weak",
    average: "Average",
    strong: "Strong",
    insufficient: "Needs more data",
  };

  // ANSI 15-unit alphanumeric block. Widths are in key units (1 unit = 4 grid
  // columns). Modifier keys are drawn for recognition but are not tracked.
  const LAYOUT = [
    [
      ["Backquote", 1], ["Digit1", 1], ["Digit2", 1], ["Digit3", 1],
      ["Digit4", 1], ["Digit5", 1], ["Digit6", 1], ["Digit7", 1],
      ["Digit8", 1], ["Digit9", 1], ["Digit0", 1], ["Minus", 1],
      ["Equal", 1], ["Backspace", 2],
    ],
    [
      ["Tab", 1.5], ["KeyQ", 1], ["KeyW", 1], ["KeyE", 1], ["KeyR", 1],
      ["KeyT", 1], ["KeyY", 1], ["KeyU", 1], ["KeyI", 1], ["KeyO", 1],
      ["KeyP", 1], ["BracketLeft", 1], ["BracketRight", 1],
      ["Backslash", 1.5],
    ],
    [
      ["CapsLock", 1.75], ["KeyA", 1], ["KeyS", 1], ["KeyD", 1], ["KeyF", 1],
      ["KeyG", 1], ["KeyH", 1], ["KeyJ", 1], ["KeyK", 1], ["KeyL", 1],
      ["Semicolon", 1], ["Quote", 1], ["Enter", 2.25],
    ],
    [
      ["ShiftLeft", 2.25], ["KeyZ", 1], ["KeyX", 1], ["KeyC", 1], ["KeyV", 1],
      ["KeyB", 1], ["KeyN", 1], ["KeyM", 1], ["Comma", 1], ["Period", 1],
      ["Slash", 1], ["ShiftRight", 2.75],
    ],
    [
      ["ControlLeft", 1.25], ["MetaLeft", 1.25], ["AltLeft", 1.25],
      ["Space", 6.25], ["AltRight", 1.25], ["MetaRight", 1.25],
      ["ContextMenu", 1.25], ["ControlRight", 1.25],
    ],
  ];

  const UNTRACKED_LABELS = {
    Tab: "Tab",
    CapsLock: "Caps",
    Enter: "Enter",
    ShiftLeft: "Shift",
    ShiftRight: "Shift",
    ControlLeft: "Ctrl",
    ControlRight: "Ctrl",
    MetaLeft: "Meta",
    MetaRight: "Meta",
    AltLeft: "Alt",
    AltRight: "Alt",
    ContextMenu: "Menu",
  };

  let scope = root.dataset.scope;
  let keys = [];
  let minObservations = 20;
  let pinnedCode = null;
  let requestToken = 0;

  function formatPercent(ratio) {
    return ratio === null || ratio === undefined
      ? DASH
      : `${(Number(ratio) * 100).toFixed(1)}%`;
  }

  function formatMs(value) {
    return value === null || value === undefined
      ? DASH
      : `${Number(value).toFixed(1)} ms`;
  }

  function sampleText(count, mean) {
    return count ? `${count} samples · ${formatMs(mean)}` : DASH;
  }

  function classText(entry) {
    if (entry.code === BACKSPACE) {
      return "Not classified";
    }
    if (entry.attempts === 0) {
      return "No data";
    }
    return CLASS_TEXT[entry.class] || entry.class;
  }

  function keyTitle(entry) {
    if (entry.code === BACKSPACE) {
      return `Backspace: ${entry.backspace_presses} presses · dwell ${sampleText(entry.dwell_count, entry.mean_dwell_ms)}`;
    }
    return [
      `${entry.label}: ${classText(entry)}`,
      `${entry.attempts} attempts · ${entry.errors} mistakes · ${formatPercent(entry.error_rate)} errors`,
      `dwell ${sampleText(entry.dwell_count, entry.mean_dwell_ms)}`,
      `IKI ${sampleText(entry.iki_count, entry.mean_iki_ms)}`,
    ].join(" · ");
  }

  function setScope(nextScope) {
    scope = nextScope;
    for (const button of scopeButtons) {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.scopeOption === scope),
      );
    }
  }

  function buildKey(code, units, entry) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "key";
    button.dataset.code = code;
    button.style.gridColumn = `span ${Math.round(units * 4)}`;

    const label = document.createElement("span");
    label.className = "key__label";

    if (!entry) {
      button.classList.add("key--untracked");
      button.disabled = true;
      label.textContent = UNTRACKED_LABELS[code] || code;
      button.setAttribute("aria-label", `${label.textContent} (not tracked)`);
      button.append(label);
      return button;
    }

    label.textContent = entry.label;
    button.dataset.class = entry.class;
    button.setAttribute("aria-pressed", String(code === pinnedCode));
    button.title = keyTitle(entry);
    button.setAttribute("aria-label", keyTitle(entry));

    const detail = document.createElement("span");
    detail.className = "key__detail";

    if (code === BACKSPACE) {
      button.classList.add("key--special");
      detail.textContent = String(entry.backspace_presses);
    } else if (entry.attempts === 0) {
      button.classList.add("key--empty");
    } else if (entry.class === "insufficient") {
      button.classList.add("key--none");
      detail.textContent = `${entry.attempts}/${minObservations}`;
    } else {
      button.classList.add(`key--${entry.class}`);
      const glyph = document.createElement("span");
      glyph.className = "key__glyph";
      glyph.textContent = GLYPHS[entry.class] || "";
      glyph.setAttribute("aria-hidden", "true");
      button.append(glyph);
      detail.textContent = formatPercent(entry.error_rate);
    }

    if (code === pinnedCode) {
      button.classList.add("key--pinned");
    }

    button.append(label, detail);
    button.addEventListener("click", () => pin(code));
    return button;
  }

  function renderBoard() {
    const byCode = new Map(keys.map((entry) => [entry.code, entry]));
    const rows = LAYOUT.map((row) => {
      const rowElement = document.createElement("div");
      rowElement.className = "keyboard__row";
      for (const [code, units] of row) {
        rowElement.append(buildKey(code, units, byCode.get(code) || null));
      }
      return rowElement;
    });
    board.replaceChildren(...rows);
  }

  function fact(term, value) {
    const row = document.createElement("div");
    row.className = "keyboard__fact";
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.textContent = value;
    row.append(dt, dd);
    return row;
  }

  function renderInspector(entry) {
    if (!entry) {
      inspectorEmpty.hidden = false;
      inspectorBody.hidden = true;
      return;
    }

    inspectorEmpty.hidden = true;
    inspectorBody.hidden = false;
    inspectorLabel.textContent = entry.label;
    inspectorClass.textContent = classText(entry);

    const rows = [];
    if (entry.code === BACKSPACE) {
      rows.push(fact("Presses", String(entry.backspace_presses)));
      rows.push(fact("Dwell", sampleText(entry.dwell_count, entry.mean_dwell_ms)));
    } else {
      rows.push(fact("Observations", String(entry.attempts)));
      rows.push(fact("Mistakes", String(entry.errors)));
      rows.push(fact("Error rate", formatPercent(entry.error_rate)));
      rows.push(
        fact(
          "Wilson interval",
          entry.ci_low === null || entry.ci_high === null
            ? DASH
            : `${formatPercent(entry.ci_low)}–${formatPercent(entry.ci_high)}`,
        ),
      );
      rows.push(fact("Dwell", sampleText(entry.dwell_count, entry.mean_dwell_ms)));
      rows.push(fact("IKI", sampleText(entry.iki_count, entry.mean_iki_ms)));
      rows.push(fact("Sessions", String(entry.session_count)));
    }
    inspectorFacts.replaceChildren(...rows);
    inspectorReason.textContent = entry.reason;
  }

  function pin(code) {
    pinnedCode = code;
    for (const button of board.querySelectorAll(".key")) {
      const isPinned = button.dataset.code === code;
      button.classList.toggle("key--pinned", isPinned);
      if (button.dataset.class) {
        button.setAttribute("aria-pressed", String(isPinned));
      }
    }
    renderInspector(keys.find((entry) => entry.code === code) || null);
  }

  function renderList(list, empty, entries, describe) {
    list.replaceChildren(
      ...entries.map((entry) => {
        const item = document.createElement("li");
        item.className = "keyboard__list-item";
        item.textContent = describe(entry);
        return item;
      }),
    );
    empty.hidden = entries.length > 0;
  }

  function renderLists(hasObservations) {
    const weak = keys
      .filter((entry) => entry.class === "weak")
      .sort((a, b) => b.error_rate - a.error_rate)
      .slice(0, 5);
    renderList(
      weakList,
      weakEmpty,
      weak,
      (entry) =>
        `${entry.label} · ${formatPercent(entry.error_rate)} errors · ${entry.attempts} attempts`,
    );

    const needs = keys
      .filter(
        (entry) =>
          entry.code !== BACKSPACE &&
          entry.class === "insufficient" &&
          entry.attempts > 0,
      )
      .sort((a, b) => b.attempts - a.attempts)
      .slice(0, 8);
    needsEmpty.textContent = hasObservations
      ? "Every attempted key has enough observations to be classified."
      : "No key observations recorded yet.";
    renderList(
      needsList,
      needsEmpty,
      needs,
      (entry) =>
        `${entry.label} · ${entry.attempts} of ${minObservations} observations`,
    );
  }

  function renderContext(data) {
    const sessionWord = data.scoped_session_count === 1 ? "session" : "sessions";
    contextLine.textContent = [
      `${data.scoped_session_count} ${sessionWord} in scope`,
      `pooled baseline ${formatPercent(data.baseline_error_rate)}`,
      `${data.min_observations} observations needed per key`,
      `overall mean dwell ${formatMs(data.overall_mean_dwell_ms)}`,
    ].join(" · ");
  }

  function render(data) {
    keys = data.keys;
    minObservations = data.min_observations;

    const isEmpty = data.scoped_session_count === 0;
    emptyState.hidden = !isEmpty;
    content.hidden = isEmpty;
    statusLine.hidden = true;

    if (isEmpty) {
      pinnedCode = null;
      return;
    }

    const hasObservations = data.baseline_error_rate !== null;
    renderContext(data);
    renderBoard();
    renderLists(hasObservations);
    if (pinnedCode && keys.some((entry) => entry.code === pinnedCode)) {
      pin(pinnedCode);
    } else {
      pinnedCode = null;
      renderInspector(null);
    }
  }

  async function load() {
    const token = ++requestToken;
    statusLine.hidden = false;
    statusLine.textContent = "Loading key statistics…";

    try {
      const response = await fetch(
        `/api/analytics/keys?scope=${encodeURIComponent(scope)}`,
      );
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      if (token !== requestToken) {
        return;
      }
      render(data);
    } catch (error) {
      if (token !== requestToken) {
        return;
      }
      content.hidden = true;
      emptyState.hidden = true;
      statusLine.hidden = false;
      statusLine.textContent = "Could not load key statistics.";
    }
  }

  for (const button of scopeButtons) {
    button.addEventListener("click", () => {
      if (button.dataset.scopeOption === scope) {
        return;
      }
      setScope(button.dataset.scopeOption);
      load();
    });
  }

  setScope(scope);
  load();
}
