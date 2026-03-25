import type { Page } from "playwright";

import type { InteractiveElement, ObservationSnapshot } from "@/types/operator";

function summarizePageText(text: string) {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) {
    return "No meaningful visible text was detected on the current page.";
  }

  return cleaned.slice(0, 700);
}

function summarizeInteractiveElements(elements: InteractiveElement[]) {
  if (!elements.length) {
    return "No visible interactive controls were detected.";
  }

  return elements
    .slice(0, 8)
    .map((element) => {
      const parts = [
        element.tag,
        element.text || element.ariaLabel || element.name || element.placeholder || "unlabeled",
      ];
      if (element.href) {
        parts.push(`href=${element.href}`);
      }
      if (element.disabled) {
        parts.push("disabled");
      }
      return parts.join(" | ");
    })
    .join("; ");
}

export async function inspectPage(
  page: Page,
  phase: ObservationSnapshot["phase"] = "checkpoint",
): Promise<ObservationSnapshot> {
  await page.waitForLoadState("domcontentloaded").catch(() => null);

  const data = await page.evaluate(() => {
    function isVisible(element: Element) {
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();

      return (
        style.visibility !== "hidden" &&
        style.display !== "none" &&
        rect.width > 0 &&
        rect.height > 0
      );
    }

    function buildSelector(element: Element | null): string | null {
      if (!element || !(element instanceof HTMLElement)) {
        return null;
      }

      if (element.id) {
        return `#${element.id}`;
      }

      const testId =
        element.getAttribute("data-testid") ||
        element.getAttribute("data-test") ||
        element.getAttribute("data-qa");

      if (testId) {
        return `[data-testid="${CSS.escape(testId)}"]`;
      }

      const name = element.getAttribute("name");
      if (name && ["input", "select", "textarea", "button"].includes(element.tagName.toLowerCase())) {
        return `${element.tagName.toLowerCase()}[name="${CSS.escape(name)}"]`;
      }

      const ariaLabel = element.getAttribute("aria-label");
      if (ariaLabel && ["button", "input", "textarea", "select", "a"].includes(element.tagName.toLowerCase())) {
        return `${element.tagName.toLowerCase()}[aria-label="${CSS.escape(ariaLabel)}"]`;
      }

      const href = element.getAttribute("href");
      if (href && element.tagName.toLowerCase() === "a") {
        return `a[href="${CSS.escape(href)}"]`;
      }

      const parts: string[] = [];
      let current: HTMLElement | null = element;

      while (current && current.tagName.toLowerCase() !== "html" && parts.length < 4) {
        const tag = current.tagName.toLowerCase();
        const parent: HTMLElement | null = current.parentElement;
        if (!parent) {
          parts.unshift(tag);
          break;
        }

        const siblings = Array.from(parent.children).filter(
          (child) => child.tagName === current?.tagName,
        );
        const index = siblings.indexOf(current) + 1;
        parts.unshift(`${tag}:nth-of-type(${index})`);
        current = parent;
      }

      return parts.join(" > ");
    }

    function selectorSource(element: Element) {
      if (!(element instanceof HTMLElement)) {
        return null;
      }
      if (element.id) {
        return "id";
      }
      if (
        element.getAttribute("data-testid") ||
        element.getAttribute("data-test") ||
        element.getAttribute("data-qa")
      ) {
        return "data-testid";
      }
      if (element.getAttribute("name")) {
        return "name";
      }
      if (element.getAttribute("aria-label")) {
        return "aria-label";
      }
      if (element.getAttribute("href")) {
        return "href";
      }
      return "dom-path";
    }

    const visibleText = Array.from(document.querySelectorAll("body *"))
      .filter(isVisible)
      .map((element) => element.textContent?.trim() ?? "")
      .filter(Boolean)
      .join(" ");

    const interactive = Array.from(
      document.querySelectorAll("a, button, input, select, textarea, [role='button'], [onclick]"),
    )
      .filter(isVisible)
      .slice(0, 30)
      .map((element) => {
        const htmlElement = element as HTMLElement;

        return {
          selector: buildSelector(element),
          tag: element.tagName.toLowerCase(),
          role: element.getAttribute("role"),
          text: htmlElement.innerText?.trim() ?? element.getAttribute("aria-label") ?? "",
          name: element.getAttribute("name"),
          ariaLabel: element.getAttribute("aria-label"),
          placeholder: element.getAttribute("placeholder"),
          type: element.getAttribute("type"),
          href: element.getAttribute("href"),
          disabled:
            element.hasAttribute("disabled") ||
            element.getAttribute("aria-disabled") === "true",
          selectorSource: selectorSource(element),
        };
      })
      .filter((item): item is InteractiveElement => Boolean(item.selector));

    return {
      title: document.title,
      visibleText,
      interactiveMap: interactive,
    };
  });

  return {
    url: page.url(),
    title: data.title,
    visibleText: data.visibleText,
    summary: summarizePageText(data.visibleText),
    interactiveMap: data.interactiveMap,
    interactiveSummary: summarizeInteractiveElements(data.interactiveMap),
    recentErrors: [],
    startupBlank: page.url() === "about:blank",
    phase,
  };
}
