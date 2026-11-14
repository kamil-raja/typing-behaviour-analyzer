/* history-page.js — paginated session history screen.
 *
 * Layer responsibility: presentation only. Sessions and their stored metrics
 * come from GET /api/sessions?limit=&offset=; this module formats those values
 * for display and never computes or re-derives a metric. Selecting a row opens
 * that session's results page.
 */

const root = document.querySelector("[data-history-root]");

if (root) {
  const table = root.querySelector("[data-history-table]");
  const rows = root.querySelector("[data-history-rows]");
  const statusLine = root.querySelector("[data-history-status]");
  const emptyState = root.querySelector("[data-history-empty]");
  const pagination = root.querySelector("[data-history-pagination]");
  const pageStatus = root.querySelector("[data-history-page-status]");
  const previousButton = root.querySelector("[data-history-prev]");
  const nextButton = root.querySelector("[data-history-next]");

  const pageSize = Number(root.dataset.pageSize) || 25;
  const DASH = "—";

  let offset = 0;
  let total = 0;
  let loading = false;

  function oneDecimal(value) {
    return value === null || value === undefined ? DASH : Number(value).toFixed(1);
  }

  function formatDate(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
  }

  function formatMode(item) {
    return item.mode === "time"
      ? `Time ${Math.round(item.duration_limit_ms / 1000)} s`
      : "Passage";
  }

  function cell(text, className) {
    const element = document.createElement("td");
    element.textContent = text;
    if (className) {
      element.className = className;
    }
    return element;
  }

  function resultsHref(sessionId) {
    return `/results/${encodeURIComponent(sessionId)}`;
  }

  function buildRow(item) {
    const row = document.createElement("tr");
    row.className = "history-table__row";
    row.addEventListener("click", (event) => {
      if (event.target.closest("a")) {
        return;
      }
      window.location.assign(resultsHref(item.session_id));
    });

    const dateCell = document.createElement("td");
    const link = document.createElement("a");
    link.className = "history-table__link";
    link.href = resultsHref(item.session_id);
    link.textContent = formatDate(item.created_at);
    dateCell.append(link);

    row.append(
      dateCell,
      cell(formatMode(item)),
      cell(`${(Number(item.active_duration_ms) / 1000).toFixed(1)} s`, "numeric"),
      cell(oneDecimal(item.net_wpm), "numeric"),
      cell(item.accuracy_pct === null ? DASH : `${oneDecimal(item.accuracy_pct)}%`, "numeric"),
      cell(oneDecimal(item.consistency_score), "numeric"),
    );
    return row;
  }

  function render(itemCount) {
    const isEmpty = total === 0;
    emptyState.hidden = !isEmpty;
    table.hidden = isEmpty;
    pagination.hidden = isEmpty;
    statusLine.hidden = true;

    if (isEmpty) {
      return;
    }

    const page = Math.floor(offset / pageSize) + 1;
    const pageCount = Math.ceil(total / pageSize);
    pageStatus.textContent =
      `Page ${page} of ${pageCount} · sessions ${offset + 1}-${offset + itemCount} of ${total}`;
    previousButton.disabled = offset === 0;
    nextButton.disabled = offset + pageSize >= total;
  }

  async function load() {
    if (loading) {
      return;
    }
    loading = true;
    statusLine.hidden = false;
    statusLine.textContent = "Loading sessions…";

    try {
      const response = await fetch(`/api/sessions?limit=${pageSize}&offset=${offset}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      total = data.total;
      rows.replaceChildren(...data.items.map(buildRow));
      render(data.items.length);
    } catch (error) {
      table.hidden = true;
      emptyState.hidden = true;
      pagination.hidden = true;
      statusLine.hidden = false;
      statusLine.textContent = "Could not load session history.";
    } finally {
      loading = false;
    }
  }

  previousButton.addEventListener("click", () => {
    offset = Math.max(0, offset - pageSize);
    load();
  });

  nextButton.addEventListener("click", () => {
    if (offset + pageSize < total) {
      offset += pageSize;
      load();
    }
  });

  load();
}
