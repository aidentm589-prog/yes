const softwareChatButton = document.getElementById("software-chat-button");
const softwareChatPanel = document.getElementById("software-chat-panel");
const softwareChatClose = document.getElementById("software-chat-close");
const softwareChatMessages = document.getElementById("software-chat-messages");
const softwareChatForm = document.getElementById("software-chat-form");
const softwareChatInput = document.getElementById("software-chat-input");
const softwareChatSend = document.getElementById("software-chat-send");

const SOFTWARE_CHAT_STORAGE_KEY = "carFlipSoftwareChatHistory";
const SOFTWARE_CHAT_DEFAULT = [
  {
    role: "assistant",
    content: "I’m your Car Flip Analyzer assistant. Ask about features, workflows, or what to build next.",
  },
];

function loadSoftwareChatHistory() {
  try {
    const raw = window.localStorage.getItem(SOFTWARE_CHAT_STORAGE_KEY);
    if (!raw) {
      return [...SOFTWARE_CHAT_DEFAULT];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || parsed.length === 0) {
      return [...SOFTWARE_CHAT_DEFAULT];
    }
    return parsed.filter((item) => item && item.role && item.content).slice(-20);
  } catch {
    return [...SOFTWARE_CHAT_DEFAULT];
  }
}

let softwareChatHistory = loadSoftwareChatHistory();

function saveSoftwareChatHistory() {
  try {
    window.localStorage.setItem(SOFTWARE_CHAT_STORAGE_KEY, JSON.stringify(softwareChatHistory.slice(-20)));
  } catch {
    // Ignore localStorage failures.
  }
}

function setSoftwareChatOpen(open) {
  if (!softwareChatButton || !softwareChatPanel) {
    return;
  }
  softwareChatButton.setAttribute("aria-expanded", open ? "true" : "false");
  softwareChatPanel.classList.toggle("hidden-panel", !open);
  if (open) {
    renderSoftwareChatMessages();
    window.setTimeout(() => softwareChatInput?.focus(), 80);
  }
}

function renderSoftwareChatMessages() {
  if (!softwareChatMessages) {
    return;
  }
  softwareChatMessages.innerHTML = softwareChatHistory.map((item) => `
      <article class="software-chat-message ${item.role === "user" ? "user" : "assistant"}">
        ${escapeSoftwareChatHtml(item.content || "")}
      </article>
    `).join("");
  softwareChatMessages.scrollTop = softwareChatMessages.scrollHeight;
}

function escapeSoftwareChatHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")
    .replaceAll("\n", "<br>");
}

async function sendSoftwareChatMessage(event) {
  event.preventDefault();
  const text = String(softwareChatInput?.value || "").trim();
  if (!text || !softwareChatSend) {
    return;
  }

  softwareChatHistory.push({ role: "user", content: text });
  softwareChatHistory = softwareChatHistory.slice(-20);
  softwareChatInput.value = "";
  renderSoftwareChatMessages();
  saveSoftwareChatHistory();

  softwareChatSend.disabled = true;
  softwareChatHistory.push({ role: "assistant", content: "Thinking..." });
  renderSoftwareChatMessages();

  try {
    const response = await fetch("/api/software-chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: softwareChatHistory.filter((item) => item.content !== "Thinking...") }),
    });
    const payload = await response.json();
    softwareChatHistory = softwareChatHistory.filter((item) => item.content !== "Thinking...");
    softwareChatHistory.push({
      role: "assistant",
      content: payload.ok ? String(payload.message || "") : String(payload.message || "The software assistant could not answer right now."),
    });
    softwareChatHistory = softwareChatHistory.slice(-20);
    renderSoftwareChatMessages();
    saveSoftwareChatHistory();
  } catch (error) {
    softwareChatHistory = softwareChatHistory.filter((item) => item.content !== "Thinking...");
    softwareChatHistory.push({
      role: "assistant",
      content: `The software assistant hit an error: ${error.message}`,
    });
    renderSoftwareChatMessages();
    saveSoftwareChatHistory();
  } finally {
    softwareChatSend.disabled = false;
    softwareChatInput?.focus();
  }
}

softwareChatButton?.addEventListener("click", () => {
  const isOpen = softwareChatButton.getAttribute("aria-expanded") === "true";
  setSoftwareChatOpen(!isOpen);
});

softwareChatClose?.addEventListener("click", () => setSoftwareChatOpen(false));
softwareChatForm?.addEventListener("submit", sendSoftwareChatMessage);

softwareChatInput?.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    softwareChatForm?.requestSubmit();
  }
});

document.addEventListener("click", (event) => {
  if (!softwareChatButton || !softwareChatPanel) {
    return;
  }
  const target = event.target;
  if (!(target instanceof Node)) {
    return;
  }
  if (softwareChatButton.contains(target) || softwareChatPanel.contains(target)) {
    return;
  }
  setSoftwareChatOpen(false);
});

renderSoftwareChatMessages();
