import type { Page } from "playwright";

import type { InteractiveElement, ObservationSnapshot } from "@/types/operator";

function summarizePageText(text: string) {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) {
    return "No meaningful visible text was detected on the current page.";
  }

  return cleaned.slice(0, 700);
}

export async function inspectPage(page: Page): Promise<ObservationSnapshot> {
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
          placeholder: element.getAttribute("placeholder"),
          type: element.getAttribute("type"),
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
    recentErrors: [],
  };
}
