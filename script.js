const revealables = document.querySelectorAll(".reveal-item, .section-heading");
const prefersReducedMotion = window.matchMedia(
  "(prefers-reduced-motion: reduce)"
).matches;

if (!("IntersectionObserver" in window) || prefersReducedMotion) {
  revealables.forEach((element) => element.classList.add("is-visible"));
} else {
  revealables.forEach((element, index) => {
    element.style.transitionDelay = `${Math.min(index * 65, 420)}ms`;
  });

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.16 }
  );

  revealables.forEach((element) => observer.observe(element));
}
