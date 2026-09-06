import { expect, test } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';

test('source reload reaches the open browser and API', async ({ page, request }) => {
  const frontend = '/workspace/frontend/App.tsx';
  const backend = '/workspace/backend/main.py';
  const originalFrontend = await readFile(frontend, 'utf8');
  const originalBackend = await readFile(backend, 'utf8');
  await page.goto('/');
  await expect(page.getByRole('status')).toHaveText('З’єднання із сервером встановлено');
  try {
    await writeFile(frontend, originalFrontend.replace('<main>', '<main data-development-probe="updated">'));
    await expect(page.locator('main')).toHaveAttribute('data-development-probe', 'updated');
    await writeFile(backend, originalBackend + '\n\n@app.get("/api/development-probe")\ndef development_probe():\n    return {"probe": "updated"}\n');
    await expect.poll(async () => {
      try { return (await request.get('/api/development-probe')).status(); }
      catch { return 0; }
    }, { timeout: 20000 }).toBe(200);
    expect(await (await request.get('/api/development-probe')).json()).toEqual({ probe: 'updated' });
  } finally {
    await writeFile(frontend, originalFrontend);
    await writeFile(backend, originalBackend);
  }
  await expect(page.locator('main')).not.toHaveAttribute('data-development-probe');
  await expect.poll(async () => {
    try { return (await request.get('/api/development-probe')).status(); }
    catch { return 0; }
  }, { timeout: 20000 }).toBe(404);
});
