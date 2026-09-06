import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { expect, test } from "@playwright/test";

test("library uploads both kinds, retries safely, and keeps drafts across a language change", async ({ page }, testInfo) => {
  const bytes = await readFile("/fixtures/upload.docx");
  const file = { name: "Заява-Їжак.docx", mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", buffer: bytes };
  const templateTitle = `Шаблон Ґанни — ${testInfo.project.name}`;
  const documentTitle = `Окрема заява Їжака — ${testInfo.project.name}`;
  await page.goto("/");
  await page.getByLabel("Електронна пошта", { exact: true }).fill("library@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill("Synthetic-browser-Їжак-2026");
  await page.getByRole("button", { name: "Увійти", exact: true }).click();
  await expect(page).toHaveURL(/\/documents$/);
  await expect(page.getByRole("heading", { name: "Бібліотека документів" })).toBeVisible();
  let fail = true;
  const keys: string[] = [];
  await page.route("**/api/documents", async route => {
    if (route.request().method() === "POST") {
      keys.push(route.request().headers()["idempotency-key"]);
      if (fail) { fail = false; await route.abort(); return; }
    }
    await route.continue();
  });
  await page.getByLabel("Файл DOCX", { exact: true }).setInputFiles(file);
  await page.getByLabel("Назва документа", { exact: true }).fill(templateTitle);
  await page.getByRole("button", { name: "Завантажити та зберегти", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByLabel("Назва документа", { exact: true })).toHaveValue(templateTitle);
  await page.getByRole("button", { name: "Завантажити та зберегти", exact: true }).click();
  await expect(page.getByRole("article", { name: templateTitle })).toBeVisible();
  expect(keys[0]).toBe(keys[1]);
  await expect(page.getByLabel("Файл DOCX", { exact: true })).toHaveValue("");
  await page.screenshot({ path: testInfo.outputPath("library-uk.png"), fullPage: true });

  await page.getByLabel("Файл DOCX", { exact: true }).setInputFiles(file);
  await page.getByLabel("Назва документа", { exact: true }).fill(documentTitle);
  await page.getByRole("combobox", { name: "Зберегти як", exact: true }).selectOption("document");
  await page.getByRole("link", { name: "Профіль", exact: true }).click();
  await page.getByRole("combobox", { name: "Мова інтерфейсу" }).selectOption("en");
  await page.getByRole("button", { name: "Зберегти мову" }).click();
  await expect(page.getByText("Your language preference has been saved.", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Document library", exact: true }).click();
  await expect(page.getByLabel("Document title", { exact: true })).toHaveValue(documentTitle);
  await expect(page.getByRole("combobox", { name: "Save as", exact: true })).toHaveValue("document");
  await page.getByRole("button", { name: "Upload and save", exact: true }).click();
  await expect(page.getByRole("article", { name: documentTitle })).toBeVisible();
  expect(keys[2]).not.toBe(keys[1]);
  await expect(page.getByRole("tab", { name: "Documents", exact: true })).toHaveAttribute("aria-selected", "true");
  await page.screenshot({ path: testInfo.outputPath("library-en.png"), fullPage: true });
  await page.reload();
  await page.getByRole("tab", { name: "Documents", exact: true }).click();
  await expect(page.getByRole("article", { name: documentTitle })).toBeVisible();
  const list = await (await page.request.get("/api/documents?kind=document")).json();
  const saved = list.items.find((item: { title: string }) => item.title === documentTitle);
  expect(saved.digest).toBe(createHash("sha256").update(bytes).digest("hex"));
  expect(saved.size_bytes).toBe(bytes.length);
  expect(saved.processing_status).toBe("not_started");
  await page.getByRole("link", { name: "Profile", exact: true }).click();
  await page.getByRole("combobox", { name: "Interface language" }).selectOption("uk");
  await page.getByRole("button", { name: "Save language" }).click();
  await expect(page.getByText("Мову інтерфейсу збережено.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Вийти", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
});
