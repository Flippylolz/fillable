import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";
import { openNavigation, openUploadPanel } from "./navigation";

test("the workspace shows where one page ends and the next begins", async ({ page }, testInfo) => {
  const bytes = await readFile("/fixtures/upload.docx");
  const title = `Межі сторінок — ${testInfo.project.name}`;
  await page.goto("/");
  await page.getByLabel("Логін", { exact: true }).fill("pagebreaks@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill("Synthetic-browser-Їжак-2026");
  await page.getByRole("button", { name: "Увійти", exact: true }).click();
  // The saved profile language survives sessions; run this flow in Ukrainian.
  await openNavigation(page);
  await page.getByRole("link", { name: /Профіль|Profile/ }).click();
  await page.getByRole("combobox").selectOption("uk");
  await page.getByRole("button", { name: /Зберегти мову|Save language/ }).click();
  await expect(page.getByText(/Мову інтерфейсу збережено|language preference has been saved/)).toBeVisible();
  await openNavigation(page);
  await page.getByRole("link", { name: /Мої документи|My documents/ }).click();
  await openUploadPanel(page);
  await page.getByLabel("Файл DOCX", { exact: true }).setInputFiles({
    name: "Межі-сторінок.docx",
    mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: bytes,
  });
  await page.getByLabel("Назва документа", { exact: true }).fill(title);
  await page.getByRole("button", { name: "Завантажити та зберегти", exact: true }).click();
  const card = page.getByRole("article", { name: title, exact: true });
  await expect(card.getByText("Перевірку завершено", { exact: true })).toBeVisible({ timeout: 30000 });
  // Open the workspace directly by its URL; independent of library card controls.
  const list = await (await page.request.get("/api/documents?kind=template")).json();
  const saved = list.items.find((item: { title: string }) => item.title === title);
  await page.goto(`/editor/${saved.id}`);
  await expect(page.getByRole("textbox", { name: "Редагований документ", exact: true })).toBeVisible();
  const label = page.locator(".document-page-break-label");
  await expect(label.first()).toBeVisible();
  const labels = await label.allTextContents();
  expect(labels.length).toBeGreaterThanOrEqual(1);
  expect(labels).toEqual(labels.map((_, index) => `Сторінка ${index + 2}`));
  // Markers live inside the body section only, hidden from accessibility tools.
  expect(await page.evaluate(() => {
    const marker = document.querySelector(".document-page-break");
    return {
      part: marker?.parentElement?.getAttribute("data-part"),
      hidden: marker?.getAttribute("aria-hidden"),
      editable: marker?.getAttribute("contenteditable"),
    };
  })).toEqual({ part: "word/document.xml", hidden: "true", editable: "false" });
  await page.screenshot({ path: testInfo.outputPath("page-breaks-uk.png"), fullPage: true });
  // A zoom change re-measures the flow; markers stay between the same blocks.
  await page.getByText("Налаштування робочого простору", { exact: true }).click();
  await page.getByRole("combobox", { name: "Масштаб", exact: true }).selectOption("1.25");
  await expect(page.locator(".document-canvas .ProseMirror")).toHaveCSS("zoom", "1.25");
  await expect(label.first()).toBeVisible();
  expect(await label.allTextContents()).toEqual(labels);
  await page.getByText("Налаштування робочого простору", { exact: true }).click();
  // Labels follow the interface language without losing the document.
  await openNavigation(page);
  await page.getByRole("link", { name: "Профіль", exact: true }).click();
  await page.getByRole("combobox", { name: "Мова інтерфейсу" }).selectOption("en");
  await page.getByRole("button", { name: "Зберегти мову" }).click();
  await expect(page.getByText("Your language preference has been saved.", { exact: true })).toBeVisible();
  await openNavigation(page);
  await page.getByRole("link", { name: "Document workspace", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Editable document", exact: true })).toBeVisible();
  const english = page.locator(".document-page-break-label");
  await expect(english.first()).toBeVisible();
  const englishLabels = await english.allTextContents();
  expect(englishLabels).toEqual(englishLabels.map((_, index) => `Page ${index + 2}`));
  await page.screenshot({ path: testInfo.outputPath("page-breaks-en.png"), fullPage: true });
});
