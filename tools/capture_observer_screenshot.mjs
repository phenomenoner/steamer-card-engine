#!/usr/bin/env node
import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

function arg(name, fallback = null) {
  const prefix = `--${name}=`;
  const hit = process.argv.find((item) => item.startsWith(prefix));
  if (hit) return hit.slice(prefix.length);
  const idx = process.argv.indexOf(`--${name}`);
  if (idx >= 0 && process.argv[idx + 1]) return process.argv[idx + 1];
  return fallback;
}

const url = arg('url', 'http://43.212.33.0/');
const out = resolve(arg('out', '.state/screenshots/observer.png'));
const metaOut = resolve(arg('meta', `${out}.json`));
const width = Number(arg('width', '1440'));
const height = Number(arg('height', '1200'));
const fullPage = arg('full-page', 'true') !== 'false';
const waitMs = Number(arg('wait-ms', '1500'));

mkdirSync(dirname(out), { recursive: true });
mkdirSync(dirname(metaOut), { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
const errors = [];
page.on('pageerror', (error) => errors.push(String(error)));
page.on('console', (message) => {
  if (['error', 'warning'].includes(message.type())) errors.push(`${message.type()}: ${message.text()}`);
});
const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 });
await page.waitForTimeout(waitMs);
await page.screenshot({ path: out, fullPage });
const title = await page.title();
const visibleText = await page.locator('body').innerText({ timeout: 5000 }).catch(() => '');
const markers = [
  'Step 1 · Strategy Card',
  'Step 2 · View',
  'Step 3 · Symbol for detail',
  'Current Strategy Card path',
  'chart symbol',
  'mounted symbol',
  'Symbol Detail ·',
];
const meta = {
  url,
  out,
  captured_at: new Date().toISOString(),
  status: response?.status() ?? null,
  title,
  viewport: { width, height, fullPage },
  marker_visible_text: Object.fromEntries(markers.map((marker) => [marker, visibleText.includes(marker)])),
  visible_text_head: visibleText.slice(0, 2000),
  console_errors: errors.slice(0, 50),
};
writeFileSync(metaOut, JSON.stringify(meta, null, 2));
await browser.close();
console.log(JSON.stringify(meta, null, 2));
