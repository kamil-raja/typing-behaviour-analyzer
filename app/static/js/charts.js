/* charts.js — Chart.js wrappers and theme helpers.
 *
 * Layer responsibility: draw stored analytics values. The moving average and
 * every other metric arrive from the API; this module only maps them onto
 * Chart.js datasets and keeps the chart colours in step with the active theme.
 *
 * Chart.js is vendored locally (static/vendor/chart.umd.min.js) and exposes the
 * global `Chart` constructor.
 */

const ChartConstructor = window.Chart;

/** Read one design token from the document root. */
function token(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Snapshot the theme-dependent colours and fonts used by the charts. */
function palette() {
  return {
    accent: token("--accent"),
    text: token("--text"),
    muted: token("--text-muted"),
    border: token("--border"),
    surface: token("--surface"),
    mono: token("--font-mono"),
  };
}

function styleDatasets(chart, colors) {
  for (const dataset of chart.data.datasets) {
    if (dataset.tbaRole === "average") {
      dataset.borderColor = colors.muted;
      dataset.pointBackgroundColor = colors.muted;
    } else {
      dataset.borderColor = colors.accent;
      dataset.pointBackgroundColor = colors.accent;
      dataset.pointBorderColor = colors.surface;
    }
  }
}

function styleAxes(chart, colors) {
  for (const scale of Object.values(chart.options.scales || {})) {
    scale.ticks.color = colors.muted;
    scale.ticks.font = { family: colors.mono };
    scale.grid.color = colors.border;
    if (scale.title) {
      scale.title.color = colors.muted;
    }
  }

  const plugins = chart.options.plugins || {};
  if (plugins.legend && plugins.legend.labels) {
    plugins.legend.labels.color = colors.muted;
    plugins.legend.labels.font = { family: colors.mono };
  }
  if (plugins.tooltip) {
    plugins.tooltip.backgroundColor = colors.surface;
    plugins.tooltip.titleColor = colors.text;
    plugins.tooltip.bodyColor = colors.text;
    plugins.tooltip.borderColor = colors.border;
  }
}

/**
 * Re-read the current theme tokens and recolour one chart without animation.
 * Called on `tba:themechange` so a theme switch never reloads the page.
 * @param {import("chart.js").Chart} chart
 */
export function applyChartTheme(chart) {
  const colors = palette();
  styleDatasets(chart, colors);
  styleAxes(chart, colors);
  chart.update("none");
}

/**
 * Build one progress line chart: the stored series plus its server-computed
 * moving average. Null values stay as gaps; they are never drawn as zero.
 * @param {HTMLCanvasElement} canvas
 * @param {{
 *   labels: string[],
 *   label: string,
 *   averageLabel: string,
 *   values: (number | null)[],
 *   average: (number | null)[],
 *   unit: string,
 *   minimum: number,
 *   maximum?: number,
 * }} series
 */
export function createProgressChart(canvas, series) {
  const colors = palette();
  const chart = new ChartConstructor(canvas, {
    type: "line",
    data: {
      labels: series.labels,
      datasets: [
        {
          label: series.label,
          data: series.values,
          tbaRole: "sessions",
          borderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 5,
          tension: 0.25,
          spanGaps: false,
        },
        {
          label: series.averageLabel,
          data: series.average,
          tbaRole: "average",
          borderWidth: 2,
          borderDash: [6, 4],
          pointRadius: 0,
          pointHoverRadius: 0,
          tension: 0.25,
          spanGaps: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          position: "bottom",
          labels: { boxWidth: 12, usePointStyle: true },
        },
        tooltip: {
          borderWidth: 1,
          callbacks: {
            label(context) {
              const value = context.parsed.y;
              if (value === null || value === undefined) {
                return `${context.dataset.label}: —`;
              }
              return `${context.dataset.label}: ${Number(value).toFixed(1)}${series.unit}`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 },
        },
        y: {
          beginAtZero: true,
          min: series.minimum,
          max: series.maximum,
          ticks: { maxTicksLimit: 6 },
          title: {
            display: true,
            text: series.unit === "%" ? "Accuracy (%)" : "Net WPM",
          },
        },
      },
    },
  });

  styleDatasets(chart, colors);
  styleAxes(chart, colors);
  return chart;
}
