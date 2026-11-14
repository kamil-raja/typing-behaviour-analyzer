/* results-page.js — accessible metric-definition tooltips.
 *
 * Layer responsibility: presentation only. The page is server-rendered from
 * the persisted session record; this module never fetches or computes metrics.
 * CSS provides the hover and keyboard-focus states; this module wires click
 * toggling, Escape dismissal and outside-click dismissal.
 */

const helps = Array.from(document.querySelectorAll("[data-metric-help]"));

/**
 * Set the expanded state of one tooltip trigger.
 * @param {HTMLButtonElement} button
 * @param {boolean} expanded
 */
function setExpanded(button, expanded) {
  button.setAttribute("aria-expanded", expanded ? "true" : "false");
}

function closeAll() {
  helps.forEach((button) => setExpanded(button, false));
}

helps.forEach((button, index) => {
  const tooltip = button.parentElement
    ? button.parentElement.querySelector(".metric-tooltip")
    : null;
  if (!tooltip) {
    return;
  }

  const id = `metric-tooltip-${index + 1}`;
  tooltip.id = id;
  button.setAttribute("aria-controls", id);
  button.setAttribute("aria-describedby", id);
  // The custom tooltip replaces the native title once JavaScript is running.
  button.removeAttribute("title");

  button.addEventListener("click", () => {
    closeAll();
    setExpanded(button, true);
  });

  button.addEventListener("blur", () => setExpanded(button, false));

  button.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setExpanded(button, false);
      button.blur();
    }
  });
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".metric-help-wrap")) {
    closeAll();
  }
});
