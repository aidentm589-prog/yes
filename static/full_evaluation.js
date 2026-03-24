const finalBuyPriceInput = document.getElementById("final-buy-price");
const fullEvaluationVehicle = document.getElementById("full-evaluation-vehicle");
const fullEvaluationLoading = document.getElementById("full-evaluation-loading");
const suggestedBuyPrice = document.getElementById("suggested-buy-price");
const autoFinalBuyPriceButton = document.getElementById("auto-final-buy-price-button");
const autoFinalBuyPriceStatus = document.getElementById("auto-final-buy-price-status");
const expectedResaleRange = document.getElementById("expected-resale-range");
const evaluationConfidence = document.getElementById("evaluation-confidence");
const evaluationRisk = document.getElementById("evaluation-risk");
const fullEvaluationTitleImpact = document.getElementById("full-evaluation-title-impact");
const profitTableBody = document.getElementById("profit-table-body");
const favoriteEvaluationButton = document.getElementById("favorite-evaluation-button");
const favoriteEvaluationStatus = document.getElementById("favorite-evaluation-status");
const accountStatusPill = document.querySelector(".account-status-pill");
const topbarCreditValue = document.getElementById("topbar-credit-value");
const topbarTierLabel = document.getElementById("topbar-tier-label");
const topbarTierDefault = document.getElementById("topbar-tier-default");
const topbarTierHover = document.getElementById("topbar-tier-hover");
const EVALUATION_CACHE_KEY = "car-flip-analyzer:latest-evaluation";

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

let currentEvaluation = null;
let currentSafeBuyPrice = null;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderAccountStatus(status) {
  if (!status) {
    return;
  }
  if (accountStatusPill) {
    accountStatusPill.innerHTML = `
      <span>Account</span>
      <strong><a href="/account">${escapeHtml(status.first_name || "Account")}</a></strong>
    `;
  }
  if (topbarCreditValue) {
    topbarCreditValue.textContent = status.is_unlimited ? "Unlimited" : `${Number(status.credit_balance || 0)}`;
  }
  if (topbarTierLabel) {
    topbarTierLabel.textContent = status.tier_label || "Guest Access";
  }
  if (topbarTierDefault) {
    topbarTierDefault.textContent = "Current subscription access";
  }
  if (topbarTierHover) {
    topbarTierHover.textContent = tierHoverCopy(status);
  }
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

function buildEvaluationCacheFingerprint(vehicleInput, mileage, rebuiltTitle) {
  return JSON.stringify({
    vehicle_input: String(vehicleInput || "").trim().toLowerCase(),
    mileage: String(mileage || "").trim(),
    rebuilt_title: String(rebuiltTitle || "").trim().toLowerCase(),
  });
}

function readCachedEvaluation(vehicleInput, mileage, rebuiltTitle) {
  try {
    const cachedRaw = window.sessionStorage.getItem(EVALUATION_CACHE_KEY);
    if (!cachedRaw) {
      return null;
    }
    const cached = JSON.parse(cachedRaw);
    if (!cached?.payload || cached.payload.status !== "complete") {
      return null;
    }
    if (Date.now() - Number(cached.saved_at || 0) > 15 * 60 * 1000) {
      return null;
    }
    const expected = buildEvaluationCacheFingerprint(vehicleInput, mileage, rebuiltTitle);
    return cached.fingerprint === expected ? cached.payload : null;
  } catch (error) {
    console.warn("Unable to read cached evaluation.", error);
    return null;
  }
}

function cacheEvaluationPayload(vehicleInput, mileage, rebuiltTitle, payload) {
  try {
    if (!payload || payload.status !== "complete") {
      return;
    }
    window.sessionStorage.setItem(
      EVALUATION_CACHE_KEY,
      JSON.stringify({
        fingerprint: buildEvaluationCacheFingerprint(vehicleInput, mileage, rebuiltTitle),
        saved_at: Date.now(),
        payload,
      }),
    );
  } catch (error) {
    console.warn("Unable to cache full evaluation payload.", error);
  }
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

function setAutoFinalBuyPriceFromSafeBuy() {
  runFinalBuyCalculation().catch((error) => {
    if (autoFinalBuyPriceStatus) {
      autoFinalBuyPriceStatus.textContent = error instanceof Error ? error.message : "Unable to calculate buy target.";
    }
  });
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

function vehicleSummary(details) {
  const parts = [
    details?.year,
    details?.make,
    details?.model,
    details?.trim,
  ].filter(Boolean);
  const mileage = details?.mileage ? `${Number(details.mileage).toLocaleString()} miles` : "";
  return [parts.join(" "), mileage].filter(Boolean).join(" | ") || "Vehicle details unavailable.";
}

function renderTitleImpact(titleAdjustment) {
  if (!fullEvaluationTitleImpact) {
    return;
  }
  if (!titleAdjustment?.active) {
    fullEvaluationTitleImpact.textContent = "Title impact adjustments will appear here when applicable.";
    fullEvaluationTitleImpact.classList.add("muted");
    return;
  }

  fullEvaluationTitleImpact.classList.remove("muted");
  fullEvaluationTitleImpact.innerHTML = [
    ["Clean Title Benchmark", titleAdjustment.clean_title_value],
    [
      "Rebuilt Title Range",
      `${titleAdjustment.rebuilt_title_range?.low || ""} to ${titleAdjustment.rebuilt_title_range?.high || ""}`,
    ],
    ["Average Rebuilt Value", titleAdjustment.rebuilt_title_average],
    [
      "Clean vs Rebuilt Difference",
      `${titleAdjustment.value_difference?.low || ""} to ${titleAdjustment.value_difference?.high || ""}`,
    ],
    ["Average Difference", titleAdjustment.value_difference?.average || ""],
    [
      "Rebuilt Safe Buy Window",
      `${titleAdjustment.safe_buy_range?.low || ""} to ${titleAdjustment.safe_buy_range?.high || ""}`,
    ],
  ].map(([label, value]) => `
      <div class="range-row">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value || "")}</strong>
      </div>
    `).join("");
}

function renderProfitTable() {
  if (!currentEvaluation) {
    profitTableBody.innerHTML = `
      <tr>
        <td colspan="3" class="muted">Run or carry a valuation into this page to see the likely profit table.</td>
      </tr>
    `;
    return;
  }

  const resaleRange = currentEvaluation.recommended_target_resale_range || {};
  const resaleLow = parseMoney(resaleRange.low);
  const resaleHigh = parseMoney(resaleRange.high);
  const baseConfidence = Number(currentEvaluation.confidence_score || 0);
  const hasFinalBuyPrice = finalBuyPriceInput.value.trim() !== "";
  const finalBuyPrice = hasFinalBuyPrice ? Number(finalBuyPriceInput.value) : 0;
  const suggestedBuy = parseMoney(currentEvaluation.recommended_max_buy_price) || null;

  if (resaleLow === null || resaleHigh === null) {
    profitTableBody.innerHTML = `
      <tr>
        <td colspan="3" class="muted">Expected resale data is not available for this evaluation.</td>
      </tr>
    `;
    return;
  }

  const expectedResaleMidpoint = (resaleLow + resaleHigh) / 2;
  const dynamicConfidence = hasFinalBuyPrice
    ? computeDealConfidence(
      baseConfidence,
      finalBuyPrice,
      expectedResaleMidpoint,
      suggestedBuy,
    )
    : Math.round(baseConfidence);
  const confidenceDecimal = Math.max(0, Math.min(1, baseConfidence / 100));
  const marketRiskLabel = riskLabelFromConfidence(baseConfidence);
  const riskLabel = riskLabelFromConfidence(dynamicConfidence);
  const riskMultiplier = RISK_MULTIPLIERS[marketRiskLabel] || RISK_MULTIPLIERS.Medium;
  const adjustedResaleBase =
    expectedResaleMidpoint * (0.85 + 0.15 * confidenceDecimal) * riskMultiplier;

  evaluationConfidence.textContent = `${dynamicConfidence}%`;
  evaluationRisk.textContent = riskLabel;

  profitTableBody.innerHTML = CONDITION_MULTIPLIERS.map(([label, multiplier]) => {
    const likelyResale = adjustedResaleBase * multiplier;
    const likelyProfit = hasFinalBuyPrice ? likelyResale - finalBuyPrice : null;

    return `
      <tr>
        <td>${escapeHtml(label)}</td>
        <td>${escapeHtml(formatMoney(likelyResale))}</td>
        <td>${escapeHtml(likelyProfit === null ? "Enter buy price" : formatMoney(likelyProfit))}</td>
      </tr>
    `;
  }).join("");
}

function applyEvaluationPayload(payload) {
  currentEvaluation = payload;
  fullEvaluationVehicle.textContent = vehicleSummary(payload.parsed_details);
  if (fullEvaluationLoading) {
    fullEvaluationLoading.classList.add("hidden-panel");
  }
  const resaleRange = payload.recommended_target_resale_range || {};
  expectedResaleRange.textContent = resaleRange.low && resaleRange.high
    ? (resaleRange.low === resaleRange.high ? resaleRange.low : `${resaleRange.low} - ${resaleRange.high}`)
    : "$0-$0";
  evaluationConfidence.textContent = `${Number(payload.confidence_score || 0)}%`;
  evaluationRisk.textContent = riskLabelFromConfidence(Number(payload.confidence_score || 0));

  const suggestedBuy =
    parseMoney(payload.recommended_max_buy_price) ||
    parseMoney(payload.overall_range?.reseller_buy_price) ||
    0;
  currentSafeBuyPrice = suggestedBuy || null;
  if (suggestedBuyPrice) {
    suggestedBuyPrice.textContent = suggestedBuy
      ? `Safe Buy Value: ${formatMoney(suggestedBuy)}`
      : "Suggested final buy price is unavailable for this evaluation.";
  }
  if (autoFinalBuyPriceStatus) {
    autoFinalBuyPriceStatus.textContent = suggestedBuy
      ? "Calculate for 1 Credit"
      : "Safe buy price is unavailable for this evaluation.";
  }
  renderTitleImpact(payload.title_adjustment);
  finalBuyPriceInput.value = "";
  if (favoriteEvaluationButton) {
    favoriteEvaluationButton.classList.add("hidden-panel");
  }
  if (favoriteEvaluationStatus) {
    favoriteEvaluationStatus.textContent = "";
  }

  renderProfitTable();
}

async function runFinalBuyCalculation() {
  if (!currentEvaluation) {
    throw new Error("Run a valuation before using this add-on.");
  }
  if (autoFinalBuyPriceButton) {
    autoFinalBuyPriceButton.disabled = true;
  }
  if (autoFinalBuyPriceStatus) {
    autoFinalBuyPriceStatus.textContent = "Calculating premium buy target...";
  }
  try {
    const response = await fetch("/api/final-buy-offer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ evaluation: currentEvaluation }),
    });
    const payload = await response.json();
    renderAccountStatus(payload.account_status);
    if (!payload.ok) {
      throw new Error(payload.message || "Unable to calculate premium buy target.");
    }
    const lowestBuyValue = parseMoney(payload.lowest_buy_point);
    finalBuyPriceInput.value = lowestBuyValue ? String(lowestBuyValue) : "";
    renderProfitTable();
    if (favoriteEvaluationButton) {
      favoriteEvaluationButton.classList.toggle("hidden-panel", !lowestBuyValue);
    }
    if (suggestedBuyPrice) {
      suggestedBuyPrice.innerHTML = `
        <strong>Starting Offer:</strong> ${escapeHtml(payload.starting_offer || "")}<br />
        <strong>Lowest Buying Point:</strong> ${escapeHtml(payload.lowest_buy_point || "")}
      `;
    }
    if (autoFinalBuyPriceStatus) {
      autoFinalBuyPriceStatus.textContent = "Premium buy target calculated and credits updated.";
    }
    if (favoriteEvaluationStatus) {
      favoriteEvaluationStatus.textContent = "";
    }
  } finally {
    if (autoFinalBuyPriceButton) {
      autoFinalBuyPriceButton.disabled = false;
    }
  }
}

function buildFullEvaluationSnapshot() {
  if (!currentEvaluation) {
    return null;
  }
  const expectedResaleMidpoint = (() => {
    const resaleRange = currentEvaluation.recommended_target_resale_range || {};
    const low = parseMoney(resaleRange.low);
    const high = parseMoney(resaleRange.high);
    if (!Number.isFinite(low) || !Number.isFinite(high)) {
      return null;
    }
    return (low + high) / 2;
  })();

  const suggestedBuy = parseMoney(currentEvaluation.recommended_max_buy_price) || null;
  const finalBuyPrice = finalBuyPriceInput.value.trim() ? formatMoney(Number(finalBuyPriceInput.value)) : "";
  const profitRows = Array.from(profitTableBody.querySelectorAll("tr")).map((row) => {
    const cells = Array.from(row.querySelectorAll("td")).map((cell) => cell.textContent.trim());
    if (cells.length !== 3) {
      return null;
    }
    return {
      condition: cells[0],
      likely_resale: cells[1],
      likely_profit: cells[2],
    };
  }).filter(Boolean);

  return {
    vehicle_summary: fullEvaluationVehicle.textContent.trim(),
    suggested_buy_price: suggestedBuy ? formatMoney(suggestedBuy) : "",
    final_buy_price: finalBuyPrice,
    average_price_near_mileage: currentEvaluation.average_price_near_mileage?.value
      || currentEvaluation.average_price_near_mileage?.message
      || "",
    expected_resale_range: expectedResaleRange.textContent.trim(),
    expected_resale_midpoint: expectedResaleMidpoint ? formatMoney(expectedResaleMidpoint) : "",
    confidence: evaluationConfidence.textContent.trim(),
    risk: evaluationRisk.textContent.trim(),
    comparable_count: currentEvaluation.comparable_count || 0,
    title_adjustment: currentEvaluation.title_adjustment || {},
    profit_table: profitRows,
  };
}

function cleanVehicleTitle(parsedDetails = {}, fallback = "") {
  const base = [
    parsedDetails.year,
    parsedDetails.make,
    parsedDetails.model,
    cleanTrim(parsedDetails.trim),
  ].filter(Boolean).join(" ").trim();
  const mileage = parsedDetails.mileage ? `${Number(parsedDetails.mileage).toLocaleString()} miles` : "";
  return [base || fallback, mileage].filter(Boolean).join(" | ").trim() || "Saved Evaluation";
}

async function saveEvaluationToPortfolio() {
  const snapshot = buildFullEvaluationSnapshot();
  if (!currentEvaluation || !snapshot || !snapshot.final_buy_price) {
    favoriteEvaluationStatus.textContent = "Enter a final buy price before saving.";
    return;
  }

  favoriteEvaluationButton.disabled = true;
  favoriteEvaluationStatus.textContent = "Saving evaluation...";

  const vehicleTitle = cleanVehicleTitle(currentEvaluation.parsed_details, currentEvaluation.vehicle_summary);

  const preview = {
    comparable_count: `${currentEvaluation.comparable_count || 0} comps`,
    final_buy_price: snapshot.final_buy_price,
    suggested_buy_price: snapshot.suggested_buy_price,
    average_price_near_mileage: snapshot.average_price_near_mileage || "",
    expected_resale_range: snapshot.expected_resale_range,
    confidence: snapshot.confidence,
    risk: snapshot.risk,
  };

  const payload = {
    vehicle_title: vehicleTitle,
    vehicle_input: currentEvaluation.parsed_details?.vehicle_input || "",
    preview,
    snapshot: {
      front_evaluation: currentEvaluation,
      full_evaluation: snapshot,
    },
  };

  try {
    const response = await fetch("/api/portfolio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!result.ok) {
      throw new Error(result.message || "Unable to save evaluation.");
    }
    favoriteEvaluationStatus.textContent = "Saved to Evaluation Portfolio.";
    document.querySelector(".sticky-portfolio-button")?.classList.add("portfolio-bump");
    favoriteEvaluationButton?.classList.add("is-saved");
    window.setTimeout(() => {
      window.location.href = `/portfolio/${result.id}`;
    }, 500);
  } catch (error) {
    favoriteEvaluationStatus.textContent = error.message;
  } finally {
    window.setTimeout(() => {
      document.querySelector(".sticky-portfolio-button")?.classList.remove("portfolio-bump");
      favoriteEvaluationButton?.classList.remove("is-saved");
    }, 900);
    favoriteEvaluationButton.disabled = false;
  }
}

async function loadEvaluation() {
  const url = new URL(window.location.href);
  const vehicleInput = url.searchParams.get("vehicle_input") || "";
  const rebuiltTitle = url.searchParams.get("rebuilt_title") || "";
  const mileage = url.searchParams.get("mileage") || "";
  if (!vehicleInput) {
    if (fullEvaluationLoading) {
      fullEvaluationLoading.classList.add("hidden-panel");
    }
    fullEvaluationVehicle.textContent = "Open this page from the comps screen to carry a vehicle into the deal analyzer.";
    renderTitleImpact(null);
    renderProfitTable();
    return;
  }

  fullEvaluationVehicle.textContent = "";
  if (fullEvaluationLoading) {
    fullEvaluationLoading.classList.remove("hidden-panel");
  }
  const cachedPayload = readCachedEvaluation(vehicleInput, mileage, rebuiltTitle);
  if (cachedPayload) {
    applyEvaluationPayload(cachedPayload);
    return;
  }
  const response = await fetch("/api/valuation", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      vehicle_input: vehicleInput,
      mileage,
      rebuilt_title: rebuiltTitle,
      force_refresh: true,
    }),
  });
  const payload = await response.json();
  renderAccountStatus(payload.account_status);
  if (!payload.ok) {
    if (fullEvaluationLoading) {
      fullEvaluationLoading.classList.add("hidden-panel");
    }
    fullEvaluationVehicle.textContent = payload.message || "Unable to load the current valuation.";
    renderTitleImpact(null);
    renderProfitTable();
    return;
  }

  if (payload.status !== "complete") {
    currentEvaluation = null;
    if (fullEvaluationLoading) {
      fullEvaluationLoading.classList.add("hidden-panel");
    }
    fullEvaluationVehicle.textContent = payload.message || "Please include the year, make, and model to continue.";
    renderTitleImpact(null);
    renderProfitTable();
    return;
  }

  cacheEvaluationPayload(vehicleInput, mileage, rebuiltTitle, payload);
  applyEvaluationPayload(payload);
}

finalBuyPriceInput?.addEventListener("input", () => {
  renderProfitTable();
  if (favoriteEvaluationButton) {
    favoriteEvaluationButton.classList.toggle("hidden-panel", finalBuyPriceInput.value.trim() === "");
  }
  if (favoriteEvaluationStatus) {
    favoriteEvaluationStatus.textContent = "";
  }
  if (autoFinalBuyPriceStatus) {
    autoFinalBuyPriceStatus.textContent = "";
  }
});

favoriteEvaluationButton?.addEventListener("click", saveEvaluationToPortfolio);
autoFinalBuyPriceButton?.addEventListener("click", setAutoFinalBuyPriceFromSafeBuy);

loadEvaluation().catch((error) => {
  if (fullEvaluationLoading) {
    fullEvaluationLoading.classList.add("hidden-panel");
  }
  fullEvaluationVehicle.textContent = `Unable to load the current valuation: ${error.message}`;
  renderTitleImpact(null);
  renderProfitTable();
});
