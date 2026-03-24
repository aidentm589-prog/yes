const adminOverview = document.getElementById("admin-overview");
const adminSourceHealth = document.getElementById("admin-source-health");
const adminSources = document.getElementById("admin-sources");
const adminUsers = document.getElementById("admin-users");
const adminPayoutJobs = document.getElementById("admin-payout-jobs");
const adminSubscriptions = document.getElementById("admin-subscriptions");
const accountStatusPill = document.querySelector(".account-status-pill");
const topbarCreditValue = document.getElementById("topbar-credit-value");
const topbarTierLabel = document.getElementById("topbar-tier-label");
const topbarTierDefault = document.getElementById("topbar-tier-default");
const topbarTierHover = document.getElementById("topbar-tier-hover");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
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

function badgeClass(status) {
  if (status === "error") {
    return "admin-badge error";
  }
  if (status === "disabled") {
    return "admin-badge disabled";
  }
  return "admin-badge";
}

function renderOverview(data) {
  if (!adminOverview) {
    return;
  }
  adminOverview.classList.remove("muted");
  adminOverview.innerHTML = [
    ["Generated", formatDateTime(data.generated_at || "")],
    ["Clients", String(data.client_count || 0)],
    ["Saved Evaluations", String(data.portfolio_count || 0)],
    ["Enabled Sources", String(data.enabled_source_count || 0)],
    ["Cache DB", data.cache_db_path || ""],
  ].map(([label, value]) => `
      <article class="listing-card">
        <span class="muted">${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </article>
    `).join("");
}

function renderHealthTable(items) {
  if (!adminSourceHealth) {
    return;
  }
  if (!Array.isArray(items) || items.length === 0) {
    adminSourceHealth.textContent = "No source health data available.";
    return;
  }
  adminSourceHealth.classList.remove("muted");
  adminSourceHealth.innerHTML = `
    <table class="admin-table">
      <thead>
        <tr>
          <th>Source</th>
          <th>Status</th>
          <th>Enabled</th>
          <th>Message</th>
          <th>Comps</th>
        </tr>
      </thead>
      <tbody>
        ${items.map((item) => `
          <tr>
            <td>${escapeHtml(item.label || item.key || "Source")}</td>
            <td><span class="${escapeHtml(badgeClass(item.status))}">${escapeHtml(item.status || "unknown")}</span></td>
            <td>${escapeHtml(item.enabled ? "Yes" : "No")}</td>
            <td>${escapeHtml(item.message || "")}</td>
            <td>${escapeHtml(item.count ? String(item.count) : "0")}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderSourcesTable(items) {
  if (!adminSources) {
    return;
  }
  if (!Array.isArray(items) || items.length === 0) {
    adminSources.textContent = "No source metadata available.";
    return;
  }
  adminSources.classList.remove("muted");
  adminSources.innerHTML = `
    <table class="admin-table">
      <thead>
        <tr>
          <th>Source</th>
          <th>Official</th>
          <th>Fragile</th>
          <th>Enabled</th>
          <th>Fields</th>
          <th>Notes</th>
        </tr>
      </thead>
      <tbody>
        ${items.map((item) => `
          <tr>
            <td>${escapeHtml(item.label || item.key || "Source")}</td>
            <td>${escapeHtml(item.official ? "Yes" : "No")}</td>
            <td>${escapeHtml(item.fragile ? "Yes" : "No")}</td>
            <td>${escapeHtml(item.enabled ? "Yes" : "No")}</td>
            <td>${escapeHtml(Array.isArray(item.fields) ? item.fields.join(", ") : "")}</td>
            <td>${escapeHtml(item.notes || "")}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderUsersTable(items) {
  if (!adminUsers) {
    return;
  }
  if (!Array.isArray(items) || items.length === 0) {
    adminUsers.textContent = "No clients found.";
    return;
  }
  adminUsers.classList.remove("muted");
  adminUsers.innerHTML = `
    <table class="admin-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Email</th>
          <th>Tier</th>
          <th>Credits</th>
          <th>Created</th>
          <th>Updated</th>
          <th>Status</th>
          <th>Permissions</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${items.map((item) => `
          <tr data-user-id="${item.id}">
            <td><input class="admin-name-input" type="text" value="${escapeHtml(item.first_name || "")}" placeholder="First name" /></td>
            <td>${escapeHtml(item.email)}</td>
            <td>
              <select class="admin-tier-select">
                <option value="1" ${item.tier === 1 ? "selected" : ""}>Tier 1</option>
                <option value="2" ${item.tier === 2 ? "selected" : ""}>Tier 2</option>
                <option value="3" ${item.tier === 3 ? "selected" : ""}>Tier 3</option>
                <option value="4" ${item.tier === 4 ? "selected" : ""}>Tier 4</option>
              </select>
            </td>
            <td><input class="admin-credit-input" type="number" min="0" step="1" value="${escapeHtml(String(item.credit_balance || 0))}" /></td>
            <td>${escapeHtml(formatDateTime(item.created_at))}</td>
            <td>${escapeHtml(formatDateTime(item.updated_at))}</td>
            <td>${escapeHtml(item.status || "active")}</td>
            <td>${escapeHtml(item.permissions_summary || "")}</td>
            <td>
              <div class="admin-action-row">
                <button type="button" class="ghost-button admin-user-save">Save</button>
                <button type="button" class="ghost-button admin-user-role">${item.role === "admin" ? "Remove Admin" : "+ Admin"}</button>
                <button type="button" class="ghost-button admin-user-ban">${item.status === "banned" ? "Unban" : "Ban"}</button>
                <button type="button" class="ghost-button admin-user-delete admin-user-delete-button">Delete</button>
              </div>
              <div class="admin-inline-status muted"></div>
            </td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderSubscriptionTiers(items) {
  if (!adminSubscriptions) {
    return;
  }
  if (!Array.isArray(items) || items.length === 0) {
    adminSubscriptions.textContent = "No subscription tiers found.";
    return;
  }
  adminSubscriptions.classList.remove("muted");
  adminSubscriptions.innerHTML = items.map((item) => `
    <article class="subscription-admin-card" data-tier="${item.tier}">
      <div class="subscription-admin-head">
        <span>Tier ${escapeHtml(String(item.tier))}</span>
        <strong>${escapeHtml(item.display_name || `Tier ${item.tier}`)}</strong>
      </div>
      <label class="full-evaluation-label">
        <span>Display Name</span>
        <input class="admin-subscription-name" type="text" value="${escapeHtml(item.display_name || "")}" />
      </label>
      <label class="full-evaluation-label">
        <span>Credits Granted</span>
        <input class="admin-subscription-credits" type="number" min="0" step="1" value="${escapeHtml(String(item.credits_granted || 0))}" />
      </label>
      <label class="full-evaluation-label">
        <span>Monthly Price</span>
        <input class="admin-subscription-monthly" type="text" value="${escapeHtml(item.monthly_price || "")}" />
      </label>
      <label class="full-evaluation-label">
        <span>Yearly Price</span>
        <input class="admin-subscription-yearly" type="text" value="${escapeHtml(item.yearly_price || "")}" />
      </label>
      <label class="full-evaluation-label">
        <span>Value Line</span>
        <textarea class="admin-subscription-copy" rows="3">${escapeHtml(item.marketing_copy || "")}</textarea>
      </label>
      <div class="subscription-admin-flags">
        <label><input class="admin-subscription-bulk" type="checkbox" ${item.has_bulk_access ? "checked" : ""} /> Bulk Access</label>
        <label><input class="admin-subscription-unlimited" type="checkbox" ${item.is_unlimited ? "checked" : ""} /> Unlimited Usage</label>
      </div>
      <div class="admin-action-row">
        <button type="button" class="ghost-button admin-subscription-save">Save Tier</button>
        <div class="admin-inline-status muted"></div>
      </div>
    </article>
  `).join("");
}

function renderPayoutJobsTable(items) {
  if (!adminPayoutJobs) {
    return;
  }
  if (!Array.isArray(items) || items.length === 0) {
    adminPayoutJobs.textContent = "No payout jobs found.";
    return;
  }
  adminPayoutJobs.classList.remove("muted");
  adminPayoutJobs.innerHTML = `
    <table class="admin-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Vehicle</th>
          <th>Status</th>
          <th>Offer</th>
          <th>Mileage</th>
          <th>Created</th>
          <th>Summary / Error</th>
        </tr>
      </thead>
      <tbody>
        ${items.map((item) => `
          <tr>
            <td>${escapeHtml(String(item.id))}</td>
            <td>${escapeHtml(item.vehicle_identifier || "")}</td>
            <td><span class="${escapeHtml(badgeClass(item.status))}">${escapeHtml(item.status || "")}</span></td>
            <td>${escapeHtml(item.offer_amount_display || "")}</td>
            <td>${escapeHtml(item.mileage ? `${Number(item.mileage).toLocaleString()}` : "")}</td>
            <td>${escapeHtml(formatDateTime(item.created_at))}</td>
            <td>${escapeHtml(item.result_summary || item.error_message || "")}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

async function loadAdminOverview() {
  if (!adminOverview && !adminSourceHealth && !adminSources) {
    return;
  }
  const response = await fetch("/api/admin/overview");
  const payload = await response.json();
  if (!payload.ok) {
    throw new Error(payload.message || "Unable to load admin overview.");
  }
  renderOverview(payload);
  renderHealthTable(payload.source_health || []);
  renderSourcesTable(payload.sources || []);
}

async function loadUsers() {
  if (!adminUsers) {
    return;
  }
  const response = await fetch("/api/admin/users");
  const payload = await response.json();
  if (!payload.ok) {
    throw new Error(payload.message || "Unable to load users.");
  }
  renderUsersTable(payload.items || []);
}

async function loadPayoutJobs() {
  if (!adminPayoutJobs) {
    return;
  }
  const response = await fetch("/api/admin/payout-jobs");
  const payload = await response.json();
  if (!payload.ok) {
    throw new Error(payload.message || "Unable to load payout jobs.");
  }
  renderPayoutJobsTable(payload.items || []);
}

async function loadSubscriptionTiers() {
  if (!adminSubscriptions) {
    return;
  }
  const response = await fetch("/api/admin/subscriptions");
  const payload = await response.json();
  if (!payload.ok) {
    throw new Error(payload.message || "Unable to load subscription settings.");
  }
  renderSubscriptionTiers(payload.items || []);
}

async function refreshAccountStatus() {
  if (!accountStatusPill) {
    return;
  }
  const response = await fetch("/api/account/status");
  const payload = await response.json();
  if (payload?.ok && payload.account_status) {
    renderAccountStatus(payload.account_status);
  }
}

adminUsers?.addEventListener("click", async (event) => {
  const actionButton = event.target.closest(".admin-user-save, .admin-user-role, .admin-user-ban, .admin-user-delete");
  if (!actionButton) {
    return;
  }
  const row = actionButton.closest("tr");
  if (!row) {
    return;
  }
  const userId = row.dataset.userId;
  const tier = row.querySelector(".admin-tier-select")?.value;
  const creditBalance = row.querySelector(".admin-credit-input")?.value;
  const firstName = row.querySelector(".admin-name-input")?.value || "";
  const inlineStatus = row.querySelector(".admin-inline-status");
  const saveButton = row.querySelector(".admin-user-save");
  const roleButton = row.querySelector(".admin-user-role");
  const banButton = row.querySelector(".admin-user-ban");
  const deleteButton = row.querySelector(".admin-user-delete");

  const setButtonsDisabled = (disabled) => {
    [saveButton, roleButton, banButton, deleteButton].forEach((button) => {
      if (button) {
        button.disabled = disabled;
      }
    });
  };

  if (inlineStatus) {
    inlineStatus.textContent = actionButton.classList.contains("admin-user-save")
      ? "Saving..."
      : actionButton.classList.contains("admin-user-ban")
        ? "Updating..."
        : "Deleting...";
  }
  setButtonsDisabled(true);
  try {
    if (actionButton.classList.contains("admin-user-delete")) {
      const confirmed = window.confirm("Delete this account permanently? This will wipe the account, saved evaluations, and payout jobs.");
      if (!confirmed) {
        if (inlineStatus) {
          inlineStatus.textContent = "";
        }
        return;
      }
      const response = await fetch(`/api/admin/users/${userId}`, {
        method: "DELETE",
      });
      const payload = await response.json();
      if (!payload.ok) {
        throw new Error(payload.message || "Unable to delete user.");
      }
      row.remove();
      if (inlineStatus) {
        inlineStatus.textContent = "Deleted.";
      }
      await loadAdminOverview();
      await refreshAccountStatus();
      return;
    }

    if (actionButton.classList.contains("admin-user-ban")) {
      const nextStatus = actionButton.textContent.trim().toLowerCase() === "unban" ? "active" : "banned";
      const response = await fetch(`/api/admin/users/${userId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus }),
      });
      const payload = await response.json();
      if (!payload.ok) {
        throw new Error(payload.message || "Unable to update user status.");
      }
      if (inlineStatus) {
        inlineStatus.textContent = nextStatus === "banned" ? "Account banned." : "Account reactivated.";
      }
      await loadUsers();
      await loadAdminOverview();
      await refreshAccountStatus();
      return;
    }

    if (actionButton.classList.contains("admin-user-role")) {
      const nextRole = actionButton.textContent.trim().toLowerCase().includes("remove") ? "client" : "admin";
      const response = await fetch(`/api/admin/users/${userId}/role`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: nextRole }),
      });
      const payload = await response.json();
      if (!payload.ok) {
        throw new Error(payload.message || "Unable to update admin access.");
      }
      if (inlineStatus) {
        inlineStatus.textContent = nextRole === "admin" ? "Admin access granted." : "Admin access removed.";
      }
      await loadUsers();
      await loadAdminOverview();
      await refreshAccountStatus();
      return;
    }

    const response = await fetch(`/api/admin/users/${userId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        first_name: firstName,
        tier: Number(tier || 1),
        credit_balance: Number(creditBalance || 0),
      }),
    });
    const payload = await response.json();
    if (!payload.ok) {
      throw new Error(payload.message || "Unable to update user.");
    }
    if (inlineStatus) {
      inlineStatus.textContent = "Saved.";
    }
    await loadUsers();
    await loadAdminOverview();
    await refreshAccountStatus();
  } catch (error) {
    if (inlineStatus) {
      inlineStatus.textContent = error instanceof Error ? error.message : "Request failed.";
    }
  } finally {
    setButtonsDisabled(false);
  }
});

adminSubscriptions?.addEventListener("click", async (event) => {
  const button = event.target.closest(".admin-subscription-save");
  if (!button) {
    return;
  }
  const card = button.closest("[data-tier]");
  if (!card) {
    return;
  }
  const tier = Number(card.dataset.tier || 0);
  const inlineStatus = card.querySelector(".admin-inline-status");
  button.disabled = true;
  if (inlineStatus) {
    inlineStatus.textContent = "Saving...";
  }
  try {
    const response = await fetch(`/api/admin/subscriptions/${tier}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        display_name: card.querySelector(".admin-subscription-name")?.value || "",
        credits_granted: Number(card.querySelector(".admin-subscription-credits")?.value || 0),
        monthly_price: card.querySelector(".admin-subscription-monthly")?.value || "",
        yearly_price: card.querySelector(".admin-subscription-yearly")?.value || "",
        marketing_copy: card.querySelector(".admin-subscription-copy")?.value || "",
        has_bulk_access: Boolean(card.querySelector(".admin-subscription-bulk")?.checked),
        is_unlimited: Boolean(card.querySelector(".admin-subscription-unlimited")?.checked),
      }),
    });
    const payload = await response.json();
    if (!payload.ok) {
      throw new Error(payload.message || "Unable to save subscription tier.");
    }
    if (inlineStatus) {
      inlineStatus.textContent = "Saved.";
    }
  } catch (error) {
    if (inlineStatus) {
      inlineStatus.textContent = error instanceof Error ? error.message : "Request failed.";
    }
  } finally {
    button.disabled = false;
  }
});

Promise.all([loadAdminOverview(), loadUsers(), loadPayoutJobs(), loadSubscriptionTiers()]).catch((error) => {
  const message = `Unable to load admin dashboard: ${error.message}`;
  if (adminOverview) {
    adminOverview.textContent = message;
  }
  if (adminUsers) {
    adminUsers.textContent = message;
  }
  if (adminSourceHealth) {
    adminSourceHealth.textContent = message;
  }
  if (adminSources) {
    adminSources.textContent = message;
  }
  if (adminPayoutJobs) {
    adminPayoutJobs.textContent = message;
  }
  if (adminSubscriptions) {
    adminSubscriptions.textContent = message;
  }
});
