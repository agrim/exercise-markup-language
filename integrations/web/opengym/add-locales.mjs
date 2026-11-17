#!/usr/bin/env node
// Add only missing optional-preview strings to an explicitly selected OpenGym checkout.
import {readFile, writeFile} from 'node:fs/promises';
import {resolve, join} from 'node:path';
import {pathToFileURL} from 'node:url';

const [frontend, ...rest] = process.argv.slice(2);
if (!frontend || rest.some(arg => arg !== '--check')) {
  throw new Error('Usage: node add-locales.mjs /path/to/openGym/frontend [--check]');
}
const additions = JSON.parse(await readFile(new URL('./locale-additions.json', import.meta.url), 'utf8'));
const marks = text => [...text.matchAll(/\{[^{}]+\}/g)].map(match => match[0]).sort().join('|');
const changes = [];
// Prepare every edit before writing any file; unsupported source layouts fail closed.
for (const [locale, entries] of Object.entries(additions)) {
  const name = locale.endsWith('.js') ? locale : `${locale}.js`;
  if (!/^[a-z]{2}(?:-[A-Z]{2})?\.js$/.test(name)) throw new Error(`Invalid locale: ${locale}`);
  const path = join(resolve(frontend), 'src/locales', name);
  const source = await readFile(path, 'utf8');
  const {default: existing} = await import(pathToFileURL(path).href);
  const missing = [];
  for (const [key, value] of Object.entries(entries)) {
    if (!key.trim() || typeof value !== 'string' || !value.trim() || marks(key) !== marks(value)) {
      throw new Error(`Invalid translation or placeholders: ${name}: ${key}`);
    }
    if (!Object.hasOwn(existing, key)) missing.push([key, value]);
  }
  if (!missing.length) continue;
  const marker = name === 'pt-BR.js' ? 'export const PT_BR_OVERRIDES = {' : 'export default {';
  if (source.split(marker).length !== 2) throw new Error(`Unrecognized locale layout: ${name}`);
  const lines = missing.map(([key, value]) => `  ${JSON.stringify(key)}: ${JSON.stringify(value)},`).join('\n');
  changes.push({path, count: missing.length, before: source,
    after: source.replace(marker, `${marker}\n  // Optional EML movement preview.\n${lines}`)});
}
for (const change of changes) {
  // Do not overwrite a translator's concurrent edit.
  if (await readFile(change.path, 'utf8') !== change.before) throw new Error(`Locale changed: ${change.path}`);
}
if (!rest.includes('--check')) for (const change of changes) await writeFile(change.path, change.after);
console.log(JSON.stringify({mode: rest.includes('--check') ? 'check' : 'write',
  files: changes.length, strings: changes.reduce((sum, change) => sum + change.count, 0)}, null, 2));
