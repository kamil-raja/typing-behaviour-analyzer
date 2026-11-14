/* analytics-page.js — progress charts screen.
 *
 * Layer responsibility: presentation only. The stored WPM/accuracy series and
 * the moving averages come from GET /api/analytics/progress?scope=; this module
 * formats labels, switches the scope, and hands the values to charts.js. It
 * never computes a metric or a moving average.
 */

import { applyChartTheme, createProgressChart } from "./charts.js";

const root = document.querySelector("[data-analytics-root]");

if (root) {
  const chartsHost = root.querySelector("[data-analytics-charts]");
  const statusLine = root.querySelector("[data-analytics-status]");
  const emptyState = root.querySelector("[data-analytics-empty]");
  const scopeButtons = Array.from(root.querySelectorAll("[data-scope-option]"));
  const wpmCanvas = root.querySelector('[data-chart="wpm"]');
  const accuracyCanvas = root.querySelector('[data-chart="accuracy"]');

  let scope = root.dataset.scope;
  let charts = [];
  let requestToken = 0;

  function destroyCharts() {
    for (const chart of charts) {
      chart.destroy();
    }
    charts = [];
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

  function formatLabel(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function valuesOf(sessions, field) {
    return sessions.map((session) => {
      const value = session[field];
      return value === null || value === undefined ? null : Number(value);
    });
  }

  function render(sessions, windowSize) {
    destroyCharts();

    const isEmpty = sessions.length === 0;
    emptyState.hidden = !isEmpty;
    chartsHost.hidden = isEmpty;
    statusLine.hidden = true;

    if (isEmpty) {
      return;
    }

    const averageLabel = windowSize
      ? `${windowSize}-session moving average`
      : "Moving average";

    charts = [
      createProgressChart(wpmCanvas, {
        labels: sessions.map((session) => formatLabel(session.created_at)),
        label: "Net WPM",
        averageLabel,
        values: valuesOf(sessions, "net_wpm"),
        average: valuesOf(sessions, "moving_average_net_wpm"),
        unit: "",
        minimum: 0,
      }),
      createProgressChart(accuracyCanvas, {
        labels: sessions.map((session) => formatLabel(session.created_at)),
        label: "Accuracy",
        averageLabel,
        values: valuesOf(sessions, "accuracy_pct"),
        average: valuesOf(sessions, "moving_average_accuracy_pct"),
        unit: "%",
        minimum: 0,
        maximum: 100,
      }),
    ];
  }

  async function load() {
    const token = ++requestToken;
    statusLine.hidden = false;
    statusLine.textContent = "Loading progress…";

    try {
      const response = await fetch(
        `/api/analytics/progress?scope=${encodeURIComponent(scope)}`,
      );
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      if (token !== requestToken) {
        return;
      }
      render(data.sessions, data.window);
    } catch (error) {
      if (token !== requestToken) {
        return;
      }
      destroyCharts();
      chartsHost.hidden = true;
      emptyState.hidden = true;
      statusLine.hidden = false;
      statusLine.textContent = "Could not load progress data.";
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

  window.addEventListener("tba:themechange", () => {
    for (const chart of charts) {
      applyChartTheme(chart);
    }
  });

  setScope(scope);
  load();
}
