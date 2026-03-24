const siteMenuButton = document.getElementById("site-menu-button");
const siteMenuPanel = document.getElementById("site-menu-panel");

function setMenuOpen(open) {
  if (!siteMenuButton || !siteMenuPanel) {
    return;
  }
  siteMenuButton.setAttribute("aria-expanded", open ? "true" : "false");
  siteMenuPanel.classList.toggle("hidden-panel", !open);
}

siteMenuButton?.addEventListener("click", () => {
  const isOpen = siteMenuButton.getAttribute("aria-expanded") === "true";
  setMenuOpen(!isOpen);
});

document.addEventListener("click", (event) => {
  if (!siteMenuButton || !siteMenuPanel) {
    return;
  }
  const target = event.target;
  if (!(target instanceof Node)) {
    return;
  }
  if (siteMenuButton.contains(target) || siteMenuPanel.contains(target)) {
    return;
  }
  setMenuOpen(false);
});
