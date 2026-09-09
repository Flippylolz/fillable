import { expect, test } from '@playwright/test';

test('Ukrainian default and real same-origin API', async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('lang', 'uk');
  await expect(page.getByRole('heading', { name: 'Fillable' })).toBeVisible();
  await expect(page.getByRole('status')).toHaveText('З’єднання із сервером встановлено');
  expect((await request.get('/api/ready')).ok()).toBeTruthy();
  // Conventional favicon fallbacks resolve for older clients and tools (F8).
  const ico = await request.get('/favicon.ico');
  expect(ico.ok()).toBe(true);
  expect(ico.headers()['content-type']).toContain('image');
  expect((await ico.body()).subarray(0, 4)).toEqual(Buffer.from([0, 0, 1, 0]));
  const png = await request.get('/favicon.png');
  expect(png.ok()).toBe(true);
  expect(png.headers()['content-type']).toContain('image/png');
  const shell = await request.get('/');
  expect(await shell.text()).toContain('/favicon.ico');
  expect(errors).toEqual([]);
  await page.screenshot({ path: `test-results/shell-${test.info().project.name}.png`, fullPage: true });
});

test('failed connection offers a working retry', async ({ page }) => {
  let fail = true;
  await page.route('**/api/health', route => fail ? route.abort() : route.continue());
  await page.goto('/');
  await expect(page.getByRole('status')).toHaveText('Не вдалося з’єднатися із сервером');
  fail = false;
  await page.getByRole('button', { name: 'Спробувати знову' }).click();
  await expect(page.getByRole('status')).toHaveText('З’єднання із сервером встановлено');
});
