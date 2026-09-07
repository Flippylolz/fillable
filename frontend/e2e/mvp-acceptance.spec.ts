import { readFile, writeFile } from "node:fs/promises";
import { randomUUID, createHash } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";
import { manualSaving } from "./autosave-setting";

const email = process.env.FILLABLE_INITIAL_EMAIL ?? "library@example.test";
const password = process.env.FILLABLE_INITIAL_PASSWORD ?? "Synthetic-browser-Їжак-2026";

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value !== null && typeof value === "object") return `{${Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([key, item]) => `${JSON.stringify(key)}:${canonical(item)}`).join(",")}}`;
  return JSON.stringify(value);
}

async function retained(page: Page, identities: string[]) {
  const result = [];
  for (const id of identities) {
    const endpoint = `/api/documents/${id}`;
    const current = await (await page.request.get(`${endpoint}/content`)).json();
    const history = await (await page.request.get(`${endpoint}/versions`)).json();
    const versions = [];
    for (const entry of history.items) {
      const selected = `${endpoint}/versions/${entry.id}`;
      const document = (await (await page.request.get(`${selected}/content`)).json()).document;
      versions.push({ id: entry.id, number: entry.number, sha256: hash(await (await page.request.get(`${selected}/download`)).body()), model_sha256: hash(Buffer.from(canonical(document))) });
    }
    result.push({ id, current_version_id: current.resource.current_version_id, sha256: hash(await (await page.request.get(`${endpoint}/download`)).body()), model_sha256: hash(Buffer.from(canonical(current.document))), versions });
  }
  return result;
}

async function badge(page: Page, language: "uk" | "en") {
  const version = process.env.EXPECTED_APP_VERSION ?? "development";
  const badge = page.locator(".version-badge");
  await expect(badge).toHaveCount(1); await expect(badge).toBeVisible();
  await expect(badge).toHaveText(`version: ${version}`);
  await expect(badge).toHaveAttribute("aria-label", `${language === "uk" ? "Версія застосунку" : "Application version"} ${version}`);
  await expect(page.locator("html")).toHaveAttribute("lang", language);
}
async function download(page: Page, name: string) {
  const pending = page.waitForEvent("download");
  await page.getByRole("button", { name, exact: true }).click();
  return readFile((await (await pending).path())!);
}
const hash = (bytes: Buffer) => createHash("sha256").update(bytes).digest("hex");

test("four-page bilingual journey saves a reviewed template, edits its independent copy and preserves it through source restoration", async ({ page }, info) => {
  test.setTimeout(120000);
  const original = await readFile("/fixtures/upload.docx");
  const title = `Шаблон заяви Ґанни Їжак для перевірки незалежного документа — ${randomUUID().slice(0, 8)}`;
  const copyTitle = `Незалежна заява Єви — ${info.project.name}`;
  const label = "Електронна пошта відповідальної особи для узгодження документів українською мовою";
  const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByLabel("Пароль", { exact: true })).toBeVisible(); await badge(page, "uk");
  await page.getByLabel("Електронна пошта", { exact: true }).fill(email);
  await page.getByLabel("Пароль", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Увійти", exact: true }).click();
  await expect(page).toHaveURL(/\/documents$/); await badge(page, "uk");
  await page.getByLabel("Файл DOCX", { exact: true }).setInputFiles({ name: "Заява-Ґанни.docx", mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", buffer: original });
  await page.getByLabel("Назва документа", { exact: true }).fill(title);
  await page.getByRole("combobox", { name: "Зберегти як", exact: true }).selectOption("template");
  await page.getByRole("button", { name: "Завантажити та зберегти", exact: true }).click();
  const card = page.getByRole("article", { name: title, exact: true });
  await expect(card.getByText("Перевірку завершено", { exact: true })).toBeVisible({ timeout: 30000 });
  await card.getByRole("link", { name: "Відкрити", exact: true }).click();
  await expect(page.getByText("Редагування дозволено.", { exact: true })).toBeVisible(); await badge(page, "uk");
  await manualSaving(page);
  const templateId = page.url().split("/").at(-1)!;
  await page.getByText("Перевірка полів", { exact: true }).click();
  const proposal = page.getByRole("article", { name: "Пропозиція поля: ЕЛЕКТРОННА_ПОШТА", exact: true }).first();
  await proposal.getByLabel("Назва поля", { exact: true }).fill(label);
  await proposal.getByRole("combobox", { name: "Пов’язати значення з", exact: true }).selectOption("");
  await proposal.getByRole("button", { name: "Прийняти", exact: true }).click();
  await page.getByRole("textbox", { name: `Значення поля: ${label}`, exact: true }).fill("їжак@example.test");
  await page.getByRole("textbox", { name: "Значення поля: ПІБ клієнта", exact: true }).first().fill("Ґанна Їжак 🙂");
  await page.getByText("Перевірка полів", { exact: true }).click();
  await page.getByRole("button", { name: "Зберегти документ", exact: true }).click();
  await expect(page.getByText("Усі зміни документа збережено.", { exact: true })).toBeVisible();
  const template = await (await page.request.get(`/api/documents/${templateId}/content`)).json();
  expect(template.document.attrs.review.items).toEqual(expect.arrayContaining([expect.objectContaining({ label, decision: "accepted" })]));
  const templateBytes = await download(page, "Завантажити збережений DOCX");
  expect(hash(templateBytes)).toBe(template.resource.digest); expect(templateBytes).not.toEqual(original);
  await page.screenshot({ path: info.outputPath("acceptance-reviewed-template-uk.png"), fullPage: true });
  await page.getByRole("article").filter({ has: page.getByRole("textbox", { name: `Значення поля: ${label}`, exact: true }) }).screenshot({ path: info.outputPath("acceptance-long-label-uk.png") });

  await page.getByRole("link", { name: "Профіль", exact: true }).click(); await badge(page, "uk");
  await expect(page.locator(".profile-storage dd").nth(2)).toHaveText(/^\d+,\d{1,2}\s+ГБ$/);
  await page.getByRole("combobox", { name: "Мова інтерфейсу", exact: true }).selectOption("en");
  await page.getByRole("button", { name: "Зберегти мову", exact: true }).click();
  await expect(page.getByText("Your language preference has been saved.", { exact: true })).toBeVisible(); await badge(page, "en");
  await expect(page.locator(".profile-storage dd").nth(2)).toHaveText(/^\d+\.\d{1,2}\s+GB$/);
  await page.getByRole("link", { name: "Document library", exact: true }).click(); await badge(page, "en");
  await page.getByRole("tab", { name: "Templates", exact: true }).click();
  await card.getByRole("button", { name: "Use template", exact: true }).click();
  await card.getByRole("textbox", { name: "New document title", exact: true }).fill(copyTitle);
  await card.getByRole("button", { name: "Create and open document", exact: true }).click();
  await expect(page.getByRole("heading", { name: copyTitle, exact: true })).toBeVisible(); await badge(page, "en");
  await expect(page.getByText("Editing enabled.", { exact: true })).toBeVisible(); await manualSaving(page);
  const copyId = page.url().split("/").at(-1)!; expect(copyId).not.toBe(templateId);
  const mail = page.getByRole("textbox", { name: `Field value: ${label}`, exact: true });
  await expect(mail).toHaveValue("їжак@example.test");
  const native = page.getByRole("textbox", { name: "Field value: ПІБ клієнта", exact: true }).first();
  await expect(native).toHaveValue("Ґанна Їжак 🙂");
  expect(await download(page, "Download saved DOCX")).toEqual(templateBytes);
  await native.fill("Єва Ґанок 🙂"); await mail.fill("єва@example.test");
  await page.getByRole("button", { name: "Save document", exact: true }).click();
  await expect(page.getByText("All document changes saved.", { exact: true })).toBeVisible();
  const copy = await (await page.request.get(`/api/documents/${copyId}/content`)).json();
  const copyBytes = await download(page, "Download saved DOCX"); expect(hash(copyBytes)).toBe(copy.resource.digest);
  expect(copyBytes).not.toEqual(templateBytes);
  expect(await (await page.request.get(`/api/documents/${templateId}/download`)).body()).toEqual(templateBytes);
  await page.reload(); await expect(mail).toHaveValue("єва@example.test"); await expect(native).toHaveValue("Єва Ґанок 🙂"); await badge(page, "en");
  await page.getByRole("button", { name: "Version history", exact: true }).click();
  await page.getByRole("button", { name: /^Version 1/ }).click();
  await expect(page.getByRole("heading", { name: "Version 1", exact: true })).toBeVisible();
  expect(await download(page, "Download this DOCX revision")).toEqual(templateBytes);
  await page.screenshot({ path: info.outputPath("acceptance-copy-history-en.png"), fullPage: true });
  await page.getByRole("button", { name: "Return to editing", exact: true }).click();

  await page.getByRole("link", { name: "Document library", exact: true }).click();
  await page.getByRole("tab", { name: "Templates", exact: true }).click();
  await card.getByRole("link", { name: "Open", exact: true }).click();
  await expect(page.getByText("Editing enabled.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Version history", exact: true }).click();
  await page.getByRole("button", { name: /^Version 1/ }).click();
  await expect(page.getByRole("heading", { name: "Version 1", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Restore as a new revision", exact: true }).click();
  await expect(page.getByRole("button", { name: "Version history", exact: true })).toBeVisible();
  expect(await download(page, "Download saved DOCX")).toEqual(original);
  const templateHistory = await (await page.request.get(`/api/documents/${templateId}/versions`)).json();
  const copyHistory = await (await page.request.get(`/api/documents/${copyId}/versions`)).json();
  expect(templateHistory.items.map((item: { number: number }) => item.number)).toEqual([3, 2, 1]);
  expect(copyHistory.items.map((item: { number: number }) => item.number)).toEqual([2, 1]);
  expect(await (await page.request.get(`/api/documents/${copyId}/download`)).body()).toEqual(copyBytes);
  expect((await (await page.request.get(`/api/documents/${copyId}`)).json()).current_version_id).toBe(copy.resource.current_version_id);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByLabel("Password", { exact: true })).toBeVisible(); await badge(page, "en");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("link", { name: "Profile", exact: true }).click(); await badge(page, "en");
  await page.getByRole("combobox", { name: "Interface language", exact: true }).selectOption("uk");
  await page.getByRole("button", { name: "Save language", exact: true }).click();
  await expect(page.getByRole("link", { name: "Профіль", exact: true })).toBeVisible();
  expect(errors).toEqual([]);
  await writeFile(info.outputPath("acceptance-state.json"), JSON.stringify({ version: process.env.EXPECTED_APP_VERSION ?? "development", resources: await retained(page, [templateId, copyId]) }));
});
