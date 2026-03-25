const form = document.getElementById("lookup-form");
const vehicleInput = document.getElementById("vehicle-input");
const vehicleInputLabel = document.getElementById("vehicle-input-label");
const vehicleInputHelper = document.getElementById("vehicle-input-helper");
const mileageField = document.getElementById("mileage-field");
const listingPriceField = document.getElementById("listing-price-field");
const rebuiltToggleRow = document.getElementById("rebuilt-toggle-row");
const evaluationModeSelect = document.getElementById("evaluation-mode");
const detailedVehicleReportSelect = document.getElementById("detailed-vehicle-report");
const evaluationModeCards = document.getElementById("evaluation-mode-cards");
const detailedReportCard = document.getElementById("detailed-report-card");
const statusMessage = document.getElementById("status-message");
const statusNotes = document.getElementById("status-notes");
const sessionBadge = document.getElementById("session-badge");
const sourceSummary = document.getElementById("source-summary");
const conditionValues = document.getElementById("condition-values");
const mileagePriceBands = document.getElementById("mileage-price-bands");
const mileageBandSelect = document.getElementById("mileage-band-select");
const mileageBandOutput = document.getElementById("mileage-band-output");
const overallRange = document.getElementById("overall-range");
const sampleListings = document.getElementById("sample-listings");
const compsToolbar = document.getElementById("comps-toolbar");
const compsCountLabel = document.getElementById("comps-count-label");
const showAllCompsButton = document.getElementById("show-all-comps");
const fullEvaluationLink = document.getElementById("full-evaluation-link");
const loadingPanel = document.getElementById("loading-panel");
const loadingMessage = document.getElementById("loading-message");
const loadingTitle = document.getElementById("loading-title");
const loadingKicker = document.getElementById("loading-kicker");
const resultsStatusPanel = document.getElementById("results-status-panel");
const resultsGrid = document.getElementById("results-grid");
const resultsTitleImpactPanel = document.getElementById("results-title-impact-panel");
const resultsPricingPanel = document.getElementById("results-pricing-panel");
const resultsCompsPanel = document.getElementById("results-comps-panel");
const resultsConditionsPanel = document.getElementById("results-conditions-panel");
const resultsDetailedReportPanel = document.getElementById("results-detailed-report-panel");
const detailedVehicleReportOutput = document.getElementById("detailed-vehicle-report-output");
const bulkResultsPanel = document.getElementById("bulk-results-panel");
const bulkResultsSummary = document.getElementById("bulk-results-summary");
const bulkResultsGrid = document.getElementById("bulk-results-grid");
const dealTransitionPanel = document.getElementById("deal-transition-panel");
const composerPanel = document.querySelector(".composer.panel");
const titleImpact = document.getElementById("title-impact");
const listingPriceAnalysis = document.getElementById("listing-price-analysis");
const previewMarketValue = document.getElementById("preview-market-value");
const previewSafeBuy = document.getElementById("preview-safe-buy");
const previewExpectedResale = document.getElementById("preview-expected-resale");
const previewEstimatedProfit = document.getElementById("preview-estimated-profit");
const previewConfidence = document.getElementById("preview-confidence");
const previewRisk = document.getElementById("preview-risk");
const favoriteFromMain = document.getElementById("favorite-from-main");
const mainFavoriteStatus = document.getElementById("main-favorite-status");
const stickyPortfolioButton = document.querySelector(".sticky-portfolio-button");
const compSortSelect = document.getElementById("comp-sort-select");
const accountStatusPill = document.querySelector(".account-status-pill");
const topbarCreditValue = document.getElementById("topbar-credit-value");
const topbarTierLabel = document.getElementById("topbar-tier-label");
const topbarTierDefault = document.getElementById("topbar-tier-default");
const topbarTierHover = document.getElementById("topbar-tier-hover");
const DEFAULT_VISIBLE_COMPS = 6;
const EVALUATION_CACHE_KEY = "car-flip-analyzer:latest-evaluation";

let currentComparableListings = [];
let showingAllComparableListings = false;
let currentMileageBands = [];
let currentMainEvaluation = null;
let loadingProgressTimer = null;
let loadingProgressValue = 0;
let currentCompSort = "closest_mileage";
let loadingMessageTimer = null;
const loadingPhases = [
  "Scraping comps from live sources",
  "Normalizing listings and filtering noise",
  "Comparing mileage and trim alignment",
  "Analyzing numbers and shaping the deal",
];

const STAT_HELP = {
  year: "The model year the engine parsed or normalized from your input, link, VIN, or listing data.",
  make: "The manufacturer matched from your input and normalization pipeline.",
  model: "The model name matched from your input, VIN data, and comp normalization.",
  trim: "The trim or package level used to keep comparable listings aligned as closely as possible.",
  mileage: "The mileage used as the main distance anchor for closest-mileage pricing and comp matching.",
  asking_price: "The listing price you entered or the scraper recovered from the listing. If none was found, it stays N/A.",
  title_status: "The title condition detected from input or scraped text, such as clean or rebuilt.",
  zip_code: "Location detail used when available to tighten market relevance.",
  state: "State-level location detail used when available to improve regional matching.",
  color: "Exterior color or normalized vehicle color detail when it could be identified.",
  market_value: "The average adjusted price across all valid comparable listings used in the evaluation.",
  safe_buy_value: "A conservative buy target built from the highest-mileage valid comps, then reduced for safer flip margin.",
  expected_resale_value: "The average adjusted price of the comps closest in mileage to the target vehicle.",
  estimated_profit: "Expected resale value minus safe buy value, used as the base profit spread.",
  imperfect_title_value: "A projected value using imperfect-title math so you can compare clean-title versus damaged-title outcomes.",
  condition_range: "The overall low-to-high pricing span built from the condition sweep and valid market comps.",
  average_price_near_this_mileage: "The average adjusted price from the nearest mileage comps, using only comps within the nearby mileage window.",
  listing_price_vs_avg_near_mileage: "Average price near this mileage minus the listing price, so you can see whether the asking price sits above or below nearby-mileage comps.",
  clean_title_benchmark: "The clean-title anchor value before any title-damage reduction is applied.",
  clean_title_range: "The expected clean-title value band before rebuilt or reconstructed title adjustments.",
  rebuilt_title_range: "The projected value band after applying title-damage reductions to the clean-title value.",
  average_rebuilt_value: "The midpoint rebuilt-title estimate derived from the clean-title benchmark and damage-factor logic.",
  value_difference: "The gap between clean-title pricing and rebuilt-title pricing.",
  average_difference: "The midpoint loss in value caused by the imperfect title adjustment.",
  rebuilt_safe_buy_window: "A more aggressive buy window for rebuilt-title flips, designed to preserve margin.",
  damage_factor: "The percentage reduction applied when projecting imperfect-title value from clean-title value.",
  provided_price: "The listing price you entered or the scraper pulled from the source listing.",
  suggested_target_price: "A target price benchmark built from the same valuation model and current comp picture.",
  market_position: "Where the asking price sits versus market value, including dollar and percentage difference.",
  estimated_profit_at_asking: "Expected resale minus the current asking price instead of minus the safe buy value.",
  negotiation_window: "A practical range between today’s ask and the model’s target number to guide negotiation.",
  takeaway: "A short interpretation of how the asking price compares with the market and deal math.",
  average_listing_price: "The average listing price inside the currently selected mileage band.",
  comparable_listings_used: "The number of comps used for that mileage-band calculation.",
  selected_mileage_range: "The currently selected mileage band used for the mileage-average breakout.",
};

const vehicleFields = [
  ["year", "Year"],
  ["make", "Make"],
  ["model", "Model"],
  ["trim", "Trim"],
  ["mileage", "Mileage"],
  ["vin", "VIN"],
  ["asking_price", "Price"],
  ["title_status", "Title"],
  ["zip_code", "ZIP Code"],
  ["state", "State"],
  ["color", "Color"],
];

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function normalizeStatHelpKey(label = "") {
  return String(label)
    .trim()
    .toLowerCase()
    .replace(/[%/+()-]/g, " ")
    .replace(/[^\w\s]/g, "")
    .replace(/\s+/g, "_");
}

function statHelpText(label = "", explicitKey = "") {
  const keys = [explicitKey, label]
    .map((value) => normalizeStatHelpKey(value))
    .filter(Boolean);
  for (const key of keys) {
    if (STAT_HELP[key]) {
      return STAT_HELP[key];
    }
  }
  return "This stat comes from the current evaluation model using normalized vehicle data and the valid comparable listings gathered for this run.";
}

function renderLabelWithHelp(label, explicitKey = "") {
  const helpText = statHelpText(label, explicitKey);
  return `
    <span class="stat-label-wrap">
      <span>${escapeHtml(label)}</span>
      <button class="stat-help-button" type="button" aria-label="Explain ${escapeHtml(label)}" data-help="${escapeHtml(helpText)}">?</button>
      <span class="stat-help-tooltip">${escapeHtml(helpText)}</span>
    </span>
  `;
}

function renderAccountStatus(status) {
  if (!accountStatusPill && !topbarCreditValue && !topbarTierLabel) {
    return;
  }

  const label = status?.tier_label || "Guest Access";
  const creditOnlyValue = status.is_unlimited
    ? "Unlimited"
    : `${Number(status?.credit_balance || 0)}`;

  if (accountStatusPill && status) {
    accountStatusPill.innerHTML = `
      <strong><a href="/account">My Account</a></strong>
    `;
  }

  if (topbarCreditValue) {
    topbarCreditValue.textContent = creditOnlyValue;
  }
  if (topbarTierLabel) {
    topbarTierLabel.textContent = label;
  }
  if (topbarTierDefault) {
    topbarTierDefault.textContent = status
      ? "Current subscription access"
      : "Explore the analyzer with guest access.";
  }
  if (topbarTierHover) {
    topbarTierHover.textContent = tierHoverCopy(status);
  }
  syncBulkLockState(status);
}

function tierHoverCopy(status) {
  if (!status) {
    return "Sign up to start at Tier 1 and unlock more evaluation power.";
  }
  if (status.tier === 1) {
    return "Upgrade to Tier 2 for Batch Model access and 50 credits.";
  }
  if (status.tier === 2) {
    return "Upgrade to Tier 3 for 500 credits and deeper deal flow.";
  }
  if (status.tier === 3) {
    return "Upgrade to Tier 4 for unlimited usage.";
  }
  if (status.tier === 4) {
    return "Unlimited usage unlocked across the platform.";
  }
  return "Upgrade your access to unlock more evaluation power.";
}

function buildEvaluationCacheFingerprint(payload = {}) {
  return JSON.stringify({
    evaluation_mode: String(payload.evaluation_mode || "zippy").trim().toLowerCase(),
    vehicle_input: String(payload.vehicle_input || "").trim().toLowerCase(),
    mileage: String(payload.mileage || "").trim(),
    rebuilt_title: String(payload.rebuilt_title || "").trim().toLowerCase(),
  });
}

function cacheEvaluationResult(payload = {}, resultBody = {}) {
  try {
    const fingerprint = buildEvaluationCacheFingerprint(payload);
    if (!fingerprint || !resultBody || resultBody.status !== "complete" || resultBody.mode === "zippy") {
      return;
    }
    window.sessionStorage.setItem(
      EVALUATION_CACHE_KEY,
      JSON.stringify({
        fingerprint,
        saved_at: Date.now(),
        payload: resultBody,
      }),
    );
  } catch (error) {
    console.warn("Unable to cache evaluation result.", error);
  }
}

function setResultsVisible(visible) {
  [
    resultsStatusPanel,
    resultsGrid,
    resultsTitleImpactPanel,
    resultsPricingPanel,
    resultsCompsPanel,
    resultsConditionsPanel,
    resultsDetailedReportPanel,
    dealTransitionPanel,
  ].forEach((element) => {
    if (!element) {
      return;
    }
    element.classList.toggle("hidden-panel", !visible);
  });
}

function setBulkResultsVisible(visible) {
  if (!bulkResultsPanel) {
    return;
  }
  bulkResultsPanel.classList.toggle("hidden-panel", !visible);
  resultsStatusPanel?.classList.toggle("hidden-panel", !visible);
}

function hideAllResultPanels() {
  setResultsVisible(false);
  setBulkResultsVisible(false);
}

function showStatusOnly(message, badge = "Needs Data") {
  resultsStatusPanel?.classList.remove("hidden-panel");
  resultsGrid?.classList.add("hidden-panel");
  resultsTitleImpactPanel?.classList.add("hidden-panel");
  resultsPricingPanel?.classList.add("hidden-panel");
  resultsCompsPanel?.classList.add("hidden-panel");
  resultsConditionsPanel?.classList.add("hidden-panel");
  resultsDetailedReportPanel?.classList.add("hidden-panel");
  bulkResultsPanel?.classList.add("hidden-panel");
  dealTransitionPanel?.classList.add("hidden-panel");
  sessionBadge.textContent = badge;
  statusMessage.textContent = message;
}

function isBulkMode() {
  return (evaluationModeSelect?.value || "individual") === "bulk";
}

function selectedEvaluationMode() {
  return evaluationModeSelect?.value || "zippy";
}

function setChoiceCardSelection(groupName, value) {
  document.querySelectorAll(`[data-choice-group="${groupName}"]`).forEach((element) => {
    element.classList.toggle("is-selected", element.getAttribute("data-value") === value);
  });
}

function syncBulkLockState(status) {
  const individualCard = evaluationModeCards?.querySelector('[data-value="individual"]');
  const bulkCard = evaluationModeCards?.querySelector('[data-value="bulk"]');
  if (!individualCard && !bulkCard) {
    syncAddonLockState(status);
    return;
  }
  const individualLocked = !status || (!status.is_unlimited && !status.can_use_individual_model);
  const bulkLocked = !status || (!status.is_unlimited && !status.can_use_bulk_model);
  if (individualCard) {
    individualCard.classList.toggle("is-locked", individualLocked);
    individualCard.setAttribute("aria-disabled", individualLocked ? "true" : "false");
    individualCard.setAttribute("data-lock-message", "Upgrade to Tier 2 to unlock the Individual Evaluation Model.");
  }
  if (bulkCard) {
    bulkCard.classList.toggle("is-locked", bulkLocked);
    bulkCard.setAttribute("aria-disabled", bulkLocked ? "true" : "false");
    bulkCard.setAttribute("data-lock-message", "Upgrade to Tier 3 to unlock the Bulk Evaluation Model.");
  }
  const selectedMode = selectedEvaluationMode();
  if ((selectedMode === "individual" && individualLocked) || (selectedMode === "bulk" && bulkLocked)) {
    evaluationModeSelect.value = "zippy";
  }
  syncAddonLockState(status);
}

function syncAddonLockState(status) {
  const addonLocked = !status || (!status.is_unlimited && !status.has_addon_access);
  if (detailedReportCard) {
    detailedReportCard.classList.toggle("is-locked", addonLocked);
    detailedReportCard.setAttribute("aria-disabled", addonLocked ? "true" : "false");
    if (addonLocked) {
      detailedReportCard.setAttribute("data-lock-message", "Your subscription level does not qualify for juicy add-ons yet.");
    }
  }
}

function setDisabledForField(container, disabled) {
  if (!container) {
    return;
  }
  container.querySelectorAll("input, select, textarea").forEach((element) => {
    if (element === evaluationModeSelect || element === vehicleInput) {
      return;
    }
    element.disabled = disabled;
  });
}

function updateEvaluationModeUI() {
  const mode = selectedEvaluationMode();
  const bulkMode = mode === "bulk";
  const zippyMode = mode === "zippy";
  if (vehicleInputLabel) {
    vehicleInputLabel.textContent = bulkMode ? "Paste the cars" : zippyMode ? "Quick vehicle input" : "Describe the car";
    vehicleInputLabel.classList.toggle("visually-hidden", !(bulkMode || zippyMode));
  }
  if (vehicleInputHelper) {
    vehicleInputHelper.classList.toggle("hidden-panel", !bulkMode);
  }
  if (vehicleInput) {
    vehicleInput.rows = bulkMode ? 10 : 3;
    vehicleInput.placeholder = bulkMode
      ? "Paste the cars"
      : zippyMode
        ? "Year make model, a rough trim, a VIN, or a listing link..."
      : "Describe the car or paste a link…";
  }
  mileageField?.classList.toggle("hidden-panel", bulkMode);
  listingPriceField?.classList.toggle("hidden-panel", bulkMode);
  rebuiltToggleRow?.classList.toggle("hidden-panel", bulkMode);
  setDisabledForField(mileageField, bulkMode);
  setDisabledForField(listingPriceField, bulkMode);
  setDisabledForField(rebuiltToggleRow, bulkMode);
  const mileageInput = document.getElementById("vehicle-mileage");
  if (mileageInput) {
    mileageInput.required = !bulkMode && !zippyMode;
    if (bulkMode) {
      mileageInput.setCustomValidity("");
    }
  }
  setChoiceCardSelection("evaluation-mode", mode);
  setChoiceCardSelection(
    "detailed-report",
    (detailedVehicleReportSelect?.value || "off") === "on" ? "on" : "off",
  );
}

function setLoadingVisible(visible, message = "", title = "", kicker = "") {
  if (!loadingPanel) {
    return;
  }
  loadingPanel.classList.toggle("hidden-panel", !visible);
  if (message && loadingMessage) {
    loadingMessage.textContent = message;
  }
  if (loadingTitle) {
    loadingTitle.textContent = title || "Building comps and pricing";
  }
  if (loadingKicker) {
    loadingKicker.textContent = kicker || "Evaluating the batch";
  }
}

function animatePortfolioSaveCue() {
  favoriteFromMain?.classList.add("is-saved");
  stickyPortfolioButton?.classList.add("portfolio-bump");
  window.setTimeout(() => favoriteFromMain?.classList.remove("is-saved"), 1200);
  window.setTimeout(() => stickyPortfolioButton?.classList.remove("portfolio-bump"), 1200);
}

function setNotes(notes = []) {
  statusNotes.innerHTML = "";
  notes.forEach((note) => {
    const item = document.createElement("li");
    item.textContent = note;
    statusNotes.appendChild(item);
  });
}

function averageListingPrice(resultBody) {
  const comps = Array.isArray(resultBody?.matched_comps) ? resultBody.matched_comps : [];
  const prices = comps
    .map((listing) => parseMoney(listing.price))
    .filter((price) => Number.isFinite(price));

  if (!prices.length) {
    return "";
  }

  const total = prices.reduce((sum, price) => sum + price, 0);
  return formatMoney(total / prices.length);
}

function humanizeKey(value) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatVehicleToken(token) {
  const lower = String(token).toLowerCase();
  const overrides = {
    audi: "Audi",
    bmw: "BMW",
    gmc: "GMC",
    amg: "AMG",
    awd: "AWD",
    rwd: "RWD",
    fwd: "FWD",
    "4wd": "4WD",
    "2wd": "2WD",
    "4x4": "4x4",
    "4x2": "4x2",
    xdrive: "xDrive",
    quattro: "quattro",
    sline: "S-Line",
  };

  if (overrides[lower]) {
    return overrides[lower];
  }

  if (lower.includes("-")) {
    return lower
      .split("-")
      .map((piece) => formatVehicleToken(piece))
      .join("-");
  }

  if (/\d/.test(lower)) {
    return lower.toUpperCase();
  }

  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

function formatVehicleStyleText(value) {
  return String(value)
    .split(/\s+/)
    .filter(Boolean)
    .map((token) => formatVehicleToken(token))
    .join(" ");
}

function formatVehicleValue(key, value) {
  if (!value) {
    return "";
  }

  if (key === "make" || key === "model" || key === "trim") {
    return formatVehicleStyleText(value);
  }

  if (key === "mileage") {
    const digits = String(value).replace(/[^\d]/g, "");
    return digits ? `${Number(digits).toLocaleString()} miles` : String(value);
  }

  if (key === "asking_price") {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? formatMoney(numeric) : String(value);
  }

  if (key === "state") {
    return String(value).toUpperCase();
  }

  if (key === "color") {
    return formatVehicleStyleText(value);
  }

  return String(value);
}

function renderVehicleBrief(details, fallback) {
  const rows = vehicleFields
    .map(([key, label]) => {
      let value = formatVehicleValue(key, details?.[key]);
      if (key === "asking_price" && !value) {
        value = "N/A";
      }
      if (!value) {
        return "";
      }

      return `
        <div class="vehicle-row">
          ${renderLabelWithHelp(label, key)}
          <strong>${escapeHtml(value)}</strong>
        </div>
      `;
    })
    .filter(Boolean);

  if (rows.length === 0) {
    sourceSummary.textContent = fallback || "Vehicle valuation";
    sourceSummary.classList.add("muted");
    return;
  }

  sourceSummary.classList.remove("muted");
  const referenceVehicle = extractReferenceVehicleMedia(currentMainEvaluation);
  const vinRefinementNote = details?.vin_decoded_used
    ? `<div class="vehicle-vin-note">Vehicle details refined using VIN decode.</div>`
    : "";
  sourceSummary.innerHTML = `
    <div class="vehicle-brief">
      ${rows.join("")}
      ${vinRefinementNote}
      ${renderReferenceVehicleCard(referenceVehicle)}
    </div>
  `;
}

function extractReferenceVehicleMedia(evaluation) {
  const matched = Array.isArray(evaluation?.matched_comps) ? evaluation.matched_comps : [];
  for (const listing of matched) {
    const image = Array.isArray(listing?.image_urls)
      ? listing.image_urls.find((value) => /^https?:\/\//.test(String(value || "")))
      : "";
    if (image) {
      return {
        url: image,
        source: listing.source_label || listing.source || "Matched comp",
      };
    }
  }

  const sample = Array.isArray(evaluation?.sample_listings) ? evaluation.sample_listings : [];
  for (const listing of sample) {
    const image = Array.isArray(listing?.image_urls)
      ? listing.image_urls.find((value) => /^https?:\/\//.test(String(value || "")))
      : "";
    if (image) {
      return {
        url: image,
        source: listing.dealer || listing.source_label || "Sample comp",
      };
    }
  }

  return null;
}

function renderReferenceVehicleCard(referenceVehicle) {
  if (!referenceVehicle?.url) {
    return `
      <div class="vehicle-reference-card">
        <div class="vehicle-reference-frame">
          <div class="vehicle-reference-placeholder">
            A matching comp photo was not available for this run, but the evaluation is still complete.
          </div>
        </div>
      </div>
    `;
  }

  return `
    <div class="vehicle-reference-card">
      <div class="vehicle-reference-frame">
        <img src="${escapeHtml(referenceVehicle.url)}" alt="Reference vehicle" loading="lazy" />
      </div>
    </div>
  `;
}

function renderOverallRange(data) {
  if (!data || Object.keys(data).length === 0) {
    overallRange.textContent = "No values yet.";
    overallRange.classList.add("muted");
    return;
  }

  const rangeOrder = [
    "market_value",
    "safe_buy_value",
    "expected_resale_value",
    "estimated_profit",
    "imperfect_title_value",
    "condition_range",
  ];
  const orderedEntries = Object.entries(data).sort(([left], [right]) => {
    const leftIndex = rangeOrder.indexOf(left);
    const rightIndex = rangeOrder.indexOf(right);
    const normalizedLeft = leftIndex === -1 ? Number.MAX_SAFE_INTEGER : leftIndex;
    const normalizedRight = rightIndex === -1 ? Number.MAX_SAFE_INTEGER : rightIndex;
    return normalizedLeft - normalizedRight;
  });

  overallRange.classList.remove("muted");
  overallRange.innerHTML = orderedEntries
    .map(([key, value]) => {
      const formattedValue =
        value && typeof value === "object" && "low" in value && "high" in value
          ? `${value.low} to ${value.high}`
          : String(value || "");
      const isEstimatedProfit = key === "estimated_profit";
      const profitValue = isEstimatedProfit ? parseMoney(formattedValue) : null;
      const strongClass = isEstimatedProfit
        ? (profitValue !== null && profitValue < 0 ? "metric-negative" : "metric-positive")
        : "";

      return `
        <div class="range-row">
          ${renderLabelWithHelp(humanizeKey(key), key)}
          <strong class="${escapeHtml(strongClass)}">${escapeHtml(formattedValue)}</strong>
        </div>
      `;
    })
    .join("");
}

function renderAveragePriceNearMileage(data) {
  if (!overallRange || !data || (!data.value && !data.message)) {
    return;
  }

  const summary = data.value
    ? `${data.value}${data.comps_used ? ` • ${data.comps_used} nearby comps` : ""}`
    : (data.message || "Not enough nearby mileage comps");

  overallRange.insertAdjacentHTML(
    "beforeend",
    `
      <div class="range-row">
        ${renderLabelWithHelp(data.label || "Average Price Near This Mileage", "average_price_near_this_mileage")}
        <strong>${escapeHtml(summary)}</strong>
      </div>
    `,
  );
}

function renderMileagePriceDelta(averageNearMileage, parsedDetails = {}) {
  if (!overallRange || !averageNearMileage?.value) {
    return;
  }

  const listingPrice = Number(parsedDetails?.asking_price);
  const averagePrice = parseMoney(averageNearMileage.value);
  if (!Number.isFinite(listingPrice) || !Number.isFinite(averagePrice)) {
    return;
  }

  const delta = averagePrice - listingPrice;
  const deltaClass = delta < 0 ? "metric-negative" : "metric-positive";

  overallRange.insertAdjacentHTML(
    "beforeend",
    `
      <div class="range-row">
        ${renderLabelWithHelp("Listing Price vs Avg Near Mileage", "listing_price_vs_avg_near_mileage")}
        <strong class="${escapeHtml(deltaClass)}">${escapeHtml(formatMoney(delta))}</strong>
      </div>
    `,
  );
}

function renderTitleImpact(data) {
  if (!titleImpact || !resultsTitleImpactPanel) {
    return;
  }

  if (!data?.active) {
    titleImpact.textContent = "Rebuilt-title pricing adjustments will appear here when applicable.";
    titleImpact.classList.add("muted");
    resultsTitleImpactPanel.classList.add("hidden-panel");
    return;
  }

  titleImpact.classList.remove("muted");
  resultsTitleImpactPanel.classList.remove("hidden-panel");
  titleImpact.innerHTML = `
    <div class="range-row">
      ${renderLabelWithHelp("Clean Title Benchmark")}
      <strong>${escapeHtml(data.clean_title_value || "")}</strong>
    </div>
    <div class="range-row">
      ${renderLabelWithHelp("Clean Title Range")}
      <strong>${escapeHtml(`${data.clean_title_range?.low || ""} to ${data.clean_title_range?.high || ""}`)}</strong>
    </div>
    <div class="range-row">
      ${renderLabelWithHelp("Rebuilt Title Range")}
      <strong>${escapeHtml(`${data.rebuilt_title_range?.low || ""} to ${data.rebuilt_title_range?.high || ""}`)}</strong>
    </div>
    <div class="range-row">
      ${renderLabelWithHelp("Average Rebuilt Value")}
      <strong>${escapeHtml(data.rebuilt_title_average || "")}</strong>
    </div>
    <div class="range-row">
      ${renderLabelWithHelp("Value Difference")}
      <strong>${escapeHtml(`${data.value_difference?.low || ""} to ${data.value_difference?.high || ""}`)}</strong>
    </div>
    <div class="range-row">
      ${renderLabelWithHelp("Average Difference")}
      <strong>${escapeHtml(data.value_difference?.average || "")}</strong>
    </div>
    <div class="range-row">
      ${renderLabelWithHelp("Rebuilt Safe Buy Window")}
      <strong>${escapeHtml(`${data.safe_buy_range?.low || ""} to ${data.safe_buy_range?.high || ""}`)}</strong>
    </div>
    <div class="range-row">
      ${renderLabelWithHelp("Damage Factor")}
      <strong>${escapeHtml(data.damage_factor_range || "")}</strong>
    </div>
  `;
}

function renderListingPriceAnalysis(data) {
  if (!listingPriceAnalysis || !resultsPricingPanel) {
    return;
  }

  if (!data?.active) {
    listingPriceAnalysis.textContent = "Provide a listing price to see how closely it tracks the market estimate.";
    listingPriceAnalysis.classList.add("muted");
    resultsPricingPanel.classList.add("hidden-panel");
    return;
  }

  listingPriceAnalysis.classList.remove("muted");
  resultsPricingPanel.classList.remove("hidden-panel");
  listingPriceAnalysis.innerHTML = `
    <div class="range-row">
      ${renderLabelWithHelp("Provided Price")}
      <strong>${escapeHtml(data.provided_price || "")}</strong>
    </div>
    <div class="range-row">
      ${renderLabelWithHelp("Suggested Target Price")}
      <strong>${escapeHtml(data.recommended_target_price || "")}</strong>
    </div>
    <div class="range-row">
      ${renderLabelWithHelp("Market Value")}
      <strong>${escapeHtml(data.market_value || "")}</strong>
    </div>
    <div class="range-row">
      ${renderLabelWithHelp("Safe Buy Value")}
      <strong>${escapeHtml(data.safe_buy_price || "")}</strong>
    </div>
    <div class="range-row">
      ${renderLabelWithHelp("Expected Resale Value")}
      <strong>${escapeHtml(data.expected_resale || "")}</strong>
    </div>
    <div class="range-row">
      ${renderLabelWithHelp("Market Position")}
      <strong>${escapeHtml(
        [data.position_label || "", data.difference_to_market ? `${data.difference_to_market} • ${data.difference_percent}` : ""]
          .filter(Boolean)
          .join(" • "),
      )}</strong>
    </div>
    <div class="range-row">
      ${renderLabelWithHelp("Estimated Profit At Asking")}
      <strong>${escapeHtml(data.estimated_profit_at_asking || "")}</strong>
    </div>
    <div class="range-row">
      ${renderLabelWithHelp("Negotiation Window")}
      <strong>${escapeHtml(data.negotiation_window || "")}</strong>
    </div>
    <div class="range-row">
      ${renderLabelWithHelp("Takeaway")}
      <strong>${escapeHtml(data.note || "")}</strong>
    </div>
  `;
}

function renderConditionValues(values) {
  if (!values || Object.keys(values).length === 0) {
    conditionValues.textContent = "No condition values were returned.";
    conditionValues.classList.add("muted");
    return;
  }

  conditionValues.classList.remove("muted");
  conditionValues.innerHTML = Object.entries(values)
    .map(([condition, entries]) => {
      const lines = Object.entries(entries)
        .filter(([key]) => !["anchor_price", "pricing_note"].includes(key))
        .map(
          ([key, value]) => `
            <div class="value-line">
              ${renderLabelWithHelp(humanizeKey(key), key)}
              <strong>${escapeHtml(value)}</strong>
            </div>
          `
        )
        .join("");

      return `
        <article class="condition-card">
          <h3>${escapeHtml(condition)}</h3>
          ${lines}
        </article>
      `;
    })
    .join("");
}

function renderMileagePriceBands(bands) {
  if (!mileagePriceBands || !mileageBandSelect || !mileageBandOutput) {
    return;
  }

  if (!bands || bands.length === 0) {
    mileagePriceBands.classList.add("muted");
    mileageBandSelect.innerHTML = `<option>No mileage bands available</option>`;
    mileageBandSelect.disabled = true;
    mileageBandOutput.textContent = "Mileage-based average listing prices will appear here after a valuation run.";
    currentMileageBands = [];
    return;
  }

  currentMileageBands = bands;
  mileagePriceBands.classList.remove("muted");
  mileageBandSelect.disabled = false;
  mileageBandSelect.innerHTML = bands
    .map(
      (band, index) => `<option value="${index}">${escapeHtml(band.label || "")}</option>`,
    )
    .join("");
  mileageBandSelect.value = "0";
  renderSelectedMileageBand(0);
}

function renderSelectedMileageBand(index) {
  if (!mileageBandOutput) {
    return;
  }

  const band = currentMileageBands[index];
  if (!band) {
    mileageBandOutput.textContent = "No mileage band selected.";
    return;
  }

  mileageBandOutput.innerHTML = `
    <div class="mileage-band-summary">
      ${renderLabelWithHelp("Average Listing Price")}
      <strong>${escapeHtml(band.average_price || "")}</strong>
    </div>
    <div class="mileage-band-summary">
      ${renderLabelWithHelp("Comparable Listings Used")}
      <strong>${escapeHtml(`${band.count} comp${band.count === 1 ? "" : "s"}`)}</strong>
    </div>
    <div class="mileage-band-summary">
      ${renderLabelWithHelp("Selected Mileage Range")}
      <strong>${escapeHtml(band.label || "")}</strong>
    </div>
  `;
}

function renderBulkSummary(summary = {}) {
  if (!bulkResultsSummary) {
    return;
  }
  const cards = [
    ["Pasted Vehicles", summary.total_entries || 0],
    ["Parsed Vehicles", summary.parsed_entries || 0],
    ["Evaluated Vehicles", summary.evaluated_entries || 0],
    ["Skipped / Failed", (summary.skipped_entries || 0) + (summary.failed_entries || 0)],
  ];
  bulkResultsSummary.classList.remove("muted");
  bulkResultsSummary.innerHTML = cards.map(([label, value]) => `
      <article class="bulk-summary-card">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(String(value))}</strong>
      </article>
    `).join("");
}

function renderDetailedReport(report) {
  if (!detailedVehicleReportOutput || !resultsDetailedReportPanel) {
    return;
  }

  if (!report?.requested) {
    detailedVehicleReportOutput.textContent = "Enable Detailed Vehicle Report to generate specs, reliability, ownership, and performance context.";
    detailedVehicleReportOutput.classList.add("muted");
    resultsDetailedReportPanel.classList.add("hidden-panel");
    return;
  }

  const sections = Array.isArray(report.sections)
    ? report.sections.filter((section) => Array.isArray(section.items) && section.items.length)
    : [];

  if (!sections.length) {
    detailedVehicleReportOutput.textContent = "Detailed report data is limited for this vehicle, but the main evaluation is still complete.";
    detailedVehicleReportOutput.classList.add("muted");
    resultsDetailedReportPanel.classList.remove("hidden-panel");
    return;
  }

  detailedVehicleReportOutput.classList.remove("muted");
  resultsDetailedReportPanel.classList.remove("hidden-panel");
  detailedVehicleReportOutput.innerHTML = sections.map((section) => `
      <article class="detailed-report-section">
        <h3>${escapeHtml(section.title || "Section")}</h3>
        <div class="detailed-report-items">
          ${(section.items || []).map((item) => `
            <div class="range-row">
              ${renderLabelWithHelp(item.label || "")}
              <strong>${escapeHtml(item.value || "")}</strong>
            </div>
          `).join("")}
        </div>
      </article>
    `).join("");
}

function renderCompactDetailedReport(report) {
  if (!report?.requested) {
    return "";
  }

  const compact = Array.isArray(report.compact_summary)
    ? report.compact_summary.filter((item) => item?.label && item?.value)
    : [];
  const sections = Array.isArray(report.sections)
    ? report.sections.filter((section) => Array.isArray(section.items) && section.items.length)
    : [];

  if (!compact.length && !sections.length) {
    return `
      <div class="bulk-report-empty muted">
        Detailed report data is limited for this vehicle.
      </div>
    `;
  }

  return `
    <details class="bulk-report-details">
      <summary>Detailed Vehicle Report</summary>
      ${compact.length ? `
        <div class="bulk-report-summary">
          ${compact.map((item) => `
            <div class="listing-meta-line">
              <span>${escapeHtml(item.label)}</span>
              <strong>${escapeHtml(item.value)}</strong>
            </div>
          `).join("")}
        </div>
      ` : ""}
      ${sections.map((section) => `
        <div class="bulk-report-section">
          <strong>${escapeHtml(section.title || "Section")}</strong>
          <div class="bulk-report-section-items">
            ${(section.items || []).map((item) => `
              <div class="listing-meta-line">
                <span>${escapeHtml(item.label || "")}</span>
                <strong>${escapeHtml(item.value || "")}</strong>
              </div>
            `).join("")}
          </div>
        </div>
      `).join("")}
    </details>
  `;
}

function bulkStatusClass(status) {
  if (status === "complete") {
    return "bulk-status-complete";
  }
  if (status === "skipped") {
    return "bulk-status-skipped";
  }
  return "bulk-status-failed";
}

function renderBulkResults(items = []) {
  if (!bulkResultsGrid) {
    return;
  }
  if (!Array.isArray(items) || items.length === 0) {
    bulkResultsGrid.textContent = "No bulk evaluation results were returned.";
    bulkResultsGrid.classList.add("muted");
    return;
  }

  bulkResultsGrid.classList.remove("muted");
  bulkResultsGrid.innerHTML = items.map((item) => {
    const status = String(item.status || "failed");
    const rank = item.rank ? `#${item.rank}` : status.toUpperCase();
    const estimatedProfitValue = parseMoney(item.estimated_profit);
    const keyFacts = [
      ["Listed Price", item.listed_price || ""],
      ["Market Value", item.market_value || ""],
      ["Safe Buy Value", item.safe_buy_value || ""],
      ["Expected Resale", item.expected_resale_value || ""],
      ["Estimated Profit", item.estimated_profit || ""],
      ["Confidence", item.confidence || ""],
      ["Risk", item.risk || ""],
      ["Comp Count", item.comp_count ? String(item.comp_count) : ""],
      ["Location", item.location || ""],
    ].filter(([, value]) => value);

    const strongStatusClass = bulkStatusClass(status);
    const profitClass = parseMoney(item.estimated_profit) >= 0 ? "metric-positive" : "metric-negative";
    const detailedReportMarkup = renderCompactDetailedReport(item.detailed_vehicle_report);
    return `
      <article class="listing-card bulk-result-card ${escapeHtml(strongStatusClass)}">
        <div class="listing-card-head bulk-card-head">
          <div>
            <strong class="listing-card-title">${escapeHtml(item.vehicle_name || "Unparsed vehicle")}</strong>
            <span class="listing-card-hover">${escapeHtml(
              status === "complete" ? `Rank ${rank}` : `${status.charAt(0).toUpperCase()}${status.slice(1)}`
            )}</span>
          </div>
          <div class="listing-price-badge bulk-rank-badge">
            <span class="listing-price-label">Rank</span>
            <span class="listing-price">${escapeHtml(rank)}</span>
          </div>
        </div>
        <div class="listing-meta bulk-result-meta">
          ${keyFacts.map(([label, value]) => `
            <div class="listing-meta-line">
              <span>${escapeHtml(label)}</span>
              <strong class="${escapeHtml(label === "Estimated Profit" && estimatedProfitValue !== null ? profitClass : "")}">${escapeHtml(value)}</strong>
            </div>
          `).join("")}
          ${item.reason ? `
            <div class="listing-meta-line bulk-reason-line">
              <span>Reason</span>
              <strong>${escapeHtml(item.reason)}</strong>
            </div>
          ` : ""}
        </div>
        ${detailedReportMarkup}
      </article>
    `;
  }).join("");
}

function normalizeComparableListing(listing) {
  if (!listing) {
    return null;
  }

  const title =
    listing.title ||
    [listing.year, listing.make, listing.model, listing.trim].filter(Boolean).join(" ").trim() ||
    "Comparable listing";
  const miles =
    listing.miles ||
    (listing.mileage ? `${Number(listing.mileage).toLocaleString()} mi` : "");

  return {
    title,
    price: listing.price || "",
    miles,
    mileageValue: listing.mileage ? Number(listing.mileage) : parseMoney(String(miles).replace(/[^\d]/g, "")),
    trim: listing.trim || "",
    dealer: listing.dealer || listing.source_label || listing.source || "",
    sourceUrl: listing.source_url || listing.url || "",
    url: listing.url || "",
    originalIndex: typeof listing.originalIndex === "number" ? listing.originalIndex : 0,
  };
}

function updateCompsToolbar(totalCount, visibleCount) {
  if (!compsToolbar || !compsCountLabel || !showAllCompsButton) {
    return;
  }

  if (!totalCount) {
    compsToolbar.classList.add("hidden-panel");
    showAllCompsButton.classList.add("hidden-panel");
    compsCountLabel.textContent = "Showing 0 of 0 comps";
    return;
  }

  compsToolbar.classList.remove("hidden-panel");
  compsCountLabel.textContent = `Showing ${visibleCount} of ${totalCount} comps`;

  if (totalCount <= DEFAULT_VISIBLE_COMPS) {
    showAllCompsButton.classList.add("hidden-panel");
    return;
  }

  showAllCompsButton.classList.remove("hidden-panel");
  showAllCompsButton.textContent = showingAllComparableListings
    ? "Show Less"
    : `Show All ${totalCount} Comps`;
}

function renderSampleListings(listings) {
  if (!listings || listings.length === 0) {
    sampleListings.textContent = "No comparable listings were returned.";
    sampleListings.classList.add("muted");
    updateCompsToolbar(0, 0);
    return;
  }

  const targetMileage = Number(currentMainEvaluation?.parsed_details?.mileage || 0) || null;
  const sortedListings = [...listings].sort((left, right) => {
    if (currentCompSort === "price_low") {
      return (parseMoney(left.price) || Number.MAX_SAFE_INTEGER) - (parseMoney(right.price) || Number.MAX_SAFE_INTEGER);
    }
    if (currentCompSort === "price_high") {
      return (parseMoney(right.price) || 0) - (parseMoney(left.price) || 0);
    }
    if (currentCompSort === "closest_mileage" && targetMileage) {
      const leftMileage = Number.isFinite(left.mileageValue) ? left.mileageValue : Number.MAX_SAFE_INTEGER;
      const rightMileage = Number.isFinite(right.mileageValue) ? right.mileageValue : Number.MAX_SAFE_INTEGER;
      const leftDelta = Math.abs(leftMileage - targetMileage);
      const rightDelta = Math.abs(rightMileage - targetMileage);
      if (leftDelta !== rightDelta) {
        return leftDelta - rightDelta;
      }
    }
    if (currentCompSort === "mileage_low") {
      const leftMileage = Number.isFinite(left.mileageValue) ? left.mileageValue : Number.MAX_SAFE_INTEGER;
      const rightMileage = Number.isFinite(right.mileageValue) ? right.mileageValue : Number.MAX_SAFE_INTEGER;
      if (leftMileage !== rightMileage) {
        return leftMileage - rightMileage;
      }
    }
    if (currentCompSort === "mileage_high") {
      const leftMileage = Number.isFinite(left.mileageValue) ? left.mileageValue : -1;
      const rightMileage = Number.isFinite(right.mileageValue) ? right.mileageValue : -1;
      if (leftMileage !== rightMileage) {
        return rightMileage - leftMileage;
      }
    }
    return (left.originalIndex || 0) - (right.originalIndex || 0);
  });

  const visibleListings = showingAllComparableListings
    ? sortedListings
    : sortedListings.slice(0, DEFAULT_VISIBLE_COMPS);

  sampleListings.classList.remove("muted");
  sampleListings.innerHTML = visibleListings
    .map((listing) => {
      const safeUrl =
        typeof listing.url === "string" && /^https?:\/\//.test(listing.url)
          ? listing.url
          : "";
      const safeTitle = escapeHtml(listing.title || "Comparable listing");

      const meta = [
        listing.trim
          ? `
            <div class="listing-meta-line">
              <span>Trim</span>
              <strong>${escapeHtml(formatVehicleStyleText(listing.trim))}</strong>
            </div>
          `
          : "",
        listing.miles
          ? `
            <div class="listing-meta-line">
              <span>Mileage</span>
              <strong>${escapeHtml(listing.miles)}</strong>
            </div>
          `
          : "",
        listing.dealer
          ? `
            <div class="listing-meta-line">
              <span>Source</span>
              <strong>${escapeHtml(listing.dealer || "")}</strong>
            </div>
          `
          : "",
      ]
        .filter(Boolean)
        .join("");

      const cardInner = `
          <div class="listing-card-head">
            <div>
              <strong class="listing-card-title">${safeTitle}</strong>
              <span class="listing-card-hover">Open listing</span>
            </div>
            <div class="listing-price-badge">
              <span class="listing-price-label">Price</span>
              <span class="listing-price">${escapeHtml(listing.price || "")}</span>
            </div>
          </div>
          <div class="listing-meta">
            ${meta}
          </div>
      `;

      if (safeUrl) {
        return `
          <a class="listing-card listing-card-link" href="${escapeHtml(safeUrl)}" target="_blank" rel="noreferrer" aria-label="${safeTitle}">
            ${cardInner}
          </a>
        `;
      }

      return `
        <article class="listing-card">
          ${cardInner}
        </article>
      `;
    })
    .join("");

  updateCompsToolbar(listings.length, visibleListings.length);
}

function setComparableListings(sample = [], matched = []) {
  const normalizedMatched = Array.isArray(matched)
    ? matched.map((listing, index) => normalizeComparableListing({ ...listing, originalIndex: index })).filter(Boolean)
    : [];
  const normalizedSample = Array.isArray(sample)
    ? sample.map((listing, index) => normalizeComparableListing({ ...listing, originalIndex: index })).filter(Boolean)
    : [];

  currentComparableListings = normalizedMatched.length ? normalizedMatched : normalizedSample;
  renderSampleListings(currentComparableListings);
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

function formatResaleValue(range = {}) {
  if (!range?.low || !range?.high) {
    return "";
  }
  return range.low === range.high ? range.low : `${range.low} - ${range.high}`;
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

function updateDealPreview(resultBody) {
  if (
    !previewMarketValue
    || !previewSafeBuy
    || !previewExpectedResale
    || !previewEstimatedProfit
    || !previewConfidence
    || !previewRisk
  ) {
    return;
  }
  const overallRangeData = resultBody?.overall_range || {};
  const adjustedEstimate = resultBody?.adjusted_price_estimate || {};
  const recommendedBuy = resultBody?.recommended_max_buy_price || "";
  const resaleRange = resultBody?.recommended_target_resale_range || {};
  const confidence = Number(resultBody?.confidence_score || 0);

  const marketValue =
    overallRangeData.market_value ||
    adjustedEstimate.weighted_median ||
    (overallRangeData.condition_range
      ? `${overallRangeData.condition_range.low} to ${overallRangeData.condition_range.high}`
      : "$14,200");
  const safeBuy = recommendedBuy || overallRangeData.safe_buy_value || "$10,800";
  const expectedResale = formatResaleValue(resaleRange) || overallRangeData.expected_resale_value || "$13,800";

  let profitText = resultBody?.gross_spread_estimate || "$2,200";
  const safeBuyNumber = parseMoney(safeBuy);
  const resaleValueNumber = parseMoney(resaleRange.low || overallRangeData.expected_resale_value);
  if (!resultBody?.gross_spread_estimate && safeBuyNumber !== null && resaleValueNumber !== null) {
    profitText = formatMoney(Math.max(0, resaleValueNumber - safeBuyNumber));
  }

  previewMarketValue.textContent = marketValue;
  previewSafeBuy.textContent = safeBuy;
  previewExpectedResale.textContent = expectedResale;
  previewEstimatedProfit.textContent = profitText;
  previewConfidence.textContent = confidence ? `${confidence}%` : "82%";
  previewRisk.textContent = riskLabelFromConfidence(confidence);
}

function updateFullEvaluationLink(payload) {
  const vehicleInput = String(payload?.vehicle_input || "").trim();
  const rebuiltTitle = String(payload?.rebuilt_title || "").trim();
  const mileage = String(payload?.mileage || "").trim();
  if (!vehicleInput) {
    fullEvaluationLink.href = "/full-evaluation";
    return;
  }

  const target = new URL("/full-evaluation", window.location.origin);
  target.searchParams.set("vehicle_input", vehicleInput);
  if (mileage) {
    target.searchParams.set("mileage", mileage);
  }
  if (rebuiltTitle) {
    target.searchParams.set("rebuilt_title", rebuiltTitle);
  }
  fullEvaluationLink.href = target.toString();
}

function buildStatusMessage(result) {
  if (result.body?.mode === "bulk") {
    return result.body.message || "Bulk evaluation complete.";
  }
  if (result.body?.mode === "zippy") {
    const count = result.body.comparable_count || 0;
    return count
      ? `Zippy scraped ${count} priced comps and generated the quick market values.`
      : (result.body.message || "Zippy run complete.");
  }
  const count = result.body.comparable_count || 0;
  const averagePrice = averageListingPrice(result.body);
  if (count && averagePrice) {
    return `Found ${count} comparable listings. Total average listing price: ${averagePrice}.`;
  }
  if (count) {
    return `Found ${count} comparable listings.`;
  }
  return result.body.message || `Processed your input with ${result.body.provider}.`;
}

function buildNotes(result) {
  return [];
}

function renderZippyResult(resultBody) {
  setResultsVisible(true);
  resultsConditionsPanel?.classList.add("hidden-panel");
  resultsTitleImpactPanel?.classList.add("hidden-panel");
  resultsPricingPanel?.classList.add("hidden-panel");
  resultsDetailedReportPanel?.classList.add("hidden-panel");
  dealTransitionPanel?.classList.add("hidden-panel");
  renderVehicleBrief(resultBody.parsed_details, resultBody.vehicle_summary);
  renderConditionValues(null);
  renderMileagePriceBands(null);
  const values = resultBody.values || {};
  const zippyRange = {
    average_price_of_all_comps: values.average_all_comps || "",
    average_price_of_20_closest_mileage_comps: values.average_20_closest_mileage_comps || values.average_all_comps || "",
    very_poor_buy_price: values.very_poor_buy_price || "",
    good_buy_price: values.good_buy_price || "",
    excellent_buy_price: values.excellent_buy_price || "",
  };
  renderOverallRange(zippyRange);
  renderAveragePriceNearMileage(null);
  renderMileagePriceDelta(null, null);
  renderTitleImpact(null);
  renderListingPriceAnalysis(null);
  renderDetailedReport(null);
  showingAllComparableListings = false;
  setComparableListings([], resultBody.matched_comps || []);
}

async function postJson(url, payload = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return {
    status: response.status,
    body: await response.json(),
  };
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

function cleanVehicleTitle(parsedDetails = {}, fallback = "") {
  const base = [
    parsedDetails.year,
    parsedDetails.make,
    parsedDetails.model,
    cleanTrim(parsedDetails.trim),
  ].filter(Boolean).join(" ").trim();
  return base || fallback || "Saved Evaluation";
}

function startLoadingProgress() {
  const progressLabel = document.getElementById("loading-progress");
  loadingProgressValue = 6;
  let phaseIndex = 0;
  if (progressLabel) {
    progressLabel.textContent = `Approximately ${loadingProgressValue}%`;
  }
  if (loadingMessage) {
    loadingMessage.textContent = loadingPhases[0];
  }
  if (loadingProgressTimer) {
    window.clearInterval(loadingProgressTimer);
  }
  if (loadingMessageTimer) {
    window.clearInterval(loadingMessageTimer);
  }
  loadingProgressTimer = window.setInterval(() => {
    loadingProgressValue = Math.min(92, loadingProgressValue + (loadingProgressValue < 40 ? 9 : loadingProgressValue < 70 ? 5 : 2));
    if (progressLabel) {
      progressLabel.textContent = `Approximately ${loadingProgressValue}%`;
    }
  }, 650);
  loadingMessageTimer = window.setInterval(() => {
    phaseIndex = (phaseIndex + 1) % loadingPhases.length;
    if (loadingMessage) {
      loadingMessage.textContent = loadingPhases[phaseIndex];
    }
  }, 1500);
}

function stopLoadingProgress() {
  const progressLabel = document.getElementById("loading-progress");
  if (loadingProgressTimer) {
    window.clearInterval(loadingProgressTimer);
    loadingProgressTimer = null;
  }
  if (loadingMessageTimer) {
    window.clearInterval(loadingMessageTimer);
    loadingMessageTimer = null;
  }
  if (progressLabel) {
    progressLabel.textContent = "Approximately 100%";
  }
}

function initBillingToggle() {
  const toggle = document.getElementById("billing-toggle");
  if (!toggle) {
    return;
  }
  const buttons = Array.from(toggle.querySelectorAll(".billing-choice"));
  const applyBilling = (mode) => {
    buttons.forEach((button) => {
      button.classList.toggle("is-active", button.dataset.billing === mode);
    });
    document.querySelectorAll("[data-price-monthly]").forEach((node) => {
      const price = mode === "yearly" ? node.getAttribute("data-price-yearly") : node.getAttribute("data-price-monthly");
      node.textContent = price || "";
    });
    document.querySelectorAll(".subscription-price span").forEach((node) => {
      node.textContent = mode === "yearly" ? "/ year" : "/ month";
    });
  };
  toggle.addEventListener("click", (event) => {
    const button = event.target.closest(".billing-choice");
    if (!button) {
      return;
    }
    applyBilling(button.dataset.billing || "monthly");
  });
  applyBilling("monthly");
}

function initSubscriptionSelection() {
  const grid = document.getElementById("subscriptions-grid");
  if (!grid) {
    return;
  }
  grid.addEventListener("click", async (event) => {
    const button = event.target.closest(".subscription-select-button");
    if (!button) {
      return;
    }
    const card = button.closest("[data-tier]");
    const inlineStatus = card?.querySelector(".subscription-inline-status");
    const tier = Number(button.dataset.tier || card?.dataset.tier || 0);
    if (!tier) {
      return;
    }
    button.disabled = true;
    if (inlineStatus) {
      inlineStatus.textContent = "Updating access...";
    }
    try {
      const response = await fetch("/api/account/subscription-select", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tier }),
      });
      const payload = await response.json();
      if (!payload.ok) {
        throw new Error(payload.message || "Unable to update access.");
      }
      renderAccountStatus(payload.account_status);
      if (inlineStatus) {
        inlineStatus.textContent = payload.message || "Access updated.";
      }
    } catch (error) {
      if (inlineStatus) {
        inlineStatus.textContent = error instanceof Error ? error.message : "Request failed.";
      }
    } finally {
      button.disabled = false;
    }
  });
}

async function saveMainEvaluationToPortfolio() {
  if (!currentMainEvaluation) {
    return;
  }
  mainFavoriteStatus.textContent = "Saving evaluation...";
  const vehicleTitle = cleanVehicleTitle(currentMainEvaluation.parsed_details, currentMainEvaluation.vehicle_summary);
  const payload = {
    vehicle_title: vehicleTitle,
    vehicle_input: currentMainEvaluation.parsed_details?.vehicle_input || "",
    preview: {
      comparable_count: `${currentMainEvaluation.comparable_count || 0} comps`,
      final_buy_price: "",
      suggested_buy_price: currentMainEvaluation.recommended_max_buy_price || "",
      average_price_near_mileage: currentMainEvaluation.average_price_near_mileage?.value
        || currentMainEvaluation.average_price_near_mileage?.message
        || "",
      expected_resale_range: formatResaleValue(currentMainEvaluation.recommended_target_resale_range) || "",
      confidence: `${Number(currentMainEvaluation.confidence_score || 0)}%`,
      risk: riskLabelFromConfidence(Number(currentMainEvaluation.confidence_score || 0)),
    },
    snapshot: {
      front_evaluation: currentMainEvaluation,
      full_evaluation: {
        final_buy_price: "",
        suggested_buy_price: currentMainEvaluation.recommended_max_buy_price || "",
        average_price_near_mileage: currentMainEvaluation.average_price_near_mileage?.value
          || currentMainEvaluation.average_price_near_mileage?.message
          || "",
        expected_resale_range: formatResaleValue(currentMainEvaluation.recommended_target_resale_range) || "",
        confidence: `${Number(currentMainEvaluation.confidence_score || 0)}%`,
        risk: riskLabelFromConfidence(Number(currentMainEvaluation.confidence_score || 0)),
        comparable_count: currentMainEvaluation.comparable_count || 0,
        profit_table: [],
      },
    },
  };
  try {
    const result = await postJson("/api/portfolio", payload);
    if (!result.body.ok) {
      throw new Error(result.body.message || "Unable to save evaluation.");
    }
    mainFavoriteStatus.textContent = "Saved to Evaluation Portfolio.";
    animatePortfolioSaveCue();
  } catch (error) {
    mainFavoriteStatus.textContent = error.message;
  }
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const mileageInput = document.getElementById("vehicle-mileage");
  const mode = selectedEvaluationMode();
  const bulkMode = mode === "bulk";
  const zippyMode = mode === "zippy";
  if (mileageInput) {
    mileageInput.setCustomValidity("");
  }
  if (!bulkMode && !form.reportValidity()) {
    if (!zippyMode && mileageInput && !String(mileageInput.value || "").trim()) {
      mileageInput.setCustomValidity("Mileage is required to run the evaluation.");
      mileageInput.reportValidity();
    }
    return;
  }
  if (bulkMode && !String(vehicleInput?.value || "").trim()) {
    vehicleInput?.setCustomValidity("Paste the cars you want evaluated.");
    vehicleInput?.reportValidity();
    return;
  }
  vehicleInput?.setCustomValidity("");
  const submitButton = form.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  hideAllResultPanels();
  setLoadingVisible(
    true,
    bulkMode
      ? "Parsing vehicles, evaluating each one, and ranking the best deals in the batch."
      : zippyMode
        ? "Scraping live comps, averaging the market, and generating the fast buy values."
      : "Building comps, checking pricing, and calculating your potential deal.",
    bulkMode ? "Ranking the strongest deals" : zippyMode ? "Running Zippy" : "Building comps and pricing",
    bulkMode ? "Evaluating the batch" : zippyMode ? "Evaluating the deal" : "Evaluating the deal",
  );
  startLoadingProgress();
  sessionBadge.textContent = "Running";
  statusMessage.textContent = bulkMode ? "Running bulk evaluation..." : "Running background valuation...";

  const payload = {
    ...Object.fromEntries(new FormData(form).entries()),
    force_refresh: true,
  };
  if (!bulkMode) {
    updateFullEvaluationLink(payload);
  }
  try {
    const result = await postJson("/api/valuation", payload);
    renderAccountStatus(result.body?.account_status);
    if (!result.body.ok) {
      currentMainEvaluation = null;
      setLoadingVisible(false);
      stopLoadingProgress();
      showStatusOnly(result.body.message || "Valuation failed.", "Error");
      setNotes([]);
      sourceSummary.textContent = "No valuation run yet.";
      sourceSummary.classList.add("muted");
      renderConditionValues(null);
      renderMileagePriceBands(null);
      renderOverallRange(null);
      renderAveragePriceNearMileage(null);
      renderMileagePriceDelta(null, null);
      renderTitleImpact(null);
      renderListingPriceAnalysis(null);
      renderDetailedReport(null);
      currentComparableListings = [];
      showingAllComparableListings = false;
      renderSampleListings(null);
      renderBulkSummary({});
      renderBulkResults([]);
      return;
    }

    if (result.body.mode === "bulk") {
      currentMainEvaluation = null;
      setLoadingVisible(false);
      stopLoadingProgress();
      setResultsVisible(false);
      setBulkResultsVisible(true);
      sessionBadge.textContent = `${result.body.summary?.evaluated_entries || 0} evaluated`;
      statusMessage.textContent = buildStatusMessage(result);
      setNotes([]);
      renderBulkSummary(result.body.summary || {});
      renderBulkResults(result.body.items || []);
      currentComparableListings = [];
      showingAllComparableListings = false;
      renderSampleListings(null);
      renderConditionValues(null);
      renderOverallRange(null);
      renderAveragePriceNearMileage(null);
      renderMileagePriceDelta(null, null);
      renderTitleImpact(null);
      renderListingPriceAnalysis(null);
      renderDetailedReport(null);
      return;
    }

    if (result.body.mode === "zippy") {
      currentMainEvaluation = result.body;
      setLoadingVisible(false);
      stopLoadingProgress();
      sessionBadge.textContent = `${result.body.comparable_count || 0} comps`;
      statusMessage.textContent = buildStatusMessage(result);
      setNotes([]);
      renderZippyResult(result.body);
      if (composerPanel) {
        composerPanel.classList.add("hidden-panel");
      }
      window.requestAnimationFrame(() => {
        const top = (resultsStatusPanel?.getBoundingClientRect().top || 0) + window.scrollY - 72;
        window.scrollTo({ top, behavior: "smooth" });
      });
      return;
    }

    if (result.body.status !== "complete") {
      currentMainEvaluation = null;
      setLoadingVisible(false);
      stopLoadingProgress();
      showStatusOnly(
        result.body.message || "Please make sure you include the year, make, and model so the engine knows what to evaluate.",
        "Needs Data",
      );
      setNotes([]);
      renderConditionValues(null);
      renderMileagePriceBands(null);
      renderOverallRange(null);
      renderAveragePriceNearMileage(result.body.average_price_near_mileage);
      renderMileagePriceDelta(result.body.average_price_near_mileage, result.body.parsed_details);
      renderTitleImpact(null);
      renderListingPriceAnalysis(result.body.listing_price_analysis);
      renderDetailedReport(result.body.detailed_vehicle_report);
      currentComparableListings = [];
      showingAllComparableListings = false;
      renderSampleListings(null);
      return;
    }

    setLoadingVisible(false);
    stopLoadingProgress();
    setResultsVisible(true);
    currentMainEvaluation = result.body;
    const comparableCount = result.body.comparable_count || 0;
    sessionBadge.textContent =
      comparableCount > 0
        ? `${comparableCount} comps`
        : result.body.status === "complete"
          ? "Complete"
          : "Needs data";
    statusMessage.textContent = buildStatusMessage(result);
    setNotes(buildNotes(result));
    renderVehicleBrief(result.body.parsed_details, result.body.vehicle_summary);
    renderConditionValues(result.body.values);
    renderMileagePriceBands(result.body.mileage_price_bands);
    renderOverallRange(result.body.overall_range);
    renderAveragePriceNearMileage(result.body.average_price_near_mileage);
    renderMileagePriceDelta(result.body.average_price_near_mileage, result.body.parsed_details);
    renderTitleImpact(result.body.title_adjustment);
    renderListingPriceAnalysis(result.body.listing_price_analysis);
    renderDetailedReport(result.body.detailed_vehicle_report);
    showingAllComparableListings = false;
    setComparableListings(result.body.sample_listings, result.body.matched_comps);
    updateDealPreview(result.body);
    cacheEvaluationResult(payload, result.body);
    if (composerPanel) {
      composerPanel.classList.add("hidden-panel");
    }
    if (mainFavoriteStatus) {
      mainFavoriteStatus.textContent = "";
    }
    window.requestAnimationFrame(() => {
      const top = (resultsStatusPanel?.getBoundingClientRect().top || 0) + window.scrollY - 72;
      window.scrollTo({ top, behavior: "smooth" });
    });
  } catch (error) {
    currentMainEvaluation = null;
    setLoadingVisible(false);
    stopLoadingProgress();
    showStatusOnly(`Valuation failed: ${error.message}`, "Error");
    renderDetailedReport(null);
  } finally {
    submitButton.disabled = false;
  }
});

if (showAllCompsButton) {
  showAllCompsButton.addEventListener("click", () => {
    showingAllComparableListings = !showingAllComparableListings;
    renderSampleListings(currentComparableListings);
  });
}

if (mileageBandSelect) {
  mileageBandSelect.addEventListener("change", (event) => {
    renderSelectedMileageBand(Number(event.target.value || 0));
  });
}

document.addEventListener("click", (event) => {
  const clickedButton = event.target.closest(".stat-help-button");
  document.querySelectorAll(".stat-help-button.is-open").forEach((button) => {
    if (button !== clickedButton) {
      button.classList.remove("is-open");
    }
  });
  if (clickedButton) {
    clickedButton.classList.toggle("is-open");
  }
});

if (compSortSelect) {
  compSortSelect.addEventListener("change", (event) => {
    currentCompSort = event.target.value || "closest_mileage";
    renderSampleListings(currentComparableListings);
  });
}

initBillingToggle();
initSubscriptionSelection();

favoriteFromMain?.addEventListener("click", saveMainEvaluationToPortfolio);
evaluationModeCards?.addEventListener("click", (event) => {
  const card = event.target.closest('[data-choice-group="evaluation-mode"]');
  if (!card || !evaluationModeSelect) {
    return;
  }
  if (card.classList.contains("is-locked")) {
    window.alert(card.getAttribute("data-lock-message") || "Your subscription level does not qualify for this model.");
    return;
  }
  evaluationModeSelect.value = card.getAttribute("data-value") || "zippy";
  updateEvaluationModeUI();
  hideAllResultPanels();
  currentMainEvaluation = null;
});

detailedReportCard?.addEventListener("click", () => {
  if (!detailedVehicleReportSelect) {
    return;
  }
  if (detailedReportCard.classList.contains("is-locked")) {
    window.alert(detailedReportCard.getAttribute("data-lock-message") || "Your subscription level does not qualify for juicy add-ons yet.");
    return;
  }
  detailedVehicleReportSelect.value = detailedVehicleReportSelect.value === "on" ? "off" : "on";
  setChoiceCardSelection("detailed-report", detailedVehicleReportSelect.value);
});

evaluationModeSelect?.addEventListener("change", () => {
  updateEvaluationModeUI();
  hideAllResultPanels();
  currentMainEvaluation = null;
});

if (form) {
  updateEvaluationModeUI();
  updateFullEvaluationLink({});
  hideAllResultPanels();
  setLoadingVisible(false);
}
