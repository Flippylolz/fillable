import { expect, type Page } from "@playwright/test";

/** Manual/review scenarios explicitly choose manual saving through the real UI. */
export async function manualSaving(page: Page) {
  const settings = page.locator(".workspace-settings");
  const wasOpen = await settings.getAttribute("open") !== null;
  if (!wasOpen) await settings.locator("summary").click();
  await settings.getByRole("checkbox", { name: /^(Автозбереження документа|Autosave document)$/ }).uncheck();
  await expect(settings.getByRole("checkbox", { name: /^(Автозбереження документа|Autosave document)$/ })).not.toBeChecked();
  if (!wasOpen) await settings.locator("summary").click();
}
