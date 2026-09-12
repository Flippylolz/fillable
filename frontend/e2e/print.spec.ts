import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";
import { openUploadPanel } from "./navigation";

test("a clean document prints through a print-only frame and unavailable printing suggests a local save", async ({ page }, testInfo) => {
  testInfo.setTimeout(120000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const bytes = await readFile("/fixtures/upload.docx");
  const file = { name: "Друк-Їжак.docx", mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", buffer: bytes };
  const title = `Друк Їжака — ${Date.now()}`;
  await page.goto("/");
  await page.getByLabel("Логін", { exact: true }).fill("print@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill("Synthetic-browser-Їжак-2026");
  await page.getByRole("button", { name: "Увійти", exact: true }).click();
  await expect(page).toHaveURL(/\/documents$/);
  await openUploadPanel(page);
  await page.getByLabel("Файл DOCX", { exact: true }).setInputFiles(file);
  await page.getByLabel("Назва документа", { exact: true }).fill(title);
  await page.getByLabel("Зберегти як").selectOption("document");
  await page.getByRole("button", { name: "Завантажити та зберегти", exact: true }).click();
  const card = page.getByRole("article", { name: title });
  await expect(card).toBeVisible();
  await expect(card.getByText("Перевірку завершено", { exact: true })).toBeVisible({ timeout: 30000 });
  // The card link stretches over the cover; force skips Playwright's
  // hit-target refusal for the stretched overlay (see E09.14).
  await page.getByRole("article", { name: title }).locator(".library-document-cover").click({ force: true });
  await expect(page).toHaveURL(/\/editor\//);
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await expect(page.getByText("Редагування дозволено.")).toBeVisible();
  // Individual documents never offer save-to-documents; both kinds offer print.
  await expect(page.getByRole("button", { name: "Зберегти в документи", exact: true })).toHaveCount(0);
  // A clean document prints without creating a new revision.
  await page.getByRole("button", { name: "Друк", exact: true }).click();
  await expect(page.locator("iframe.print-frame")).toHaveCount(1);
  await expect(page.getByText(/Не вдалося відкрити друк у браузері/)).toHaveCount(0);
  // A clean print creates no revision: the save state stays "opened".
  await expect(page.getByText("Відкрито збережену версію.")).toBeVisible();
  const frameHtml = await page.evaluate(() => {
    const frame = document.querySelector("iframe.print-frame");
    return frame ? frame.outerHTML : "";
  });
  expect(frameHtml).toContain("aria-hidden");
  await page.screenshot({ path: testInfo.outputPath("print-workspace-uk.png"), fullPage: true });
  expect(errors).toEqual([]);
});
