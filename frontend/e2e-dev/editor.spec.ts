import { expect, test } from "@playwright/test";

test("corpus fields synchronize, navigate and survive locale changes", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/prototype.html");
  const editor = page.getByRole("textbox", { name: "Редагований документ" });
  const originalEditor = await editor.elementHandle();
  await expect(page.locator(".document-field")).toHaveCount(5);
  const clients = page.getByRole("textbox", {
    name: "Значення поля: ПІБ клієнта",
    exact: true,
  });
  await expect(clients).toHaveCount(2);
  await clients.first().fill("Ґанна Їжак");
  await expect(clients.nth(1)).toHaveValue("Ґанна Їжак");
  await expect(
    page.locator('.document-field[data-field-key="ПІБ_КЛІЄНТА"]').first(),
  ).toHaveText("Ґанна Їжак");
  await page
    .getByRole("button", { name: "Перейти до поля: ПІБ клієнта", exact: true })
    .last()
    .click();
  await expect(editor).toBeFocused();
  await page.keyboard.insertText("Єва Ільїна");
  await expect(clients.first()).toHaveValue("Єва Ільїна");
  await expect(clients.last()).toHaveValue("Єва Ільїна");

  await page.getByRole("textbox", { name: "Назва нового поля" }).fill("Пошта");
  const email = page
    .locator(".document-canvas td p")
    .filter({ hasText: "{{ЕЛЕКТРОННА_ПОШТА}}" });
  await email.click();
  await page.keyboard.press("Home");
  await page.keyboard.press("Shift+End");
  expect(await page.evaluate(() => window.getSelection()?.toString())).toBe(
    "{{ЕЛЕКТРОННА_ПОШТА}}",
  );
  await page
    .getByRole("button", { name: "Створити поле з виділення", exact: true })
    .click();
  expect(errors).toEqual([]);
  const mail = page.getByRole("textbox", {
    name: "Значення поля: Пошта",
    exact: true,
  });
  await expect(mail).toHaveValue("{{ЕЛЕКТРОННА_ПОШТА}}");
  await mail.fill("їжак@example.test");
  await expect(
    page.locator(".document-field").filter({ hasText: "їжак@example.test" }),
  ).toHaveCount(1);
  await page.getByRole("button", { name: "English", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "Editable document" }),
  ).toBeVisible();
  expect(await originalEditor!.evaluate((el) => el.isConnected)).toBe(true);
  await expect(
    page.getByRole("textbox", { name: "Field value: Пошта", exact: true }),
  ).toHaveValue("їжак@example.test");
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "Field value: Пошта", exact: true }),
  ).toHaveValue("{{ЕЛЕКТРОННА_ПОШТА}}");
  await page.getByRole("button", { name: "Redo", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "Field value: Пошта", exact: true }),
  ).toHaveValue("їжак@example.test");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export DOCX", exact: true }).click();
  await (await download).saveAs("/tmp/fillable-dev-results/created-field.docx");
  await page.getByRole("button", { name: "Reopen exported DOCX", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Field value: Пошта", exact: true })).toHaveValue("їжак@example.test");
  await expect(page.locator(".document-field")).toHaveCount(6);
  expect(errors).toEqual([]);
  await page.screenshot({
    path: "/tmp/fillable-dev-results/editor-desktop.png",
    fullPage: true,
  });
});

test("surrounding edits, control removal and undo survive DOCX export and reopen", async ({
  page,
}) => {
  await page.goto("/prototype.html");
  await page.getByRole("button", { name: "English", exact: true }).click();
  const editor = page.getByRole("textbox", { name: "Editable document" });
  await expect(editor).toBeVisible();
  const downloadOriginal = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export DOCX", exact: true }).click();
  await (
    await downloadOriginal
  ).saveAs("/tmp/fillable-dev-results/unchanged.docx");
  const firstParagraph = editor
    .locator('section[data-part="word/document.xml"] > p')
    .first();
  await firstParagraph.click();
  await page.keyboard.press("Home");
  await page.keyboard.insertText("Ґанна — ");
  await page.keyboard.press("Enter");
  const clients = page.getByRole("textbox", {
    name: "Field value: ПІБ клієнта",
    exact: true,
  });
  await clients.first().fill("Єва Їжак");
  await expect(clients.last()).toHaveValue("Єва Їжак");
  const remove = page.getByRole("button", {
    name: "Remove field: ПІБ клієнта",
    exact: true,
  });
  await remove.first().click();
  await expect(clients).toHaveCount(1);
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(clients).toHaveCount(2);
  await page.getByRole("button", { name: "Redo", exact: true }).click();
  await expect(clients).toHaveCount(1);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export DOCX", exact: true }).click();
  await (await download).saveAs("/tmp/fillable-dev-results/edited.docx");
  await page
    .getByRole("button", { name: "Reopen exported DOCX", exact: true })
    .click();
  await expect(clients).toHaveCount(1);
  await expect(clients).toHaveValue("Єва Їжак");
  await expect(editor).toContainText("Ґанна — ");
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.screenshot({
    path: "/tmp/fillable-dev-results/reopened-desktop.png",
    fullPage: true,
  });
});
