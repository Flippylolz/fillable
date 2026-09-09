import { expect, test } from "@playwright/test";

test("local login rotates a cookie, restores language across refresh, and logout revokes it", async ({
  page,
  context,
}, testInfo) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Увійти", exact: true }),
  ).toBeEnabled();
  const initial = (await context.cookies()).find(
    (cookie) => cookie.name === "fillable_session_v1",
  )!;
  await page
    .getByLabel("Логін", { exact: true })
    .fill(" BROWSER-USER ");
  await page.getByLabel("Пароль", { exact: true }).fill("incorrect");
  await page.getByRole("button", { name: "Увійти", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "Неправильний логін або пароль.",
  );
  await page
    .getByLabel("Пароль", { exact: true })
    .fill("Synthetic-browser-Їжак-2026");
  await page.getByRole("button", { name: "Увійти", exact: true }).click();
  await expect(
    page.getByText("Signed in as Тестовий користувач."),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("signed-in.png"),
    fullPage: true,
  });
  const authenticated = (await context.cookies()).find(
    (cookie) => cookie.name === "fillable_session_v1",
  )!;
  expect(authenticated.value).not.toBe(initial.value);
  expect(authenticated.httpOnly).toBe(true);
  expect(authenticated.sameSite).toBe("Strict");
  expect(authenticated.secure).toBe(false);
  const usageResponse = await page.request.get("/api/storage/usage");
  expect(usageResponse.status()).toBe(200);
  expect(usageResponse.headers()["cache-control"]).toBe("no-store");
  const usage = await usageResponse.json();
  expect(usage.limit_bytes).toBe(1073741824);
  expect(usage.reserved_bytes).toBe(0);
  expect(usage.available_bytes).toBe(usage.limit_bytes - usage.used_bytes);
  expect(usage.over_limit).toBe(false);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Sign out", exact: true }),
  ).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const badOrigin = await page.request.post("/api/auth/logout", {
    headers: { Origin: "http://gateway:8180", "X-CSRF-Token": "wrong" },
  });
  expect(badOrigin.status()).toBe(403);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeEnabled();
  const stale = await page.request.get("/api/auth/session", {
    headers: { Cookie: `fillable_session_v1=${authenticated.value}` },
  });
  expect((await stale.json()).user).toBeNull();
  expect((await page.request.get("/api/storage/usage")).status()).toBe(401);
  await expect(page.locator("form")).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("signed-out.png"),
    fullPage: true,
  });
});

test.beforeEach(async ({ context }) => {
  await context.route("**/api/**", async route => {
    const request = route.request();
    if (request.method() !== "POST") return route.continue();
    const response = await route.fetch({ headers: { ...request.headers(), origin: new URL(request.url()).origin } });
    return route.fulfill({ response });
  });
});

test("empty sign-in shows catalog feedback and the credentials alert stays inside the card", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Увійти", exact: true }),
  ).toBeEnabled();
  await expect(page.getByLabel("Логін", { exact: true })).not.toHaveAttribute(
    "required",
  );
  await expect(page.getByLabel("Пароль", { exact: true })).not.toHaveAttribute(
    "required",
  );
  const card = page.locator("form");
  const empty = await card.boundingBox();
  await page.getByRole("button", { name: "Увійти", exact: true }).click();
  await expect(
    page.getByText("Введіть логін.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Введіть пароль.", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("login-empty-uk.png"),
    fullPage: true,
  });
  await page.getByLabel("Логін", { exact: true }).fill("browser-user");
  await page.getByLabel("Пароль", { exact: true }).fill("incorrect");
  const settled = await card.boundingBox();
  // The reserved feedback row keeps the card geometry stable when alerts appear.
  expect(settled!.y).toBeCloseTo(empty!.y, 0);
  expect(settled!.height).toBeCloseTo(empty!.height, 0);
  await page.getByRole("button", { name: "Увійти", exact: true }).click();
  const alert = page.getByRole("alert");
  await expect(alert).toHaveText("Неправильний логін або пароль.");
  await expect(alert.locator("xpath=ancestor::form")).toBeVisible();
  expect((await card.boundingBox())!.height).toBeCloseTo(empty!.height, 0);
  await page.screenshot({
    path: testInfo.outputPath("login-alert-uk.png"),
    fullPage: true,
  });
  // Signing in applies the account language; the signed-out form follows it.
  await page.getByLabel("Пароль", { exact: true }).fill("Synthetic-browser-Їжак-2026");
  await page.getByRole("button", { name: "Увійти", exact: true }).click();
  await expect(
    page.getByText("Signed in as Тестовий користувач."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeEnabled();
  const loginBox = page.getByLabel("Login", { exact: true });
  await loginBox.fill("");
  // The fill must land on the mounted form, not a node from the sign-out transition.
  await expect(loginBox).toHaveValue("");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Enter your login name.", { exact: true })).toBeVisible();
  await expect(page.getByText("Enter your password.", { exact: true })).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("login-empty-en.png"),
    fullPage: true,
  });
});
