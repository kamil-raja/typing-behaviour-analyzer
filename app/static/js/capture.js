/* capture.js — keyboard event capture for the typing test.
 *
 * Layer responsibility: translate browser keyboard events into the event
 * objects documented in docs/EVENT_SCHEMA.md. It owns the pending-keydown
 * map, repeat handling, timestamps and ignored counters. It contains no
 * rendering and no metric calculations.
 */

const PRINTABLE_ASCII = /^[\x20-\x7E]$/;
const MODIFIER_KEYS = new Set([
  "Shift",
  "Control",
  "Alt",
  "Meta",
  "CapsLock",
  "AltGraph",
]);

/**
 * @returns {{
 *   repeat_keydowns: number,
 *   shortcuts: number,
 *   unsupported_keys: number,
 *   unsupported_chars: number,
 *   paste_attempts: number,
 * }}
 */
function emptyIgnored() {
  return {
    repeat_keydowns: 0,
    shortcuts: 0,
    unsupported_keys: 0,
    unsupported_chars: 0,
    paste_attempts: 0,
  };
}

/**
 * Create the keyboard capture adapter for a passage viewport.
 *
 * Callbacks:
 * - onStart({ startedAt, firstTimestamp })
 * - onPrintable({ type: "down", t, code, key, repeat })
 * - onBackspace({ type: "down", t, code, key, repeat })
 * - onKeyUp({ type: "up", t, code, key, repeat })
 * - onCancel("focus" | "window")
 *
 * @param {{
 *   viewport: HTMLElement,
 *   isBufferFull: () => boolean,
 *   onStart: (info: { startedAt: string, firstTimestamp: number }) => void,
 *   onPrintable: (event: object) => boolean,
 *   onBackspace: (event: object) => boolean,
 *   onKeyUp: (event: object) => void,
 *   onCancel: (reason: "focus" | "window") => void,
 * }} options
 */
export function createCapture({
  viewport,
  isBufferFull,
  onStart,
  onPrintable,
  onBackspace,
  onKeyUp,
  onCancel,
}) {
  let attached = false;
  let active = false;
  let pending = new Map();
  let firstTimestamp = null;
  let startedAt = null;
  let clockChecked = false;
  let fallbackCount = 0;
  let ignored = emptyIgnored();
  let missingUpCount = 0;
  let orphanUpCount = 0;

  function timestampOf(event) {
    if (Number.isFinite(event.timeStamp)) {
      if (!clockChecked) {
        clockChecked = true;
        const delta = event.timeStamp - performance.now();
        console.debug(
          "[TBA] event.timeStamp - performance.now() =",
          Math.round(delta * 10) / 10,
          "ms",
        );
      }
      return event.timeStamp;
    }

    fallbackCount += 1;
    console.warn(
      "[TBA] event.timeStamp was not finite; falling back to performance.now().",
      { fallbackCount },
    );
    return performance.now();
  }

  function relativeT(timestamp) {
    if (firstTimestamp === null) {
      return 0;
    }
    const delta = timestamp - firstTimestamp;
    return Math.round(Math.max(0, delta) * 10) / 10;
  }

  function isAltGraph(event) {
    return typeof event.getModifierState === "function"
      && event.getModifierState("AltGraph");
  }

  function isShortcut(event) {
    return (event.ctrlKey || event.metaKey || event.altKey)
      && !isAltGraph(event);
  }

  function countUnsupported(event) {
    const key = event.key;
    if (typeof key !== "string" || key.length === 0) {
      ignored.unsupported_keys += 1;
      return;
    }

    const firstCodePoint = key.codePointAt(0);
    const isSingleCharacter = Array.from(key).length === 1;
    if (
      (key.length === 1 && !PRINTABLE_ASCII.test(key))
      || (isSingleCharacter && firstCodePoint !== undefined && firstCodePoint > 0x7e)
    ) {
      ignored.unsupported_chars += 1;
      return;
    }
    ignored.unsupported_keys += 1;
  }

  function start(timestamp) {
    firstTimestamp = timestamp;
    startedAt = new Date().toISOString();
    active = true;
    onStart({ startedAt, firstTimestamp });
  }

  function handlePrintable(event, timestamp) {
    if (event.repeat) {
      if (active) {
        event.preventDefault();
        ignored.repeat_keydowns += 1;
      }
      return;
    }

    if (active && isBufferFull()) {
      event.preventDefault();
      return;
    }

    if (!active) {
      start(timestamp);
    }

    const eventObject = {
      type: "down",
      t: relativeT(timestamp),
      code: event.code,
      key: event.key,
      repeat: false,
    };
    const accepted = onPrintable(eventObject);
    event.preventDefault();

    if (accepted && active) {
      if (pending.has(event.code)) {
        missingUpCount += 1;
      }
      pending.set(event.code, timestamp);
    }
  }

  function handleBackspace(event, timestamp) {
    if (!active) {
      return;
    }

    if (event.repeat) {
      if (pending.has(event.code)) {
        event.preventDefault();
        onBackspace({
          type: "down",
          t: relativeT(timestamp),
          code: event.code,
          key: "Backspace",
          repeat: true,
        });
      }
      return;
    }

    event.preventDefault();
    if (pending.has(event.code)) {
      missingUpCount += 1;
    }
    pending.set(event.code, timestamp);
    onBackspace({
      type: "down",
      t: relativeT(timestamp),
      code: event.code,
      key: "Backspace",
      repeat: false,
    });
  }

  function handleKeyDown(event) {
    if (event.target !== viewport) {
      return;
    }

    const key = event.key;

    // Navigation is never intercepted; focus leaving cancels a running test.
    if (key === "Tab") {
      return;
    }

    // Esc restart is owned by the page controller, not the capture layer.
    if (key === "Escape") {
      return;
    }

    if (isShortcut(event)) {
      if (active) {
        ignored.shortcuts += 1;
      }
      return;
    }

    if (MODIFIER_KEYS.has(key)) {
      return;
    }

    const timestamp = timestampOf(event);

    if (key === "Backspace") {
      handleBackspace(event, timestamp);
      return;
    }

    if (event.isComposing) {
      if (active) {
        event.preventDefault();
      }
      ignored.unsupported_chars += 1;
      return;
    }

    if (PRINTABLE_ASCII.test(key)) {
      handlePrintable(event, timestamp);
      return;
    }

    if (active) {
      event.preventDefault();
      countUnsupported(event);
    }
  }

  function handleKeyUp(event) {
    if (event.target !== viewport) {
      return;
    }

    const downTimestamp = pending.get(event.code);
    if (downTimestamp === undefined) {
      orphanUpCount += 1;
      return;
    }

    pending.delete(event.code);
    const timestamp = timestampOf(event);
    onKeyUp({
      type: "up",
      t: relativeT(timestamp),
      code: event.code,
      key: null,
      repeat: false,
    });
  }

  function handlePaste(event) {
    event.preventDefault();
    ignored.paste_attempts += 1;
  }

  function handleViewportBlur() {
    if (!active) {
      return;
    }
    onCancel(document.hasFocus() ? "focus" : "window");
  }

  function handleWindowBlur() {
    if (active) {
      onCancel("window");
    }
  }

  function handleVisibilityChange() {
    if (active && document.visibilityState === "hidden") {
      onCancel("window");
    }
  }

  function attach() {
    if (attached) {
      return;
    }
    attached = true;
    viewport.addEventListener("keydown", handleKeyDown);
    viewport.addEventListener("keyup", handleKeyUp);
    viewport.addEventListener("paste", handlePaste);
    viewport.addEventListener("blur", handleViewportBlur);
    window.addEventListener("blur", handleWindowBlur);
    document.addEventListener("visibilitychange", handleVisibilityChange);
  }

  function stop() {
    active = false;
    detach();
  }

  function detach() {
    if (!attached) {
      return;
    }
    attached = false;
    viewport.removeEventListener("keydown", handleKeyDown);
    viewport.removeEventListener("keyup", handleKeyUp);
    viewport.removeEventListener("paste", handlePaste);
    viewport.removeEventListener("blur", handleViewportBlur);
    window.removeEventListener("blur", handleWindowBlur);
    document.removeEventListener("visibilitychange", handleVisibilityChange);
  }

  function reset() {
    pending = new Map();
    firstTimestamp = null;
    startedAt = null;
    active = false;
    fallbackCount = 0;
    ignored = emptyIgnored();
    missingUpCount = 0;
    orphanUpCount = 0;
  }

  return {
    attach,
    detach,
    stop,
    reset,
    isActive: () => active,
    getFirstTimestamp: () => firstTimestamp,
    getStartedAt: () => startedAt,
    getIgnored: () => ({ ...ignored }),
    getFallbackCount: () => fallbackCount,
    getDiagnostics: () => ({
      missingUp: missingUpCount,
      orphanUp: orphanUpCount,
      fallbackCount,
    }),
  };
}
