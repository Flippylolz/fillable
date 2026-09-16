import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";
import { manualSaving } from "./autosave-setting";
import { openNavigation, openUploadPanel } from "./navigation";

test("saved previews populate on first render, persist, and follow saved fill-mode edits", async ({ page }, info) => {
  const title = `Превʼю Ґанни ${info.project.name}`;
  await page.goto("/");
  await page.getByLabel("Логін", { exact: true }).fill("pagebreaks@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill("Synthetic-browser-Їжак-2026");
  await page.getByRole("button", { name: "Увійти", exact: true }).click();
  // This existing synthetic account is also used by the page-boundary flow,
  // which finishes in English. Reset the locale before either viewport run.
  await openNavigation(page);
  await page.getByRole("link", { name: /Профіль|Profile/ }).click();
  await page.getByRole("combobox").selectOption("uk");
  await page.getByRole("button", { name: /Зберегти мову|Save language/ }).click();
  await expect(page.getByText(/Мову інтерфейсу збережено|language preference has been saved/)).toBeVisible();
  await openNavigation(page);
  await page.getByRole("link", { name: "Шаблони", exact: true }).click();
  await openUploadPanel(page);
  await page.getByLabel("Файл DOCX", { exact: true }).setInputFiles({ name: "preview.docx", mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", buffer: await readFile("/fixtures/upload.docx") });
  await page.getByLabel("Назва документа", { exact: true }).fill(title);
  await page.getByRole("button", { name: "Завантажити та зберегти", exact: true }).click();
  let card = page.getByRole("article", { name: title, exact: true });
  await expect(card.locator(".library-preview-placeholder")).toBeVisible();
  await card.getByRole("link", { name: title, exact: true }).click();
  await expect(async () => {
    if (await page.getByText("Це завантаження ще триває. Повторіть спробу згодом.", { exact: true }).isVisible()) {
      await page.getByRole("button", { name: "Повторити відкриття", exact: true }).click();
    }
    await expect(page.getByText("Редагування дозволено.", { exact: true })).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 15000 });
  const heading = await page.locator("#workspace-title").boundingBox();
  expect(heading!.width).toBeGreaterThan(200);
  expect(heading!.height).toBeLessThan(100);
  await manualSaving(page);
  await page.getByRole("button", { name: "Заповнення", exact: true }).click();
  const input = page.locator(".fill-form").getByRole("textbox", { name: "Значення поля: ПІБ клієнта", exact: true }).first();
  await input.fill("Єва Ґалаган — превʼю");
  const field = page.locator(".fill-entry").filter({ has: page.getByRole("textbox", { name: "Значення поля: ПІБ клієнта", exact: true }) }).first();
  await field.getByRole("button", { name: "Жирний", exact: true }).click();
  await expect(page.locator('.fill-preview [data-text-format]').first()).toHaveCSS("font-weight", "700");
  const widths = await page.locator(".fill-layout").evaluate(layout => ({
    form: layout.querySelector(".fill-form")!.getBoundingClientRect().width,
    preview: layout.querySelector(".fill-preview")!.getBoundingClientRect().width,
    desktop: window.innerWidth > 1000,
  }));
  if (widths.desktop) expect(widths.preview).toBeGreaterThan(widths.form);
  await page.screenshot({ path: info.outputPath("fill-formatting.png"), fullPage: true });
  await expect(page.locator(".fill-preview")).toContainText("Єва Ґалаган — превʼю");
  await expect(page.locator(".fill-preview .ProseMirror")).toHaveAttribute("contenteditable", "false");
  const fits = await page.locator(".fill-preview-viewport").evaluate(viewport => {
    const paper = viewport.querySelector('section[data-part="word/document.xml"]')!;
    return paper.getBoundingClientRect().width <= viewport.getBoundingClientRect().width + 1;
  });
  expect(fits).toBe(true);
  await page.getByRole("button", { name: "Зберегти документ", exact: true }).click();
  await expect(page.getByText("Усі зміни документа збережено.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Назад до бібліотеки", exact: true }).click();
  // Saving can refresh the retained library while navigation reveals it.
  // Retry the whole visibility/read condition if that refresh replaces a card.
  await expect(async () => {
    await card.scrollIntoViewIfNeeded();
    await expect(card.locator(".library-preview-content")).toContainText("Єва Ґалаган — превʼю");
  }).toPass({ timeout: 15000 });
  await page.reload();
  card = page.getByRole("article", { name: title, exact: true });
  // Saving can refresh the retained library while navigation reveals it.
  // Retry the whole visibility/read condition if that refresh replaces a card.
  await expect(async () => {
    await card.scrollIntoViewIfNeeded();
    await expect(card.locator(".library-preview-content")).toContainText("Єва Ґалаган — превʼю");
  }).toPass({ timeout: 15000 });
  await expect(card.locator(".library-preview")).toHaveAttribute("inert", "");
  await page.screenshot({ path: info.outputPath("saved-gallery-preview.png"), fullPage: true });
});
