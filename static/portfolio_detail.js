const evaluationId = window.PORTFOLIO_EVALUATION_ID;
const titleElement = document.getElementById("portfolio-detail-title");
const subtitleElement = document.getElementById("portfolio-detail-subtitle");
const overviewElement = document.getElementById("portfolio-detail-overview");
const sectionsElement = document.getElementById("portfolio-detail-sections");
const portfolioFinalBuyPrice = document.getElementById("portfolio-final-buy-price");
const portfolioUpdateButton = document.getElementById("portfolio-update-button");
const portfolioUpdateStatus = document.getElementById("portfolio-update-status");
const portfolioDeleteButton = document.getElementById("portfolio-delete-button");

const RISK_MULTIPLIERS = {
  Low: 0.97,
  Medium: 0.93,
  High: 0.88,
};

const CONDITION_MULTIPLIERS = [
  ["Poor", 0.88],
  ["Fair", 0.94],
  ["Good", 1.0],
  ["Very Good", 1.04],
  ["Excellent", 1.08],
];

let currentItem = null;

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
    return "$0";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatMiles(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return "";
  }
  return `${numeric.toLocaleString()} miles`;
}

function formatDateTime(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function cleanTrim(value) {
  let text = String(value || "").trim();
  if (!text) {
    return "";
  }
  text = text.split(/\s[-|]\s|•|·|\(/, 1)[0].trim();
  text = text.replace(/\b(all wheel drive|awd|fwd|rwd|quattro|xdrive|clean|new tires?|carplay|tint(?:ed)?|windows?)\b.*/i, "").trim();
  text = text.replace(/\b(sedan|coupe|hatchback|wagon|convertible|suv|truck|4d|4dr|4-door|4 door)\b.*/i, "").trim();
  const tokens = text.split(/\s+/).filter(Boolean).slice(0, 3);
  return tokens.join(" ").trim();
}

function midpointFromRange(rangeText = "") {
  const parts = String(rangeText).split(" - ").map((part) => parseMoney(part));
  if (parts.length !== 2 || !Number.isFinite(parts[0]) || !Number.isFinite(parts[1])) {
    return null;
  }
  return (parts[0] + parts[1]) / 2;
}

function profitClassName(value) {
  if (!Number.isFinite(value)) {
    return "";
  }
  return value >= 0 ? "metric-positive" : "metric-negative";
}

function confidenceClassName(value) {
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

function riskLabelFromConfidence(confidence) {
  if (!Number.isFinite(confidence)) {
    return "Medium";
  }
  if (confidence >= 80) {
    return "Low";
  }
  if (confidence >= 62) {
    return "Medium";
  }
  return "High";
}

function computeDealConfidence(baseConfidence, finalBuyPrice, expectedResaleMidpoint, suggestedBuy) {
  if (!Number.isFinite(baseConfidence)) {
    return 0;
  }
  if (!Number.isFinite(finalBuyPrice) || finalBuyPrice <= 0 || !Number.isFinite(expectedResaleMidpoint) || expectedResaleMidpoint <= 0) {
    return Math.round(baseConfidence);
  }

  const marginRatio = (expectedResaleMidpoint - finalBuyPrice) / expectedResaleMidpoint;
  let adjustedConfidence = baseConfidence + (marginRatio - 0.18) * 120;

  if (Number.isFinite(suggestedBuy) && suggestedBuy > 0 && finalBuyPrice > suggestedBuy) {
    adjustedConfidence -= ((finalBuyPrice - suggestedBuy) / expectedResaleMidpoint) * 120;
  }

  return Math.max(5, Math.min(95, Math.round(adjustedConfidence)));
}

function cleanVehicleTitle(parsedDetails = {}, fallback = "") {
  const base = [
    parsedDetails.year,
    parsedDetails.make,
    parsedDetails.model,
    cleanTrim(parsedDetails.trim),
  ].filter(Boolean).join(" ").trim();
  return base || fallback || "Saved Evaluation";
}

function buildListingTitle(listing = {}) {
  if (listing.title) {
    return listing.title;
  }
  return [
    listing.year,
    listing.make,
    listing.model,
    listing.trim,
  ].filter(Boolean).join(" ").trim() || "Comparable listing";
}

function renderKeyValueGrid(title, entries, copy = "") {
  const rows = entries
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(
      ([label, value]) => `
        <div class="portfolio-preview-row">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(String(value))}</strong>
        </div>
      `,
    )
    .join("");

  return `
    <article class="panel portfolio-section">
      <div class="results-head">
        <strong>${escapeHtml(title)}</strong>
      </div>
      ${copy ? `<p class="portfolio-section-copy">${escapeHtml(copy)}</p>` : ""}
      <div class="portfolio-section-grid">
        ${rows || '<div class="muted">No data available.</div>'}
      </div>
    </article>
  `;
}

function renderConditionSweep(values = {}) {
  const cards = Object.entries(values).map(([label, payload]) => `
    <article class="condition-card">
      <h3>${escapeHtml(label)}</h3>
      <div class="value-line">
        <span>Estimated Range</span>
        <strong>${escapeHtml(payload.estimated_range || "")}</strong>
      </div>
      <div class="value-line">
        <span>Average Mileage</span>
        <strong>${escapeHtml(payload.average_mileage || "")}</strong>
      </div>
    </article>
  `).join("");

  return `
    <section class="panel portfolio-section">
      <div class="results-head">
        <strong>Condition Sweep</strong>
      </div>
      <div class="portfolio-condition-grid">
        ${cards || '<div class="muted">No condition values were saved for this evaluation.</div>'}
      </div>
    </section>
  `;
}

function renderProfitSection(full = {}) {
  const rows = Array.isArray(full.profit_table) ? full.profit_table : [];
  const tableRows = rows
    .map((row) => `
      <tr>
        <td>${escapeHtml(row.condition || "")}</td>
        <td>${escapeHtml(row.likely_resale || "")}</td>
        <td>${escapeHtml(row.likely_profit || "")}</td>
      </tr>
    `)
    .join("");

  return `
    <section class="panel portfolio-section">
      <div class="results-head">
        <strong>Profit Outlook</strong>
      </div>
      <div class="portfolio-section-grid">
        <div class="portfolio-preview-row">
          <span>Suggested Buy Price</span>
          <strong>${escapeHtml(full.suggested_buy_price || "Pending")}</strong>
        </div>
        <div class="portfolio-preview-row">
          <span>Final Buy Price</span>
          <strong>${escapeHtml(full.final_buy_price || "Pending")}</strong>
        </div>
        <div class="portfolio-preview-row">
          <span>Expected Resale Midpoint</span>
          <strong>${escapeHtml(full.expected_resale_midpoint || "")}</strong>
        </div>
        <div class="portfolio-preview-row">
          <span>Confidence</span>
          <strong>${escapeHtml(full.confidence || "")}</strong>
        </div>
        <div class="portfolio-preview-row">
          <span>Risk</span>
          <strong>${escapeHtml(full.risk || "")}</strong>
        </div>
      </div>
      <div class="portfolio-table-wrap">
        <table class="profit-table portfolio-table">
          <thead>
            <tr>
              <th>Condition</th>
              <th>Likely Resale</th>
              <th>Likely Profit</th>
            </tr>
          </thead>
          <tbody>
            ${tableRows || '<tr><td colspan="3" class="muted">Add a final buy price to save the full profit sweep.</td></tr>'}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function pickTopRelevantComps(parsed, matchedComps = []) {
  const targetMileage = Number(parsed?.mileage || 0) || null;
  return [...matchedComps]
    .sort((left, right) => {
      const scoreGap = Number(right.relevance_score || 0) - Number(left.relevance_score || 0);
      if (scoreGap !== 0) {
        return scoreGap;
      }
      if (targetMileage) {
        const leftMileage = Math.abs((Number(left.mileage || 0) || targetMileage) - targetMileage);
        const rightMileage = Math.abs((Number(right.mileage || 0) || targetMileage) - targetMileage);
        if (leftMileage !== rightMileage) {
          return leftMileage - rightMileage;
        }
      }
      const leftPrice = parseMoney(left.adjusted_price || left.price) || Number.MAX_SAFE_INTEGER;
      const rightPrice = parseMoney(right.adjusted_price || right.price) || Number.MAX_SAFE_INTEGER;
      return leftPrice - rightPrice;
    })
    .slice(0, 4);
}

function renderComparableListings(parsed, matchedComps = []) {
  const cards = pickTopRelevantComps(parsed, matchedComps).map((listing) => {
    const safeUrl = typeof listing.url === "string" && /^https?:\/\//.test(listing.url)
      ? listing.url
      : "";
    const title = buildListingTitle(listing);
    const meta = [
      listing.trim ? ["Trim", listing.trim] : null,
      listing.mileage ? ["Mileage", formatMiles(listing.mileage)] : null,
      listing.adjusted_price ? ["Adjusted", listing.adjusted_price] : null,
      listing.source_label ? ["Source", listing.source_label] : null,
      listing.match_tier ? ["Match Tier", listing.match_tier] : null,
      listing.title_status ? ["Title", listing.title_status] : null,
    ]
      .filter(Boolean)
      .map(
        ([label, value]) => `
          <div class="listing-meta-line">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(String(value))}</strong>
          </div>
        `,
      )
      .join("");

    const cardInner = `
      <div class="listing-card-head">
        <div>
          <strong class="listing-card-title">${escapeHtml(title)}</strong>
          <span class="listing-card-hover">${escapeHtml(listing.url ? "Open comparable listing" : "Comparable listing")}</span>
        </div>
        <span class="listing-price">${escapeHtml(listing.price || "")}</span>
      </div>
      <div class="listing-meta">
        ${meta}
      </div>
    `;

    if (safeUrl) {
      return `
        <a class="listing-card listing-card-link" href="${escapeHtml(safeUrl)}" target="_blank" rel="noreferrer">
          ${cardInner}
        </a>
      `;
    }

    return `
      <article class="listing-card">
        ${cardInner}
      </article>
    `;
  }).join("");

  return `
    <section class="panel portfolio-section">
      <div class="results-head">
        <strong>Comparable Listings</strong>
      </div>
      <p class="portfolio-section-copy">The top 4 most relevant comps are shown here for a fast read on the saved deal.</p>
      <div class="portfolio-listings-grid">
        ${cards || '<div class="muted">No comparable listings were saved.</div>'}
      </div>
    </section>
  `;
}

function renderExcludedComps(excludedComps = []) {
  return renderKeyValueGrid(
    "Excluded Comps",
    excludedComps.slice(0, 18).map((entry) => [
      entry.title || entry.source || "Excluded comp",
      [entry.price, entry.reason].filter(Boolean).join(" • "),
    ]),
    "These are the listings the engine found but intentionally filtered out during scoring.",
  );
}

function renderTitleImpact(titleAdjustment = {}) {
  if (!titleAdjustment.active) {
    return "";
  }

  return renderKeyValueGrid(
    "Title Impact",
    [
      ["Clean Title Benchmark", titleAdjustment.clean_title_value || ""],
      [
        "Clean Title Range",
        titleAdjustment.clean_title_range
          ? `${titleAdjustment.clean_title_range.low} to ${titleAdjustment.clean_title_range.high}`
          : "",
      ],
      [
        "Rebuilt Title Range",
        titleAdjustment.rebuilt_title_range
          ? `${titleAdjustment.rebuilt_title_range.low} to ${titleAdjustment.rebuilt_title_range.high}`
          : "",
      ],
      ["Average Rebuilt Value", titleAdjustment.rebuilt_title_average || ""],
      [
        "Value Difference",
        titleAdjustment.value_difference
          ? `${titleAdjustment.value_difference.low} to ${titleAdjustment.value_difference.high}`
          : "",
      ],
      [
        "Rebuilt Safe Buy Window",
        titleAdjustment.safe_buy_range
          ? `${titleAdjustment.safe_buy_range.low} to ${titleAdjustment.safe_buy_range.high}`
          : "",
      ],
      ["Damage Factor", titleAdjustment.damage_factor_range || ""],
    ],
    titleAdjustment.note || "",
  );
}

function buildFullSummary(front, existingFull = {}, finalBuyOverride = "") {
  const resaleRange = front.recommended_target_resale_range || {};
  const resaleLow = parseMoney(resaleRange.low);
  const resaleHigh = parseMoney(resaleRange.high);
  const baseConfidence = Number(front.confidence_score || 0);
  const suggestedBuy = parseMoney(front.recommended_max_buy_price) || null;
  const finalBuyNumber = finalBuyOverride ? Number(finalBuyOverride) : parseMoney(existingFull.final_buy_price);
  const hasFinalBuyPrice = Number.isFinite(finalBuyNumber) && finalBuyNumber > 0;
  const midpoint = Number.isFinite(resaleLow) && Number.isFinite(resaleHigh) ? (resaleLow + resaleHigh) / 2 : 0;
  const marketConfidence = Math.max(0, Math.min(1, baseConfidence / 100));
  const marketRisk = riskLabelFromConfidence(baseConfidence);
  const marketRiskMultiplier = RISK_MULTIPLIERS[marketRisk] || RISK_MULTIPLIERS.Medium;
  const adjustedResaleBase = midpoint
    ? midpoint * (0.85 + 0.15 * marketConfidence) * marketRiskMultiplier
    : 0;
  const dynamicConfidence = hasFinalBuyPrice
    ? computeDealConfidence(baseConfidence, finalBuyNumber, midpoint, suggestedBuy)
    : Math.round(baseConfidence);

  return {
    vehicle_summary: cleanVehicleTitle(front.parsed_details || {}, front.vehicle_summary || ""),
    suggested_buy_price: suggestedBuy ? formatMoney(suggestedBuy) : "",
    final_buy_price: hasFinalBuyPrice ? formatMoney(finalBuyNumber) : "",
    average_price_near_mileage: front.average_price_near_mileage?.value
      || front.average_price_near_mileage?.message
      || existingFull.average_price_near_mileage
      || "",
    expected_resale_range: resaleRange.low && resaleRange.high ? `${resaleRange.low} - ${resaleRange.high}` : "",
    expected_resale_midpoint: midpoint ? formatMoney(midpoint) : "",
    confidence: `${dynamicConfidence}%`,
    risk: riskLabelFromConfidence(dynamicConfidence),
    comparable_count: front.comparable_count || 0,
    profit_table: CONDITION_MULTIPLIERS.map(([label, multiplier]) => {
      const likelyResale = adjustedResaleBase * multiplier;
      return {
        condition: label,
        likely_resale: formatMoney(likelyResale),
        likely_profit: hasFinalBuyPrice ? formatMoney(likelyResale - finalBuyNumber) : "Enter buy price",
      };
    }),
  };
}

function computeEstimatedProfitValue(full = {}) {
  const midpoint = parseMoney(full.expected_resale_midpoint) || midpointFromRange(full.expected_resale_range || "");
  const buy = parseMoney(full.final_buy_price || full.suggested_buy_price || "");
  if (!Number.isFinite(midpoint) || !Number.isFinite(buy)) {
    return null;
  }
  return midpoint - buy;
}

function computeSpreadText(front = {}, full = {}) {
  const resaleRange = front.recommended_target_resale_range || {};
  const low = parseMoney(resaleRange.low);
  const high = parseMoney(resaleRange.high);
  const buy = parseMoney(full.final_buy_price || full.suggested_buy_price || "");
  if (!Number.isFinite(low) || !Number.isFinite(high) || !Number.isFinite(buy)) {
    return "";
  }
  return `${formatMoney(low - buy)} to ${formatMoney(high - buy)}`;
}

function lowestCompText(matchedComps = []) {
  const sorted = [...matchedComps]
    .map((listing) => ({
      price: parseMoney(listing.price),
      title: buildListingTitle(listing),
    }))
    .filter((listing) => Number.isFinite(listing.price))
    .sort((left, right) => left.price - right.price);
  if (!sorted.length) {
    return "";
  }
  return `${formatMoney(sorted[0].price)} • ${sorted[0].title}`;
}

function overviewCard(label, value, className = "") {
  return `
    <article class="listing-card">
      <span class="muted">${escapeHtml(label)}</span>
      <strong class="${escapeHtml(className)}">${escapeHtml(value || "Pending")}</strong>
    </article>
  `;
}

function renderOverview(front, full) {
  const overall = front.overall_range || {};
  const distribution = front.price_distribution || {};
  const estimatedProfit = computeEstimatedProfitValue(full);
  const confidenceRisk = [full.confidence || "", full.risk || ""].filter(Boolean).join(" • ");
  const marketValue = distribution.weighted_median || front.adjusted_price_estimate?.weighted_median || "";
  const bestComp = lowestCompText(front.matched_comps || []);
  const spread = computeSpreadText(front, full);
  overviewElement.classList.remove("muted");
  overviewElement.innerHTML = `
    ${overviewCard("Safe Buy Value", full.suggested_buy_price || "")}
    ${overviewCard("Expected Resale Value", full.expected_resale_range || "")}
    ${overviewCard("Average Price Near This Mileage", full.average_price_near_mileage || "")}
    ${overviewCard("Estimated Profit", estimatedProfit === null ? "" : formatMoney(estimatedProfit), profitClassName(estimatedProfit))}
    ${overviewCard("Risk + Confidence", confidenceRisk, confidenceClassName(full.confidence || ""))}
    ${overviewCard("Market Value", marketValue)}
    ${overviewCard("Final Buy Price", full.final_buy_price || "")}
    ${overviewCard("Comp Count", String(full.comparable_count || front.comparable_count || "0"))}
    ${overviewCard("Price Range", overall.estimated_range ? `${overall.estimated_range.low} to ${overall.estimated_range.high}` : "")}
    ${overviewCard("Best / Lowest Comp", bestComp)}
    ${overviewCard("Spread", spread)}
  `;
}

function renderSections(front, full) {
  const parsed = front.parsed_details || {};
  const overall = front.overall_range || {};
  const values = front.values || {};
  const distribution = front.price_distribution || {};
  const mileageBands = front.mileage_price_bands || [];
  const matchedComps = front.matched_comps || [];
  const titleAdjustment = front.title_adjustment || {};

  sectionsElement.classList.remove("muted");
  sectionsElement.innerHTML = [
    renderKeyValueGrid("Vehicle Profile", [
      ["Year", parsed.year || ""],
      ["Make", parsed.make || ""],
      ["Model", parsed.model || ""],
      ["Trim", parsed.trim || ""],
      ["Mileage", formatMiles(parsed.mileage)],
      ["Body Style", parsed.body_style || ""],
      ["Drivetrain", parsed.drivetrain || ""],
      ["Transmission", parsed.transmission || ""],
      ["Exterior Color", parsed.exterior_color || ""],
      ["Title Status", parsed.title_status || ""],
      ["ZIP", parsed.zip_code || ""],
      ["State", parsed.state || ""],
      ["VIN", parsed.vin || ""],
    ]),
    renderKeyValueGrid("Market Snapshot", [
      ["Original Search", currentItem.vehicle_input || parsed.vehicle_input || ""],
      ["Reseller Buy Price", overall.reseller_buy_price || ""],
      ["Weighted Median", distribution.weighted_median || ""],
      ["Trimmed Median", distribution.trimmed_median || ""],
      ["Saved On", formatDateTime(currentItem.created_at || "")],
      ["Last Updated", formatDateTime(currentItem.updated_at || "")],
    ]),
    renderTitleImpact(titleAdjustment),
    renderConditionSweep(values),
    renderProfitSection(full),
    renderKeyValueGrid(
      "Mileage Averages",
      mileageBands.map((band) => [band.label, `${band.average_price} using ${band.count} comps`]),
      "These mileage clusters are saved from the front evaluation so you can compare this car against nearby market mileage bands.",
    ),
    renderComparableListings(parsed, matchedComps),
  ].join("");
}

async function updateSavedEvaluation() {
  if (!currentItem) {
    return;
  }

  const front = currentItem.snapshot?.front_evaluation || {};
  const full = buildFullSummary(front, currentItem.snapshot?.full_evaluation || {}, portfolioFinalBuyPrice.value.trim());
  if (!full.final_buy_price) {
    portfolioUpdateStatus.textContent = "Enter a final buy price before updating.";
    return;
  }

  const payload = {
    vehicle_title: cleanVehicleTitle(front.parsed_details || {}, front.vehicle_summary || ""),
    preview: {
      comparable_count: `${front.comparable_count || 0} comps`,
      final_buy_price: full.final_buy_price,
      suggested_buy_price: full.suggested_buy_price,
      expected_resale_range: full.expected_resale_range,
      confidence: full.confidence,
      risk: full.risk,
    },
    snapshot: {
      front_evaluation: front,
      full_evaluation: full,
    },
  };

  portfolioUpdateStatus.textContent = "Updating evaluation...";
  portfolioUpdateButton.disabled = true;

  try {
    const response = await fetch(`/api/portfolio/${evaluationId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!result.ok) {
      throw new Error(result.message || "Unable to update evaluation.");
    }

    currentItem.preview = payload.preview;
    currentItem.snapshot = payload.snapshot;
    titleElement.textContent = payload.vehicle_title;
    subtitleElement.textContent = `Saved from ${front.comparable_count || 0} matched comps • Updated ${formatDateTime(new Date().toISOString())}`;
    renderOverview(front, full);
    renderSections(front, full);
    portfolioUpdateStatus.textContent = "Saved final buy price to portfolio.";
  } catch (error) {
    portfolioUpdateStatus.textContent = error.message;
  } finally {
    portfolioUpdateButton.disabled = false;
  }
}

async function loadPortfolioDetail() {
  const response = await fetch(`/api/portfolio/${evaluationId}`);
  const payload = await response.json();
  if (!payload.ok) {
    subtitleElement.textContent = payload.message || "Unable to load saved evaluation.";
    sectionsElement.textContent = subtitleElement.textContent;
    return;
  }

  currentItem = payload.item;
  const snapshot = currentItem.snapshot || {};
  const front = snapshot.front_evaluation || {};
  const full = buildFullSummary(front, snapshot.full_evaluation || {});

  titleElement.textContent = cleanVehicleTitle(front.parsed_details || {}, currentItem.vehicle_title);
  subtitleElement.textContent = `Saved from ${front.comparable_count || 0} matched comps • ${formatDateTime(currentItem.updated_at || currentItem.created_at || "")}`;
  portfolioFinalBuyPrice.value = parseMoney(full.final_buy_price) ? String(parseMoney(full.final_buy_price)) : "";

  renderOverview(front, full);
  renderSections(front, full);
}

async function deletePortfolioEvaluation() {
  if (!currentItem) {
    return;
  }
  if (!window.confirm(`Delete ${currentItem.vehicle_title || "this evaluation"} from your portfolio?`)) {
    return;
  }

  portfolioUpdateStatus.textContent = "Deleting evaluation...";
  const response = await fetch(`/api/portfolio/${evaluationId}`, { method: "DELETE" });
  const payload = await response.json();
  if (!payload.ok) {
    portfolioUpdateStatus.textContent = payload.message || "Unable to delete evaluation.";
    return;
  }
  window.location.href = "/portfolio";
}

portfolioUpdateButton?.addEventListener("click", updateSavedEvaluation);
portfolioDeleteButton?.addEventListener("click", deletePortfolioEvaluation);

loadPortfolioDetail().catch((error) => {
  subtitleElement.textContent = `Unable to load saved evaluation: ${error.message}`;
});
