/* theme.js — light/dark theme toggle and preference persistence.
 *
 * Layer responsibility: UI chrome only. The initial theme is applied by the
 * inline blocking script in base.html; this module handles later toggles and
 * notifies listeners (for example charts) through tba:themechange.
 */

const STORAGE_KEY = "tba-theme";
const root = document.documentElement;
const toggle = document.querySelector("[data-theme-toggle]");

/**
 * Read the theme currently applied to the document.
 * @returns {"light" | "dark"}
 */
function currentTheme() {
  return root.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

/**
 * Update the toggle's accessible action label for the active theme.
 * @param {"light" | "dark"} theme
 */
function updateToggleLabel(theme) {
  if (!toggle) {
    return;
  }
  const target = theme === "dark" ? "light" : "dark";
  toggle.setAttribute("aria-label", `Switch to ${target} theme`);
  toggle.setAttribute("title", `Switch to ${target} theme`);
}

/**
 * Apply a theme, persist it when storage is available, and broadcast the change.
 * @param {"light" | "dark"} theme
 */
function applyTheme(theme) {
  const next = theme === "dark" ? "dark" : "light";
  root.setAttribute("data-theme", next);

  try {
    window.localStorage.setItem(STORAGE_KEY, next);
  } catch (error) {
    /* Storage may be unavailable (private mode or policy); the theme still applies. */
  }

  updateToggleLabel(next);
  window.dispatchEvent(new CustomEvent("tba:themechange", {
    detail: { theme: next },
  }));
}

if (toggle) {
  updateToggleLabel(currentTheme());
  toggle.addEventListener("click", () => {
    applyTheme(currentTheme() === "dark" ? "light" : "dark");
  });
}

export { applyTheme, currentTheme };
