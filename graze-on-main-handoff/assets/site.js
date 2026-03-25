const navToggle = document.querySelector(".menu-toggle");
const siteNav = document.querySelector(".site-nav");
const siteHeader = document.querySelector(".site-header");

if (navToggle && siteNav) {
  navToggle.addEventListener("click", () => {
    const isOpen = navToggle.getAttribute("aria-expanded") === "true";
    navToggle.setAttribute("aria-expanded", String(!isOpen));
    siteNav.classList.toggle("is-open");
  });
}

const syncHeaderState = () => {
  if (!siteHeader) return;
  siteHeader.classList.toggle("is-scrolled", window.scrollY > 28);
};
syncHeaderState();
window.addEventListener("scroll", syncHeaderState, { passive: true });

const reveals = document.querySelectorAll("[data-reveal]");
const revealObserver = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        revealObserver.unobserve(entry.target);
      }
    }
  },
  { threshold: 0.12 }
);
reveals.forEach((node) => revealObserver.observe(node));

const storySteps = Array.from(document.querySelectorAll("[data-scene-step]"));
const storyPanels = Array.from(document.querySelectorAll("[data-scene-panel]"));
if (storySteps.length && storyPanels.length) {
  let storyFrame = 0;

  const updateStoryPanels = () => {
    storyFrame = 0;
    const viewportCenter = window.innerHeight * 0.5;
    const weights = storySteps.map((step) => {
      const rect = step.getBoundingClientRect();
      const stepCenter = rect.top + rect.height * 0.5;
      const distance = Math.abs(viewportCenter - stepCenter);
      const maxDistance = window.innerHeight * 0.9;
      const raw = Math.max(0, 1 - distance / maxDistance);
      return raw * raw;
    });

    const strongest = weights.reduce(
      (best, weight, index) => (weight > best.weight ? { index, weight } : best),
      { index: 0, weight: -1 }
    ).index;

    const total = weights.reduce((sum, weight) => sum + weight, 0) || 1;

    storySteps.forEach((step, index) => {
      step.classList.toggle("is-active", index === strongest);
    });

    storyPanels.forEach((panel, index) => {
      const strength = weights[index] / total;
      const scale = 1.04 - strength * 0.04;
      panel.classList.toggle("is-active", index === strongest);
      panel.style.opacity = strength.toFixed(4);
      panel.style.transform = `scale(${scale.toFixed(4)})`;
    });
  };

  const queueStoryUpdate = () => {
    if (storyFrame) return;
    storyFrame = window.requestAnimationFrame(updateStoryPanels);
  };

  updateStoryPanels();
  window.addEventListener("scroll", queueStoryUpdate, { passive: true });
  window.addEventListener("resize", queueStoryUpdate);
}

document.querySelectorAll("[data-mail-form]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const target = event.currentTarget;
    if (!(target instanceof HTMLFormElement)) return;
    if (!target.reportValidity()) return;

    const recipient = target.dataset.recipient ?? "";
    const subject = target.dataset.subject ?? "Website inquiry";
    const success = target.dataset.success ?? "Your email draft is ready.";
    const status = target.querySelector(".form-status");
    const formData = new FormData(target);
    const body = Array.from(formData.entries())
      .map(([key, value]) => {
        const label = key.replace(/([A-Z])/g, " $1").replace(/^./, (s) => s.toUpperCase());
        return `${label}: ${value}`;
      })
      .join("\n");

    window.location.href = `mailto:${recipient}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    if (status) status.textContent = success;
    target.reset();
  });
});
