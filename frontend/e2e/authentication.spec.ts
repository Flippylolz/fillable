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
    .getByLabel("Електронна пошта", { exact: true })
    .fill("browser@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill("incorrect");
  await page.getByRole("button", { name: "Увійти", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "Неправильна електронна пошта або пароль.",
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
