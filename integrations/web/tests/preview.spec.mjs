import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { installAccounting } from './instrumentation.mjs';

const url = '/integrations/web/tests/fixtures/index.html';
const slider = page => page.getByRole('slider', { name: 'Movement position' });
async function fixture(page, overrides = {}) {
  await page.goto(url);
  await page.waitForFunction(() => window.fixtureReady);
  await page.evaluate(options => window.fixture.mount(options), overrides);
}
async function open(page) {
  await page.getByRole('button', { name: 'View movement', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  await expect(page.locator('#host canvas')).toBeVisible();
}
async function assertOriginal(page) {
  expect(await page.evaluate(() => window.fixture.originalUnchanged())).toBe(true);
  await page.locator('#original').click();
  await expect(page.locator('#original-status')).toHaveText('Original media selected.');
}
async function assertNoHorizontalOverflow(page, phase) {
  const layout = await page.evaluate(() => ({
    viewportWidth: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    overflowing: [...document.querySelectorAll('body *')].flatMap(element => {
      if (!element.getClientRects().length) return [];
      const rect = element.getBoundingClientRect();
      if (rect.left >= -1 && rect.right <= window.innerWidth + 1
        && element.scrollWidth <= element.clientWidth + 1) return [];
      return [{ tag: element.tagName, id: element.id, className: element.className,
        text: element.textContent.trim().slice(0, 100), left: rect.left, right: rect.right,
        clientWidth: element.clientWidth, scrollWidth: element.scrollWidth }];
    }),
  }));
  expect(layout.scrollWidth, `${phase}: ${JSON.stringify(layout)}`).toBeLessThanOrEqual(layout.viewportWidth);
}
async function pixels(page) {
  return page.locator('#host canvas').evaluate(canvas => {
    const gl = canvas.getContext('webgl2');
    const data = new Uint8Array(canvas.width * canvas.height * 4);
    gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, data);
    let visible = 0;
    const colors = new Set();
    for (let i = 0; i < data.length; i += 4) if (data[i + 3] > 0) {
      visible++; colors.add(`${data[i]},${data[i + 1]},${data[i + 2]}`);
    }
    return { visible, colors: colors.size, total: data.length / 4 };
  });
}

test.beforeEach(async ({ page }, info) => {
  info.pageErrors = [];
  page.on('pageerror', error => info.pageErrors.push(String(error)));
  await page.addInitScript(installAccounting);
});
test.afterEach(async ({}, info) => { expect(info.pageErrors).toEqual([]); });

test('optional exact mapping does no asset work before opening; real model renders paused', async ({ page }, info) => {
  const requested = [];
  page.on('request', req => requested.push(req.url()));
  await fixture(page);
  await expect(page.getByRole('button', { name: 'View movement', exact: true })).toBeVisible();
  expect(requested.filter(path => /(?:vertices\.bin|indices\.bin|clips\/|mesh\.js)/.test(path))).toEqual([]);
  expect((await page.evaluate(() => window.accounting())).created).toBe(0);
  await open(page);
  const image = await pixels(page);
  expect(image.visible).toBeGreaterThan(image.total * .03);
  expect(image.colors).toBeGreaterThan(80);
  const initial = await slider(page).inputValue();
  await page.waitForTimeout(300);
  expect(await slider(page).inputValue()).toBe(initial);
  await expect(page.locator('#host')).toContainText('Stand with feet planted');
  await expect(page.getByRole('link', { name: /credit/i })).toBeVisible();
  await info.attach('paused-render', { body: await page.screenshot({ fullPage: false }), contentType: 'image/png' });
  await assertOriginal(page);
});

test('the OpenGym plank and fluent incline push-up render with the packaged V3 human', async ({ page }) => {
  await fixture(page);
  for (const [exerciseID, title] of [['0463', 'Plank'], ['fluent:incline', 'Incline push-up']]) {
    await page.evaluate(options => window.fixture.mountPackaged(options), { exerciseID, title });
    const model = page.waitForResponse(response => response.url().endsWith('/anatomy/model.json'));
    await open(page);
    expect((await (await model).json()).modelID).toBe('simple-trainer-v3');
    const image = await pixels(page);
    expect(image.colors).toBeGreaterThan(80);
    const credits = page.getByRole('link', { name: /credit/i });
    const notice = await page.request.get(await credits.getAttribute('href'));
    expect(await notice.text()).toContain('MakeHuman');
    await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
    await assertOriginal(page);
  }
});

test('missing, duplicate, numeric IDs and absent text alternatives remain optional', async ({ page }) => {
  await fixture(page, { exerciseID: 'missing' });
  await expect(page.locator('#host')).toBeEmpty();
  for (const options of [{ exerciseID: 17 }, { description: '' }, { description: ' ' }]) {
    await page.evaluate(value => window.fixture.mount(value), options);
    await expect(page.locator('#host')).toBeEmpty();
  }
  await page.evaluate(() => window.fixture.mount({ manifest: { ...window.fixture.manifest,
    entries: [...window.fixture.manifest.entries, window.fixture.manifest.entries[0]] } }));
  await expect(page.locator('#host')).toBeEmpty();
  expect((await page.evaluate(() => window.accounting())).created).toBe(0);
  await assertOriginal(page);
});

test('keyboard play, pause, scrub and camera controls require no dragging', async ({ page }) => {
  await fixture(page);
  await page.getByRole('button', { name: 'View movement', exact: true }).focus();
  await page.keyboard.press('Enter');
  const play = page.getByRole('button', { name: 'Play', exact: true });
  await expect(play).toBeVisible();
  await play.focus();
  await page.keyboard.press('Space');
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible();
  await expect.poll(async () => Number(await slider(page).inputValue())).toBeGreaterThan(0);
  await page.keyboard.press('Space');
  await expect(play).toBeVisible();
  await slider(page).focus();
  await page.keyboard.press('End');
  expect(Number(await slider(page).inputValue())).toBeCloseTo(Number(await slider(page).getAttribute('max')), 2);
  await page.keyboard.press('Home');
  expect(Number(await slider(page).inputValue())).toBe(0);
  await page.getByText('Camera', { exact: true }).press('Enter');
  const before = await page.locator('#host canvas').screenshot();
  await page.getByRole('button', { name: 'Rotate right', exact: true }).press('Enter');
  const after = await page.locator('#host canvas').screenshot();
  expect(after.equals(before)).toBe(false);
  await page.getByRole('button', { name: 'Reset view', exact: true }).press('Enter');
  await page.getByRole('button', { name: 'Hide movement', exact: true }).press('Enter');
  await expect(page.getByRole('button', { name: 'View movement', exact: true })).toBeFocused();
  await expect(page.locator('#host canvas')).toHaveCount(0);
});

test('one cycle ends paused and never starts another automatically', async ({ page }) => {
  await fixture(page, { exerciseID: 'demo:plank', title: 'Plank', description: 'Hold the trunk steady on forearms and toes.' });
  await open(page);
  await slider(page).focus();
  await page.keyboard.press('End');
  await page.keyboard.press('ArrowLeft');
  await page.getByRole('button', { name: 'Play', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  const end = await slider(page).inputValue();
  expect(Number(end)).toBeCloseTo(Number(await slider(page).getAttribute('max')), 2);
  await page.waitForTimeout(250);
  expect(await slider(page).inputValue()).toBe(end);
});

test('unmount, repeated reopen and independent instances release owned resources', async ({ page }) => {
  await fixture(page);
  const baseline = await page.evaluate(() => window.accounting());
  for (let i = 0; i < 4; i++) {
    await open(page);
    await page.getByRole('button', { name: 'Play', exact: true }).click();
    await expect.poll(async () => Number(await slider(page).inputValue())).toBeGreaterThan(0);
    await page.getByRole('button', { name: 'Hide movement', exact: true }).click();
    await expect.poll(() => page.evaluate(() => window.accounting().live)).toEqual({ buffer: 0, vertexArray: 0, program: 0, shader: 0 });
    const closed = await page.evaluate(() => window.accounting());
    expect(closed.frames).toBe(0);
    expect(closed.observers).toBe(0);
    expect(closed.listeners).toEqual(baseline.listeners);
  }
  await open(page);
  await page.evaluate(() => window.fixture.mountSecond());
  await page.locator('#second-host').getByRole('button', { name: 'View movement', exact: true }).click();
  await expect(page.locator('#second-host canvas')).toBeVisible();
  const ids = await page.locator('[id]').evaluateAll(elements => elements.map(element => element.id));
  expect(new Set(ids).size).toBe(ids.length);
  await page.evaluate(() => { window.fixture.dispose(); window.fixture.dispose(); });
  await expect(page.locator('#host')).toBeEmpty();
  await expect(page.locator('#second-host')).toBeEmpty();
  const result = await page.evaluate(() => window.accounting());
  expect(result.live).toEqual({ buffer: 0, vertexArray: 0, program: 0, shader: 0 });
  expect(result.observers).toBe(0);
  expect(result.frames).toBe(0);
  expect(result.created).toBe(result.deleted);
});

test('cancel pending fetch and replace exercise without late canvas or stale result', async ({ page }) => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  let held = false;
  await page.route('**/clips/0001.json', async route => { held = true; await gate; await route.continue().catch(() => {}); });
  await fixture(page);
  await page.getByRole('button', { name: 'View movement', exact: true }).click();
  await expect.poll(() => held).toBe(true);
  await page.evaluate(() => window.fixture.mount({ exerciseID: 'demo:plank', title: 'Plank', description: 'Keep the trunk steady.' }));
  release();
  await page.getByRole('button', { name: 'View movement', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  await expect(page.locator('#host')).toContainText('Keep the trunk steady.');
  await expect(page.locator('#host canvas')).toHaveCount(1);
  await expect.poll(() => page.evaluate(() => window.accounting().activeFetches)).toBe(0);
  await page.evaluate(() => window.fixture.dispose());
  expect((await page.evaluate(() => window.accounting())).created).toBe((await page.evaluate(() => window.accounting())).deleted);
  expect(await page.evaluate(() => window.fixture.failures)).toEqual([]);
});

test('asset error retains original media and explicit reopen retries cleanly', async ({ page }) => {
  await page.route('**/vertices.bin', route => route.fulfill({ status: 503, body: 'Unavailable' }));
  await fixture(page);
  await page.getByRole('button', { name: 'View movement', exact: true }).click();
  await expect(page.locator('#host')).toContainText('Movement preview unavailable.');
  await expect(page.locator('#host canvas')).toHaveCount(0);
  await assertOriginal(page);
  await page.unroute('**/vertices.bin');
  await page.getByRole('button', { name: 'Hide movement', exact: true }).click();
  await open(page);
});

test('unsupported WebGL and lost context leave an accessible original-media fallback', async ({ page }) => {
  await page.addInitScript(() => {
    const getContext = HTMLCanvasElement.prototype.getContext;
    window.blockWebGL = false;
    HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
      return window.blockWebGL && kind === 'webgl2' ? null : getContext.call(this, kind, ...args);
    };
  });
  await fixture(page);
  await page.evaluate(() => { window.blockWebGL = true; });
  await page.getByRole('button', { name: 'View movement', exact: true }).click();
  await expect(page.locator('#host')).toContainText('Movement preview unavailable.');
  await assertOriginal(page);
  await page.getByRole('button', { name: 'Hide movement', exact: true }).click();
  await page.evaluate(() => { window.blockWebGL = false; });
  await open(page);
  await page.getByRole('button', { name: 'Play', exact: true }).click();
  const supported = await page.locator('#host canvas').evaluate(canvas => {
    const extension = canvas.getContext('webgl2').getExtension('WEBGL_lose_context');
    if (!extension) return false;
    extension.loseContext(); return true;
  });
  expect(supported).toBe(true);
  await expect(page.locator('#host')).toContainText('Movement preview unavailable.');
  await expect(page.locator('#host canvas')).toHaveCount(0);
  expect((await page.evaluate(() => window.accounting())).frames).toBe(0);
  await assertOriginal(page);
});

test('reduced motion starts paused and preference changes stop explicit playback', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await fixture(page);
  await open(page);
  const value = await slider(page).inputValue();
  await page.waitForTimeout(250);
  expect(await slider(page).inputValue()).toBe(value);
  await page.getByRole('button', { name: 'Play', exact: true }).click();
  await expect.poll(async () => Number(await slider(page).inputValue())).toBeGreaterThan(0);
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
});

test('offscreen and visibility changes pause without auto-resume', async ({ page }) => {
  await fixture(page);
  await open(page);
  await page.getByRole('button', { name: 'Play', exact: true }).click();
  await page.locator('#after').scrollIntoViewIfNeeded();
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeAttached();
  const value = await slider(page).inputValue();
  await page.locator('#host').scrollIntoViewIfNeeded();
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  await page.waitForTimeout(200);
  expect(await slider(page).inputValue()).toBe(value);
  await page.getByRole('button', { name: 'Play', exact: true }).click();
  // Deterministic policy check; scrolling above is actual browser intersection evidence.
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  await page.evaluate(() => {
    delete document.hidden;
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
});

test('accessible semantics and 320px enlarged text preserve controls and descriptions', async ({ page }, info) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await fixture(page);
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  await assertNoHorizontalOverflow(page, 'Enlarged host before opening the preview');
  await open(page);
  await page.getByText('Camera', { exact: true }).click();
  await assertNoHorizontalOverflow(page, 'Enlarged preview with camera controls open');
  const violations = (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze()).violations;
  expect(violations).toEqual([]);
  const dimensions = await page.locator('#host button').evaluateAll(buttons => buttons.filter(button => button.getClientRects().length).map(button => ({ text: button.textContent, width: button.getBoundingClientRect().width, height: button.getBoundingClientRect().height })));
  expect(dimensions.every(item => item.width >= 24 && item.height >= 24)).toBe(true);
  await info.attach('narrow-enlarged-controls', { body: await page.locator('#host').screenshot(), contentType: 'image/png' });
});

test('forced colors retain native control affordances', async ({ page, browserName }, info) => {
  test.skip(browserName === 'webkit', 'Playwright WebKit does not emulate forced-colors. Chromium checks this preference.');
  await page.emulateMedia({ forcedColors: 'active' });
  await fixture(page);
  await open(page);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeFocused();
  expect(await page.getByRole('button', { name: 'Play', exact: true }).evaluate(button => getComputedStyle(button).outlineStyle)).not.toBe('none');
  await info.attach('forced-colors', { body: await page.locator('#host').screenshot(), contentType: 'image/png' });
});

test('React StrictMode cleanup and prop changes preserve one optional instance', async ({ page }) => {
  await page.goto('/integrations/web/tests/fixtures/react.html');
  await page.waitForFunction(() => window.fixtureReady);
  await page.evaluate(() => window.reactFixture.render({ enabled: undefined }));
  await expect(page.locator('#react-root')).toBeEmpty();
  expect((await page.evaluate(() => window.accounting())).created).toBe(0);
  await page.evaluate(() => window.reactFixture.render());
  await expect(page.getByRole('button', { name: 'View movement', exact: true })).toHaveCount(1);
  expect((await page.evaluate(() => window.accounting())).created).toBe(0);
  await page.getByRole('button', { name: 'View movement', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  await page.evaluate(() => window.reactFixture.render({ exerciseID: 'demo:plank', title: 'Plank', description: 'Keep the trunk steady.' }));
  await expect(page.getByRole('button', { name: 'View movement', exact: true })).toHaveCount(1);
  await expect(page.locator('canvas')).toHaveCount(0);
  expect((await page.evaluate(() => window.accounting())).live).toEqual({ buffer: 0, vertexArray: 0, program: 0, shader: 0 });
  await page.getByRole('button', { name: 'View movement', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  await page.evaluate(() => window.reactFixture.unmount());
  await expect(page.locator('canvas')).toHaveCount(0);
  const final = await page.evaluate(() => window.accounting());
  expect(final.created).toBe(final.deleted);
  expect(final.frames).toBe(0);
  expect(final.observers).toBe(0);
});

test('legacy EML clip uses its matching equipment registry and renders without changing host identity', async ({ page }, info) => {
  const requested = [];
  page.on('request', request => requested.push(request.url()));
  await fixture(page, { exerciseID: 'legacy:reach', title: 'Diagonal reach', description: 'Reach diagonally while keeping both feet planted.' });
  await open(page);
  expect(requested.some(path => path.endsWith('/equipment/1.0.json'))).toBe(true);
  const image = await pixels(page);
  expect(image.visible).toBeGreaterThan(image.total * .03);
  expect(image.colors).toBeGreaterThan(80);
  await info.attach('legacy-render', { body: await page.locator('#host').screenshot(), contentType: 'image/png' });
  await assertOriginal(page);
});

test('asset integrity and bundle path rejection fail closed without external requests', async ({ page }) => {
  const external = [];
  page.on('request', request => { if (!request.url().startsWith('http://127.0.0.1:8793/')) external.push(request.url()); });
  await fixture(page, { baseURL: 'https://example.invalid/eml/' });
  await page.getByRole('button', { name: 'View movement', exact: true }).click();
  await expect(page.locator('#host')).toContainText('Movement preview unavailable.');
  await page.evaluate(() => window.fixture.mount({ manifest: { ...window.fixture.manifest,
    assets: { ...window.fixture.manifest.assets, vertices: '../outside.bin' },
    asset_sha256: { ...window.fixture.manifest.asset_sha256, '../outside.bin': window.fixture.manifest.asset_sha256[window.fixture.manifest.assets.vertices] } } }));
  await page.getByRole('button', { name: 'View movement', exact: true }).click();
  await expect(page.locator('#host')).toContainText('Movement preview unavailable.');
  await page.evaluate(() => window.fixture.mount({ manifest: { ...window.fixture.manifest,
    entries: window.fixture.manifest.entries.map(entry => ({ ...entry, clip_sha256: '0'.repeat(64) })) } }));
  await page.getByRole('button', { name: 'View movement', exact: true }).click();
  await expect(page.locator('#host')).toContainText('Movement preview unavailable.');
  expect(external).toEqual([]);
  expect((await page.evaluate(() => window.accounting())).created).toBe(0);
  await assertOriginal(page);
});

test('host translations and plain text descriptions do not introduce markup', async ({ page }) => {
  await fixture(page, { title: 'Sentadilla', description: '<img src=x onerror=alert(1)> Texto del ejercicio.', labels: {
    view: 'Ver movimiento', hide: 'Ocultar movimiento', play: 'Reproducir', pause: 'Pausar',
    position: 'Posición del movimiento', camera: 'Cámara', credits: 'Créditos de anatomía',
  } });
  await page.getByRole('button', { name: 'Ver movimiento', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Reproducir', exact: true })).toBeVisible();
  await expect(page.getByRole('slider', { name: 'Posición del movimiento' })).toBeVisible();
  await expect(page.locator('#host img')).toHaveCount(0);
  await expect(page.locator('#host')).toContainText('<img src=x onerror=alert(1)> Texto del ejercicio.');
  await page.getByRole('button', { name: 'Ocultar movimiento', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Ver movimiento', exact: true })).toBeVisible();
});

test('React inline callback and equal translated labels do not close an open preview', async ({ page }) => {
  await page.goto('/integrations/web/tests/fixtures/react.html');
  await page.waitForFunction(() => window.fixtureReady);
  await page.evaluate(() => window.reactFixture.render({ labels: { view: 'View movement' }, onUnavailable: () => {} }));
  await page.getByRole('button', { name: 'View movement', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  const created = (await page.evaluate(() => window.accounting())).created;
  await page.evaluate(() => window.reactFixture.render({ labels: { view: 'View movement' }, onUnavailable: () => {} }));
  await expect(page.getByRole('button', { name: 'Hide movement', exact: true })).toBeVisible();
  await expect(page.locator('canvas')).toHaveCount(1);
  expect((await page.evaluate(() => window.accounting())).created).toBe(created);
});

test('long localized RTL controls reflow at narrow width', async ({ page }, info) => {
  await page.setViewportSize({ width: 320, height: 850 });
  await fixture(page, { labels: { view: 'عرض توضيح الحركة اختياريًا لهذا التمرين',
    hide: 'إخفاء توضيح الحركة الاختياري لهذا التمرين', play: 'تشغيل الحركة بوضوح',
    position: 'موضع العرض التوضيحي للحركة', camera: 'عناصر التحكم في الكاميرا',
    left: 'تدوير النموذج إلى اليسار', right: 'تدوير النموذج إلى اليمين' } });
  await page.evaluate(() => { document.documentElement.dir = 'rtl'; document.documentElement.lang = 'ar'; });
  await page.getByRole('button', { name: 'عرض توضيح الحركة اختياريًا لهذا التمرين', exact: true }).click();
  await expect(page.getByRole('button', { name: 'تشغيل الحركة بوضوح', exact: true })).toBeVisible();
  await page.getByText('عناصر التحكم في الكاميرا', { exact: true }).click();
  expect(await page.locator('.eml-preview-clock').evaluate(clock => getComputedStyle(clock).direction)).toBe('ltr');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const boxes = await page.locator('#host button').evaluateAll(buttons => buttons.filter(button => button.getClientRects().length).map(button => ({ x: button.getBoundingClientRect().x, right: button.getBoundingClientRect().right })));
  expect(boxes.every(box => box.x >= 0 && box.right <= 320)).toBe(true);
  await info.attach('rtl-long-labels', { body: await page.locator('#host').screenshot(), contentType: 'image/png' });
});

test('dark appearance keeps the readable text alternative and native controls', async ({ page }, info) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await fixture(page);
  await open(page);
  const violations = (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze()).violations;
  expect(violations).toEqual([]);
  await expect(page.locator('#host')).toContainText('Stand with feet planted');
  await page.getByRole('button', { name: 'Play', exact: true }).click();
  await expect.poll(async () => Number(await slider(page).inputValue())).toBeGreaterThan(0);
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await info.attach('dark-paused', { body: await page.locator('#host').screenshot(), contentType: 'image/png' });
});

test('partial shader initialization failure releases GPU objects and preserves fallback', async ({ page }) => {
  await page.addInitScript(() => {
    const proto = WebGL2RenderingContext.prototype;
    const parameter = proto.getShaderParameter;
    let injected = false;
    proto.getShaderParameter = function (shader, key) {
      if (!injected && key === this.COMPILE_STATUS) { injected = true; return false; }
      return parameter.call(this, shader, key);
    };
  });
  await fixture(page);
  await page.getByRole('button', { name: 'View movement', exact: true }).click();
  await expect(page.locator('#host')).toContainText('Movement preview unavailable.');
  const accounting = await page.evaluate(() => window.accounting());
  expect(accounting.created).toBeGreaterThan(0);
  expect(accounting.created).toBe(accounting.deleted);
  expect(accounting.live).toEqual({ buffer: 0, vertexArray: 0, program: 0, shader: 0 });
  expect(accounting.observers).toBe(0);
  expect(accounting.frames).toBe(0);
  await assertOriginal(page);
});

test('packaged contribution runs independently with relative renderer imports and cleanup', async ({ page }, info) => {
  const requested = [];
  page.on('request', request => requested.push(request.url()));
  await page.goto(url);
  await page.waitForFunction(() => window.fixtureReady);
  await page.evaluate(() => window.fixture.mountPackaged());
  await open(page);
  expect(requested.some(path => path.endsWith('/package/renderer/mesh.js'))).toBe(true);
  expect(requested.some(path => path.endsWith('/package/renderer/camera-controls.js'))).toBe(true);
  expect(requested.some(path => path.endsWith('/viewer/mesh.js'))).toBe(false);
  const image = await pixels(page);
  expect(image.visible).toBeGreaterThan(image.total * .03);
  expect(image.colors).toBeGreaterThan(80);
  await page.getByRole('button', { name: 'Play', exact: true }).click();
  await expect.poll(async () => Number(await slider(page).inputValue())).toBeGreaterThan(0);
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await info.attach('packaged-preview', { body: await page.locator('#host').screenshot(), contentType: 'image/png' });
  await page.evaluate(() => window.fixture.dispose());
  const resources = await page.evaluate(() => window.accounting());
  expect(resources.created).toBe(resources.deleted);
  expect(resources.frames).toBe(0);
  expect(resources.observers).toBe(0);
  await assertOriginal(page);
});

test('long translated instructions keep mobile Play adjacent to the visible canvas', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fixture(page, { description: ('Stelle die Füße fest auf den Boden. Beuge Hüfte und Knie kontrolliert und kehre anschließend in die Ausgangsposition zurück. Halte den Oberkörper stabil und führe die Bewegung ohne Schwung aus. ').repeat(12) });
  await open(page);
  await page.getByRole('button', { name: 'Play', exact: true }).click();
  expect(await page.locator('#host canvas').evaluate(canvas => {
    const rect = canvas.getBoundingClientRect();
    return rect.bottom > 0 && rect.top < window.innerHeight && rect.right > 0 && rect.left < window.innerWidth;
  })).toBe(true);
  await expect.poll(async () => Number(await slider(page).inputValue())).toBeGreaterThan(.3);
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await info.attach('mobile-long-instructions', { body: await page.screenshot(), contentType: 'image/png' });
});
