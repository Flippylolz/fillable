import { expect, test, type Page } from "@playwright/test";

const originalPassword = "Synthetic-browser-Їжак-2026";
const nextPassword = "Changed-profile-Ґанна-2026";
async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Електронна пошта", { exact: true }).fill("profile@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill(originalPassword);
  await page.getByRole("button", { name: "Увійти", exact: true }).click();
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
  await expect(page.getByLabel("Електронна пошта", { exact: true })).toHaveAttribute("readonly", "");
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
