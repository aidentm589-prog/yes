const payoutForm = document.getElementById("carvana-payout-form");
const payoutSubmitButton = document.getElementById("carvana-submit-button");
const payoutFormStatus = document.getElementById("carvana-form-status");
const currentJobPanel = document.getElementById("carvana-current-job");
const resultCard = document.getElementById("carvana-result-card");
const historyGrid = document.getElementById("carvana-history");
const accountStatusPill = document.querySelector(".account-status-pill");
const topbarCreditValue = document.getElementById("topbar-credit-value");
const topbarTierLabel = document.getElementById("topbar-tier-label");
const topbarTierDefault = document.getElementById("topbar-tier-default");
const topbarTierHover = document.getElementById("topbar-tier-hover");

let currentJobId = null;
let pollTimer = null;

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
      <strong><a href="/account">${escapeHtml(status.first_name || "Open")}</a></strong>
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

function jobStatusTone(status) {
  if (status === "completed") {
    return "metric-positive";
  }
  if (status === "failed") {
    return "metric-negative";
  }
  if (status === "requires_review") {
    return "metric-warning";
  }
  return "";
}

function buildVehicleIdentifier(job) {
  if (!job) {
    return "";
  }
  const vin = String(job.vin || "").trim();
  if (vin) {
    return vin;
  }
  const plate = String(job.license_plate || "").trim();
  const state = String(job.plate_state || "").trim();
  return [plate, state].filter(Boolean).join(" • ");
}

function renderCurrentJob(job) {
  if (!job) {
    currentJobPanel.textContent = "No payout job selected yet.";
    currentJobPanel.classList.add("muted");
    return;
  }
  currentJobPanel.classList.remove("muted");
  currentJobPanel.innerHTML = `
    <div class="range-row">
      <span>Status</span>
      <strong class="${escapeHtml(jobStatusTone(job.status))}">${escapeHtml(job.status)}</strong>
    </div>
    <div class="range-row">
      <span>Vehicle</span>
      <strong>${escapeHtml(buildVehicleIdentifier(job) || `Job ${job.id}`)}</strong>
    </div>
    <div class="range-row">
      <span>Submitted Mileage</span>
      <strong>${escapeHtml(Number(job.mileage || 0).toLocaleString())}</strong>
    </div>
    <div class="range-row">
      <span>Condition</span>
      <strong>${escapeHtml(job.condition || "")}</strong>
    </div>
    <div class="range-row">
      <span>Created</span>
      <strong>${escapeHtml(formatDateTime(job.created_at))}</strong>
    </div>
    <div class="range-row">
      <span>Updated</span>
      <strong>${escapeHtml(formatDateTime(job.updated_at))}</strong>
    </div>
  `;
}

function renderResult(job) {
  if (!job || !["completed", "requires_review", "failed"].includes(job.status)) {
    resultCard.textContent = "Completed Carvana payout results will appear here.";
    resultCard.classList.add("muted");
    return;
  }
  resultCard.classList.remove("muted");
  const evidenceUrl = job.screenshot_url_or_path || job.result_json?.share_url || job.result_json?.live_url || "";
  const resultLines = [
    ["Carvana Offer", job.offer_amount_display || "N/A"],
    ["Source", "Carvana"],
    ["Submitted Mileage", `${Number(job.mileage || 0).toLocaleString()} miles`],
    ["Condition", job.condition || ""],
    ["Rebuilt Title", job.rebuilt_title ? "Yes" : "No"],
    ["Status", job.status],
    ["Completed At", formatDateTime(job.completed_at || job.failed_at || job.updated_at)],
    ["Summary", job.result_summary || job.error_message || ""],
  ].filter(([, value]) => value);

  resultCard.innerHTML = `
    ${resultLines.map(([label, value]) => `
      <div class="range-row">
        <span>${escapeHtml(label)}</span>
        <strong class="${escapeHtml(label === "Status" ? jobStatusTone(job.status) : "")}">${escapeHtml(value)}</strong>
      </div>
    `).join("")}
    ${evidenceUrl ? `
      <div class="range-row">
        <span>Evidence</span>
        <strong><a href="${escapeHtml(evidenceUrl)}" target="_blank" rel="noreferrer">Open session link</a></strong>
      </div>
    ` : ""}
    ${job.page_text_capture ? `
      <div class="carvana-text-capture">
        <span>Captured Text</span>
        <p>${escapeHtml(job.page_text_capture.slice(0, 900))}</p>
      </div>
    ` : ""}
  `;
}

function renderHistory(items) {
  if (!Array.isArray(items) || !items.length) {
    historyGrid.textContent = "Recent Carvana payout jobs will appear here.";
    historyGrid.classList.add("muted");
    return;
  }
  historyGrid.classList.remove("muted");
  historyGrid.innerHTML = items.map((job) => `
      <article class="listing-card bulk-result-card">
        <div class="listing-card-head bulk-card-head">
          <div>
            <strong class="listing-card-title">${escapeHtml(buildVehicleIdentifier(job) || `Job ${job.id}`)}</strong>
            <span class="listing-card-hover">${escapeHtml(formatDateTime(job.created_at))}</span>
          </div>
          <div class="listing-price-badge">
            <span class="listing-price-label">Offer</span>
            <span class="listing-price">${escapeHtml(job.offer_amount_display || "Pending")}</span>
          </div>
        </div>
        <div class="listing-meta bulk-result-meta">
          <div class="listing-meta-line">
            <span>Status</span>
            <strong class="${escapeHtml(jobStatusTone(job.status))}">${escapeHtml(job.status)}</strong>
          </div>
          <div class="listing-meta-line">
            <span>Condition</span>
            <strong>${escapeHtml(job.condition || "")}</strong>
          </div>
          <div class="listing-meta-line">
            <span>Mileage</span>
            <strong>${escapeHtml(Number(job.mileage || 0).toLocaleString())} miles</strong>
          </div>
        </div>
        <div class="carvana-history-actions">
          <button class="ghost-button compact-button" data-open-job="${job.id}" type="button">Open Details</button>
          ${["failed", "requires_review"].includes(job.status) ? `<button class="ghost-button compact-button" data-retry-job="${job.id}" type="button">Retry</button>` : ""}
        </div>
      </article>
    `).join("");
}

async function getJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!payload.ok) {
    throw new Error(payload.message || "Request failed.");
  }
  return payload;
}

async function refreshHistory() {
  const payload = await getJson("/api/carvana-payout/jobs?limit=12");
  renderHistory(payload.items || []);
}

async function loadJob(jobId) {
  const payload = await getJson(`/api/carvana-payout/jobs/${jobId}`);
  const job = payload.job;
  currentJobId = job.id;
  renderCurrentJob(job);
  renderResult(job);
  if (["queued", "running"].includes(job.status)) {
    startPolling(job.id);
  } else {
    stopPolling();
  }
}

function startPolling(jobId) {
  stopPolling();
  pollTimer = window.setInterval(async () => {
    try {
      await loadJob(jobId);
      await refreshHistory();
    } catch (error) {
      console.error(error);
    }
  }, 3500);
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

payoutForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  payoutSubmitButton.disabled = true;
  payoutFormStatus.textContent = "Creating payout job...";
  try {
    const formData = new FormData(payoutForm);
    const payload = Object.fromEntries(formData.entries());
    if (!payload.rebuilt_title) {
      payload.rebuilt_title = "";
    }
    const result = await getJson("/api/carvana-payout/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderAccountStatus(result.account_status);
    const job = result.job;
    payoutFormStatus.textContent = "Running Carvana payout lookup...";
    renderCurrentJob(job);
    renderResult(null);
    currentJobId = job.id;
    await refreshHistory();
    startPolling(job.id);
  } catch (error) {
    payoutFormStatus.textContent = error.message;
  } finally {
    payoutSubmitButton.disabled = false;
  }
});

historyGrid?.addEventListener("click", async (event) => {
  const openButton = event.target.closest("[data-open-job]");
  const retryButton = event.target.closest("[data-retry-job]");
  if (openButton) {
    const jobId = openButton.getAttribute("data-open-job");
    if (jobId) {
      await loadJob(jobId);
    }
    return;
  }
  if (retryButton) {
    const jobId = retryButton.getAttribute("data-retry-job");
    if (!jobId) {
      return;
    }
    payoutFormStatus.textContent = "Retrying payout job...";
    try {
      const payload = await getJson(`/api/carvana-payout/jobs/${jobId}/retry`, { method: "POST" });
      renderCurrentJob(payload.job);
      renderResult(null);
      startPolling(payload.job.id);
      await refreshHistory();
    } catch (error) {
      payoutFormStatus.textContent = error.message;
    }
  }
});

refreshHistory().catch((error) => {
  payoutFormStatus.textContent = error.message;
});
