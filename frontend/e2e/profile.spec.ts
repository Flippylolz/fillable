import { expect, test, type Page } from "@playwright/test";

const originalPassword = "Synthetic-browser-Їжак-2026";
const nextPassword = "Changed-profile-Ґанна-2026";
async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Логін", { exact: true }).fill("profile@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill(originalPassword);
  await page.getByRole("button", { name: "Увійти", exact: true }).click();
  await page.getByRole("link", { name: "Профіль", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Профіль", exact: true })).toBeVisible();
}
async function password(page: Page, current: string, next: string) {
  await page.getByLabel("Поточний пароль", { exact: true }).fill(current);
  await page.getByLabel("Новий пароль", { exact: true }).fill(next);
  await page.getByLabel("Підтвердьте новий пароль", { exact: true }).fill(next);
  await page.getByRole("button", { name: "Змінити пароль", exact: true }).click();
}

test("profile edits persist, passwords require current credentials and revoke another browser", async ({ page, browser }, testInfo) => {
  await login(page);
  await expect(page.getByLabel("Логін", { exact: true })).toHaveAttribute("readonly", "");
  await expect(page.getByRole("heading", { name: "Сховище", exact: true })).toBeVisible();
  const peer = await browser.newContext({ baseURL: new URL(page.url()).origin });
  try {
    const other = await peer.newPage();
    await login(other);
    const name = "Ґанна Єва Їжак — український профіль із довгим ім’ям";
    await page.getByLabel("Ім’я для відображення", { exact: true }).fill(`  ${name}  `);
    await page.getByRole("button", { name: "Зберегти ім’я", exact: true }).click();
    await expect(page.getByText("Ім’я для відображення збережено.", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Ім’я для відображення", { exact: true })).toHaveValue(name);
    await page.reload();
    await expect(page.getByLabel("Ім’я для відображення", { exact: true })).toHaveValue(name);
    await password(page, "incorrect", nextPassword);
    await expect(page.getByRole("alert")).toHaveText("Поточний пароль неправильний.");
    await expect(page.getByLabel("Новий пароль", { exact: true })).toHaveValue(nextPassword);
    // The ten-character minimum message renders from the catalogs (F1/E10.1).
    await password(page, originalPassword, "short-9ch");
    await expect(page.getByRole("alert")).toHaveText("Новий пароль має містити щонайменше 10 символів.");
    await password(page, originalPassword, nextPassword);
    await expect(page.getByText("Пароль змінено. Інші сеанси завершено.", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Поточний пароль", { exact: true })).toHaveValue("");
    await other.reload();
    await expect(other.getByRole("button", { name: "Увійти", exact: true })).toBeEnabled();
    await page.screenshot({ path: testInfo.outputPath("profile.png"), fullPage: true });
    // Restore only this explicitly provisioned synthetic fixture for the next viewport.
    await page.getByLabel("Ім’я для відображення", { exact: true }).fill("Тест профілю");
    await page.getByRole("button", { name: "Зберегти ім’я", exact: true }).click();
    await expect(page.getByText("Ім’я для відображення збережено.", { exact: true })).toBeVisible();
    await password(page, nextPassword, originalPassword);
    await expect(page.getByText("Пароль змінено. Інші сеанси завершено.", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Вийти", exact: true }).click();
    await expect(page.getByRole("button", { name: "Увійти", exact: true })).toBeEnabled();
    await login(page);
    await page.getByRole("button", { name: "Вийти", exact: true }).click();
  } finally {
    await peer.close();
  }
});

test("language saves preserve drafts and restore the account preference across browsers", async ({ page, browser }, testInfo) => {
  await login(page);
  const initialUsage = await (await page.request.get("/api/storage/usage")).json();
  await page.getByLabel("Ім’я для відображення", { exact: true }).fill("Незбережена Ґанна");
  await page.getByLabel("Новий пароль", { exact: true }).fill(nextPassword);
  await page.route("**/api/profile/language", route => route.fulfill({
    status: 503, contentType: "application/json", body: JSON.stringify({ error: { code: "dependencies_unavailable", parameters: {} } }),
  }));
  await page.getByRole("combobox", { name: "Мова інтерфейсу" }).selectOption("en");
  await page.getByRole("button", { name: "Зберегти мову" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Мова інтерфейсу" })).toHaveValue("uk");
  await expect(page.locator("html")).toHaveAttribute("lang", "uk");
  await page.unroute("**/api/profile/language");
  await page.getByRole("combobox", { name: "Мова інтерфейсу" }).selectOption("en");
  await page.getByRole("button", { name: "Зберегти мову" }).click();
  await expect(page.getByText("Your language preference has been saved.", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Display name", { exact: true })).toHaveValue("Незбережена Ґанна");
  await expect(page.getByLabel("New password", { exact: true })).toHaveValue(nextPassword);
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  expect(await (await page.request.get("/api/storage/usage")).json()).toEqual(initialUsage);
  await page.screenshot({ path: testInfo.outputPath("profile-language-en.png"), fullPage: true });
  await page.reload();
  await expect(page.getByRole("combobox", { name: "Interface language" })).toHaveValue("en");
  await expect(page.getByLabel("Display name", { exact: true })).toHaveValue("Тест профілю");
  const peer = await browser.newContext({ baseURL: new URL(page.url()).origin, locale: "en-US" });
  try {
    const other = await peer.newPage();
    await other.goto("/");
    await expect(other.locator("html")).toHaveAttribute("lang", "uk");
    await other.getByLabel("Логін", { exact: true }).fill("profile@example.test");
    await other.getByLabel("Пароль", { exact: true }).fill(originalPassword);
    await other.getByRole("button", { name: "Увійти", exact: true }).click();
    await other.getByRole("link", { name: "Profile", exact: true }).click();
    await expect(other.getByRole("combobox", { name: "Interface language" })).toHaveValue("en");
    await page.getByRole("combobox", { name: "Interface language" }).selectOption("uk");
    await page.getByRole("button", { name: "Save language" }).click();
    await expect(page.getByText("Мову інтерфейсу збережено.", { exact: true })).toBeVisible();
    // The peer still renders its old English preference until authenticated reload.
    await expect(other.locator("html")).toHaveAttribute("lang", "en");
    await other.reload();
    await expect(other.getByRole("combobox", { name: "Мова інтерфейсу" })).toHaveValue("uk");
  } finally { await peer.close(); }
});
