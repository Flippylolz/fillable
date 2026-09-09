import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

async function open(page: Page) {
  await page.goto("/");
  await expect(page.getByLabel("Пароль", { exact: true })).toBeVisible();
  const anonymous = await (await page.request.get("/api/auth/session")).json();
  const response = await page.request.post("/api/auth/login", {
    headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": anonymous.csrf_token },
    data: { login: "review@example.test", password: "Synthetic-browser-Їжак-2026" },
  });
  expect(response.status()).toBe(200); const session = await response.json();
  const upload = await page.request.post("/api/documents", {
    headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": session.csrf_token,
      "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Idempotency-Key": randomUUID(),
      "X-Upload-Metadata": Buffer.from(JSON.stringify({ kind: "document", filename: "Скасування-Їжак.docx", title: "Скасування Ґанни" })).toString("base64") },
    data: await readFile("/fixtures/upload.docx"),
  });
  expect(upload.status()).toBe(201); const resource = await upload.json();
  const endpoint = `/api/documents/${resource.id}`;
  await page.goto(`/editor/${resource.id}`);
  await expect(page.getByText("Редагування дозволено.", { exact: true })).toBeVisible();
  await expect(page.locator(".workspace-discovery")).toContainText("Перевірку завершено", { timeout: 20000 });
  return { endpoint };
}
const value = (page: Page) => page.getByRole("textbox", { name: "Значення поля: ПІБ клієнта", exact: true }).first();

test("undo and redo reflect document history across autosave and restore", async ({ page }) => {
  test.setTimeout(90000);
  const { endpoint } = await open(page);
  const undo = page.getByRole("button", { name: "Скасувати", exact: true });
  const redo = page.getByRole("button", { name: "Повторити", exact: true });
  await expect(undo).toBeDisabled();
  await expect(redo).toBeDisabled();
  await value(page).fill("Історія-Їжак");
  await expect(undo).toBeEnabled();
  await expect(redo).toBeDisabled();
  // A completed autosave must not change the buttons' availability.
  await expect(page.getByText("Усі зміни документа збережено.", { exact: true })).toBeVisible({ timeout: 15000 });
  await expect(undo).toBeEnabled();
  await expect(redo).toBeDisabled();
  await undo.click();
  await expect(undo).toBeDisabled();
  await expect(redo).toBeEnabled();
  await redo.click();
  await expect(undo).toBeEnabled();
  await expect(redo).toBeDisabled();
  // The undone/redone states autosave too; wait until the workspace is settled.
  await expect(page.getByText("Усі зміни документа збережено.", { exact: true })).toBeVisible({ timeout: 15000 });
  // Restoring a revision remounts the editor with an empty history.
  const before = (await (await page.request.get(`${endpoint}/versions`)).json()).items.length;
  await page.getByRole("button", { name: "Історія версій", exact: true }).click();
  const panel = page.getByRole("region", { name: "Історія версій", exact: true });
  await panel.getByRole("button", { name: /^Версія 1/ }).click();
  await expect(page.getByRole("textbox", { name: "Історична версія документа лише для читання", exact: true })).toBeVisible();
  page.once("dialog", dialog => dialog.accept());
  await panel.getByRole("button", { name: "Відновити як нову версію", exact: true }).click();
  await expect.poll(async () => (await (await page.request.get(`${endpoint}/versions`)).json()).items.length, {
    timeout: 15000,
  }).toBe(before + 1);
  await expect(undo).toBeDisabled();
  await expect(redo).toBeDisabled();
});
