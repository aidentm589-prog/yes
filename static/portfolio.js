const portfolioList = document.getElementById("portfolio-list");
const portfolioActionStatus = document.getElementById("portfolio-action-status");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function parseMoney(value) {
  const digits = String(value || "").replace(/[^\d.-]/g, "");
  if (!digits) {
    return null;
  }
  const parsed = Number(digits);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatMoney(value) {
  if (!Number.isFinite(value)) {
    return "";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function midpointFromRange(rangeText = "") {
  const parts = String(rangeText).split(" - ").map((part) => parseMoney(part));
  if (parts.length !== 2 || !Number.isFinite(parts[0]) || !Number.isFinite(parts[1])) {
    return null;
  }
  return (parts[0] + parts[1]) / 2;
}

function profitClass(value) {
  if (!Number.isFinite(value)) {
    return "";
  }
  return value >= 0 ? "metric-positive" : "metric-negative";
}

function confidenceClass(value) {
  const numeric = parseMoney(value);
  if (!Number.isFinite(numeric)) {
    return "";
  }
  if (numeric < 35) {
    return "metric-confidence-low";
  }
  if (numeric < 70) {
    return "metric-confidence-mid";
  }
  return "metric-confidence-high";
}

function estimatedProfit(preview) {
  const midpoint = midpointFromRange(preview.expected_resale_range || "");
  const buy = parseMoney(preview.final_buy_price || preview.suggested_buy_price || "");
  if (!Number.isFinite(midpoint) || !Number.isFinite(buy)) {
    return "";
  }
  return formatMoney(midpoint - buy);
}

function formatPreview(preview) {
  const profit = estimatedProfit(preview);
  const confidenceRisk = [preview.confidence || "", preview.risk || ""].filter(Boolean).join(" • ");
  return [
    ["Safe Buy Value", preview.suggested_buy_price || ""],
    ["Expected Resale Value", preview.expected_resale_range || ""],
    ["Average Price Near This Mileage", preview.average_price_near_mileage || ""],
    ["Estimated Profit", profit],
    ["Risk + Confidence", confidenceRisk],
  ]
    .filter(([, value]) => value)
    .map(
      ([label, value]) => `
        <div class="portfolio-preview-row">
          <span>${escapeHtml(label)}</span>
          <strong class="${escapeHtml(
            label === "Estimated Profit"
              ? profitClass(parseMoney(value))
              : label === "Risk + Confidence"
                ? confidenceClass(preview.confidence || "")
                : "",
          )}">${escapeHtml(value)}</strong>
        </div>
      `,
    )
    .join("");
}

async function loadPortfolio() {
  const response = await fetch("/api/portfolio");
  const payload = await response.json();
  if (!payload.ok || !Array.isArray(payload.items) || payload.items.length === 0) {
    portfolioList.textContent = "No saved evaluations yet.";
    return;
  }

  portfolioList.classList.remove("muted");
  portfolioList.innerHTML = payload.items
    .map((item) => `
      <article class="portfolio-card-shell">
        <button
          type="button"
          class="ghost-button danger-button portfolio-delete-button"
          data-id="${item.id}"
          data-title="${escapeHtml(item.vehicle_title)}"
        >
          Delete
        </button>
        <a class="listing-card listing-card-link portfolio-card" href="/portfolio/${item.id}">
          <div class="listing-card-head">
            <div>
              <strong class="listing-card-title">${escapeHtml(item.vehicle_title)}</strong>
              <span class="listing-card-hover">Open saved evaluation</span>
            </div>
          </div>
          <div class="listing-meta">
            ${formatPreview(item.preview || {})}
          </div>
        </a>
      </article>
    `)
    .join("");
}

async function deleteEvaluation(id, title) {
  if (!window.confirm(`Delete ${title || "this evaluation"} from your portfolio?`)) {
    return;
  }

  if (portfolioActionStatus) {
    portfolioActionStatus.textContent = "Deleting evaluation...";
  }

  const response = await fetch(`/api/portfolio/${id}`, { method: "DELETE" });
  const payload = await response.json();
  if (!payload.ok) {
    throw new Error(payload.message || "Unable to delete evaluation.");
  }

  if (portfolioActionStatus) {
    portfolioActionStatus.textContent = "Evaluation deleted.";
  }
  await loadPortfolio();
}

portfolioList?.addEventListener("click", async (event) => {
  const button = event.target.closest(".portfolio-delete-button");
  if (!button) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  try {
    await deleteEvaluation(button.dataset.id, button.dataset.title);
  } catch (error) {
    if (portfolioActionStatus) {
      portfolioActionStatus.textContent = error.message;
    }
  }
});

loadPortfolio().catch((error) => {
  portfolioList.textContent = `Unable to load portfolio: ${error.message}`;
});
