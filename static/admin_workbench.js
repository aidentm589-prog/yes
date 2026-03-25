const workbenchForm = document.getElementById("admin-workbench-form");
const workbenchModeInput = document.getElementById("admin-workbench-mode");
const workbenchVehicleInput = document.getElementById("admin-workbench-vehicle-input");
const workbenchInputLabel = document.getElementById("admin-workbench-input-label");
const workbenchMileageField = document.getElementById("admin-workbench-mileage-field");
const workbenchMileageInput = document.getElementById("admin-workbench-mileage");
const workbenchPriceField = document.getElementById("admin-workbench-price-field");
const workbenchVinField = document.getElementById("admin-workbench-vin-field");
const workbenchVinInput = document.getElementById("admin-workbench-vin");
const workbenchDetailedAddon = document.getElementById("admin-addon-detailed");
const workbenchForceRefresh = document.getElementById("admin-addon-force");
const workbenchRunStatus = document.getElementById("admin-workbench-run-status");
const workbenchLoading = document.getElementById("admin-workbench-loading");
const workbenchLoadingTitle = document.getElementById("admin-workbench-loading-title");
const workbenchLoadingCopy = document.getElementById("admin-workbench-loading-copy");
const workbenchSummaryPanel = document.getElementById("admin-workbench-summary-panel");
const workbenchSummary = document.getElementById("admin-workbench-summary");
const workbenchBulkPanel = document.getElementById("admin-workbench-bulk-panel");
const workbenchBulkGrid = document.getElementById("admin-workbench-bulk-grid");
const workbenchIndividualPanel = document.getElementById("admin-workbench-individual-panel");
const workbenchIndividualGrid = document.getElementById("admin-workbench-individual-grid");
const workbenchZippyPanel = document.getElementById("admin-workbench-zippy-panel");
const workbenchZippyGrid = document.getElementById("admin-workbench-zippy-grid");
const modeCards = document.querySelectorAll("[data-workbench-mode]");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function parseMoney(value) {
  if (value === null || value === undefined) {
    return null;
  }
  const digits = String(value).replace(/[^0-9.-]/g, "");
  if (!digits) {
    return null;
  }
  const number = Number(digits);
  return Number.isFinite(number) ? number : null;
}

function formatMoney(value) {
  if (!Number.isFinite(value)) {
    return "";
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
}

function postJson(url, payload) {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then(async (response) => ({
    ok: response.ok,
    status: response.status,
    body: await response.json().catch(() => ({})),
  }));
}

function setWorkbenchMode(mode) {
  workbenchModeInput.value = mode;
  modeCards.forEach((card) => card.classList.toggle("is-selected", card.dataset.workbenchMode === mode));
  const bulkMode = mode === "bulk";
  const zippyMode = mode === "zippy";
  workbenchInputLabel.textContent = bulkMode ? "Batch Input" : "Vehicle Input";
  workbenchVehicleInput.rows = bulkMode ? 12 : 4;
  workbenchVehicleInput.placeholder = bulkMode
    ? "Paste the cars"
    : zippyMode
      ? "Describe the car or paste a link for a fast scrape..."
      : "Describe the car or paste a link…";
  workbenchMileageField.classList.toggle("hidden-panel", bulkMode);
  workbenchVinField.classList.toggle("hidden-panel", bulkMode);
  workbenchPriceField.classList.toggle("hidden-panel", bulkMode);
  workbenchMileageInput.required = !bulkMode;
}

function setLoadingState(visible, title = "", copy = "") {
  workbenchLoading.classList.toggle("hidden-panel", !visible);
  if (title) {
    workbenchLoadingTitle.textContent = title;
  }
  if (copy) {
    workbenchLoadingCopy.textContent = copy;
  }
}

function hideResults() {
  workbenchSummaryPanel.classList.add("hidden-panel");
  workbenchBulkPanel.classList.add("hidden-panel");
  workbenchIndividualPanel.classList.add("hidden-panel");
  workbenchZippyPanel.classList.add("hidden-panel");
}

function renderSummary(rows = []) {
  workbenchSummaryPanel.classList.remove("hidden-panel");
  workbenchSummary.classList.remove("muted");
  workbenchSummary.innerHTML = rows.map(([label, value]) => `
    <div class="range-row">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(String(value ?? ""))}</strong>
    </div>
  `).join("");
}

function renderIndividual(result) {
  workbenchIndividualPanel.classList.remove("hidden-panel");
  workbenchIndividualGrid.classList.remove("muted");
  const rows = [
    ["Vehicle", result.vehicle_summary || ""],
    ["Market Value", result.overall_range?.market_value || ""],
    ["Safe Buy Value", result.overall_range?.safe_buy_value || ""],
    ["Expected Resale Value", result.overall_range?.expected_resale_value || ""],
    ["Estimated Profit", result.overall_range?.estimated_profit || ""],
    ["Average Price Near This Mileage", result.average_price_near_mileage?.value || result.average_price_near_mileage?.message || ""],
    ["Comp Count", result.comparable_count || 0],
    ["Message", result.message || ""],
  ];
  workbenchIndividualGrid.innerHTML = rows.map(([label, value]) => `
    <article class="listing-card">
      <span class="muted">${escapeHtml(label)}</span>
      <strong>${escapeHtml(String(value ?? ""))}</strong>
    </article>
  `).join("");
}

function renderBulk(items = []) {
  workbenchBulkPanel.classList.remove("hidden-panel");
  workbenchBulkGrid.classList.remove("muted");
  workbenchBulkGrid.innerHTML = items.map((item) => `
    <article class="listing-card bulk-result-card">
      <div class="listing-card-head">
        <div>
          <span class="muted">${escapeHtml(item.status || "complete")}</span>
          <strong class="listing-card-title">${escapeHtml(item.vehicle_name || item.vehicle_title || "Vehicle")}</strong>
        </div>
        <strong class="listing-price-badge">${escapeHtml(item.listed_price || "")}</strong>
      </div>
      <div class="portfolio-section-grid">
        <div class="range-row"><span>Market</span><strong>${escapeHtml(item.market_value || "")}</strong></div>
        <div class="range-row"><span>Safe Buy</span><strong>${escapeHtml(item.safe_buy_value || "")}</strong></div>
        <div class="range-row"><span>Resale</span><strong>${escapeHtml(item.expected_resale_value || "")}</strong></div>
        <div class="range-row"><span>Profit</span><strong>${escapeHtml(item.estimated_profit || "")}</strong></div>
        <div class="range-row"><span>Confidence</span><strong>${escapeHtml(item.confidence || "")}</strong></div>
        <div class="range-row"><span>Risk</span><strong>${escapeHtml(item.risk || "")}</strong></div>
        <div class="range-row"><span>Comps</span><strong>${escapeHtml(String(item.comp_count || 0))}</strong></div>
        <div class="range-row"><span>Location</span><strong>${escapeHtml(item.location || "")}</strong></div>
      </div>
    </article>
  `).join("");
}

function renderZippy(result) {
  workbenchZippyPanel.classList.remove("hidden-panel");
  workbenchZippyGrid.classList.remove("muted");
  const details = result.parsed_details || {};
  const values = result.values || {};
  const rows = [
    ["Vehicle", result.vehicle_summary || ""],
    ["Year", details.year || ""],
    ["Make", details.make || ""],
    ["Model", details.model || ""],
    ["Trim", details.trim || "N/A"],
    ["Mileage", details.mileage ? `${Number(details.mileage).toLocaleString()} miles` : "N/A"],
    ["Average Price Of All Comps", values.average_all_comps || ""],
    ["Average Price Of 20 Closest Mileage Comps", values.average_20_closest_mileage_comps || values.average_all_comps || ""],
    ["Very Poor Buy Price", values.very_poor_buy_price || ""],
    ["Good Buy Price", values.good_buy_price || ""],
    ["Excellent Buy Price", values.excellent_buy_price || ""],
    ["Comp Count", result.comparable_count || 0],
  ];
  workbenchZippyGrid.innerHTML = rows.map(([label, value]) => `
    <article class="listing-card">
      <span class="muted">${escapeHtml(label)}</span>
      <strong>${escapeHtml(String(value ?? ""))}</strong>
    </article>
  `).join("");
}

modeCards.forEach((card) => {
  card.addEventListener("click", () => {
    setWorkbenchMode(card.dataset.workbenchMode || "individual");
  });
});

workbenchForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const bulkMode = workbenchModeInput.value === "bulk";
  const zippyMode = workbenchModeInput.value === "zippy";
  workbenchMileageInput.setCustomValidity("");
  if (!bulkMode && !workbenchForm.reportValidity()) {
    if (!String(workbenchMileageInput.value || "").trim()) {
      workbenchMileageInput.setCustomValidity("Mileage is required.");
      workbenchMileageInput.reportValidity();
    }
    return;
  }
  if (bulkMode && !String(workbenchVehicleInput.value || "").trim()) {
    workbenchVehicleInput.setCustomValidity("Paste the cars you want to run.");
    workbenchVehicleInput.reportValidity();
    return;
  }
  workbenchVehicleInput.setCustomValidity("");
  hideResults();
  setLoadingState(
    true,
    bulkMode ? "Running Batch V1" : zippyMode ? "Running Zippy" : "Running Indiv V1",
    bulkMode
      ? "Parsing the queue and evaluating every valid car."
      : zippyMode
        ? "Scraping the market, averaging comps, and generating fast buy values."
        : "Pulling comps and calculating the deal.",
  );
  workbenchRunStatus.textContent = "Running...";

  const payload = {
    vehicle_input: workbenchVehicleInput.value,
    evaluation_mode: workbenchModeInput.value,
    mileage: workbenchMileageInput.value,
    vin: workbenchVinInput.value,
    asking_price: document.getElementById("admin-workbench-asking-price")?.value || "",
    force_refresh: workbenchForceRefresh.checked,
    detailed_vehicle_report: workbenchDetailedAddon.checked ? "on" : "off",
  };

  try {
    const result = await postJson("/api/valuation", payload);
    setLoadingState(false);
    if (!result.ok || !result.body.ok) {
      workbenchRunStatus.textContent = result.body.message || "Run failed.";
      renderSummary([["Status", "Failed"], ["Message", result.body.message || "Unable to complete the evaluation."]]);
      return;
    }

    if (result.body.mode === "bulk") {
      workbenchRunStatus.textContent = `Batch complete: ${result.body.summary?.evaluated_entries || 0} evaluated`;
      renderSummary([
        ["Mode", "Batch V1"],
        ["Pasted Vehicles", result.body.summary?.total_entries || 0],
        ["Parsed Vehicles", result.body.summary?.parsed_entries || 0],
        ["Evaluated Vehicles", result.body.summary?.evaluated_entries || 0],
        ["Skipped / Failed", (result.body.summary?.skipped_entries || 0) + (result.body.summary?.failed_entries || 0)],
      ]);
      renderBulk(result.body.items || []);
      return;
    }

    if (result.body.mode === "zippy") {
      workbenchRunStatus.textContent = "Zippy run complete.";
      renderSummary([
        ["Mode", "Zippy"],
        ["Vehicle", result.body.vehicle_summary || ""],
        ["Comp Count", result.body.comparable_count || 0],
        ["Status", result.body.status || ""],
      ]);
      renderZippy(result.body);
      return;
    }

    workbenchRunStatus.textContent = "Individual run complete.";
    renderSummary([
      ["Mode", "Indiv V1"],
      ["Vehicle", result.body.vehicle_summary || ""],
      ["Comp Count", result.body.comparable_count || 0],
      ["Status", result.body.status || ""],
    ]);
    renderIndividual(result.body);
  } catch (error) {
    setLoadingState(false);
    workbenchRunStatus.textContent = error instanceof Error ? error.message : "Run failed.";
    renderSummary([["Status", "Failed"], ["Message", workbenchRunStatus.textContent]]);
  }
});

setWorkbenchMode("individual");
