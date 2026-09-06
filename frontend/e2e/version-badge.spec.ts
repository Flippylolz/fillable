import { expect, test } from '@playwright/test';

test('build version remains fixed, theme independent and click-through', async ({ page, context }) => {
  let fail = true;
  await page.route('**/api/health', route => fail ? route.abort() : route.continue());
  await page.goto('/');
  const version = process.env.EXPECTED_APP_VERSION ?? 'development';
  const badge = page.locator('.version-badge');
  await expect(badge).toHaveCount(1);
  await expect(badge).toHaveText(`version: ${version}`);
  await expect(badge).toHaveAttribute('aria-label', `Версія застосунку ${version}`);
  const button = page.getByRole('button', { name: 'Спробувати знову' });
  await expect(button).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(button).toBeFocused();
  await page.keyboard.press('Tab');
  expect(await badge.evaluate(el => el.contains(document.activeElement))).toBe(false);

  // Stress host-theme inline-code rules without adding product-only test controls.
  await page.addStyleTag({ content: 'body { min-height: 200vh; } code { background: red; color: red; padding: 20px; border: 8px solid red; font-family: serif; }' });
  const original = await badge.boundingBox();
  for (const colorScheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme });
    await page.evaluate(() => window.scrollTo(0, 400));
    expect(await badge.boundingBox()).toEqual(original);
    const styles = await badge.evaluate(el => {
      const outer = getComputedStyle(el);
      const code = getComputedStyle(el.querySelector('code')!);
      return { color: outer.color, background: outer.backgroundColor, font: code.fontFamily, codeColor: code.color, codeBackground: code.backgroundColor, padding: code.padding, pointer: code.pointerEvents };
    });
    expect(styles.color).toBe('rgb(139, 148, 158)');
    expect(styles.background).toBe('rgba(22, 27, 34, 0.85)');
    expect(styles.codeColor).toBe(styles.color);
    expect(styles.codeBackground).toBe('rgba(0, 0, 0, 0)');
    expect(styles.font).toContain('monospace');
    expect(styles.padding).toBe('0px');
    expect(styles.pointer).toBe('none');
  }
  const client = await context.newCDPSession(page);
  await client.send('Emulation.setSafeAreaInsetsOverride', { insets: { right: 24, bottom: 30 } });
  await expect(badge).toHaveCSS('right', '24px');
  await expect(badge).toHaveCSS('bottom', '74px');
  await client.send('Emulation.setSafeAreaInsetsOverride', { insets: { right: 0, bottom: 0 } });
  await expect(badge).toHaveCSS('bottom', '44px');
  const rect = (await badge.boundingBox())!;
  await button.evaluate((el, box) => Object.assign(el.style, {
    position: 'fixed', left: `${box.x}px`, top: `${box.y}px`, width: `${box.width}px`, height: `${box.height}px`, margin: '0', zIndex: '19',
  }), rect);
  fail = false;
  if (test.info().project.name === 'mobile') await page.touchscreen.tap(rect.x + rect.width / 2, rect.y + rect.height / 2);
  else await page.mouse.click(rect.x + rect.width / 2, rect.y + rect.height / 2);
  await expect(page.getByRole('status')).toHaveText('З’єднання із сервером встановлено');
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `test-results/badge-${test.info().project.name}.png` });
});
