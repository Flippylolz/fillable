import { expect, type Page } from "@playwright/test";

/** The gallery sidebar is an off-canvas drawer below the shell's 48rem
    breakpoint; open it before using navigation links or sign-out. On wider
    viewports the rail is permanently visible, so this is a no-op. A drawer
    that is already expanded is left open. */
export async function openNavigation(page: Page) {
  if ((page.viewportSize()?.width ?? 1280) > 768) return;
  const menu = page.getByRole("button", { name: /Меню|Menu/ });
  if ((await menu.getAttribute("aria-expanded")) === "true") return;
  await menu.click();
  await expect(page.getByRole("link", { name: /Мої документи|My documents/ })).toBeVisible();
}

/** Close the narrow-screen drawer again; no-op on desktop viewports. */
export async function closeNavigation(page: Page) {
  if ((page.viewportSize()?.width ?? 1280) > 768) return;
  const menu = page.getByRole("button", { name: /Меню|Menu/ });
  if ((await menu.getAttribute("aria-expanded")) === "true") {
    await page.keyboard.press("Escape");
    await expect(page.getByRole("link", { name: /Мої документи|My documents/ })).toBeHidden();
  }
}

/** Reveal the library upload form; the gallery keeps it behind the toolbar
    button instead of permanently occupying the page. */
export async function openUploadPanel(page: Page) {
  const toggle = page.getByRole("button", { name: /Завантажити DOCX|Upload DOCX/ });
  if ((await toggle.getAttribute("aria-expanded")) === "false") await toggle.click();
  await expect(page.getByLabel("Файл DOCX", { exact: true })).toBeVisible();
}
