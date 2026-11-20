import { execFileSync } from 'node:child_process';
import { mkdirSync, rmSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const here = dirname(fileURLToPath(import.meta.url));
const integration = resolve(here, '..');
const generated = resolve(here, 'generated');
rmSync(generated, { recursive: true, force: true });
mkdirSync(generated);
const mapping = JSON.parse(readFileSync(resolve(integration, 'manifest.example.json')));
mapping.entries.push({ exercise_id: 'legacy:reach', recipe: 'examples/diagonal-reach.json' });
const pilot = JSON.parse(readFileSync(resolve(integration, 'opengym-pilot.example.json')));
mapping.entries.push(...pilot.entries);
const python = process.env.EML_PYTHON || 'python3';
execFileSync(python, ['-m', 'examples.fluent_incline_push_up', resolve(generated, 'incline.json')],
  { cwd: resolve(integration, '../..'), stdio: 'inherit' });
mapping.entries.push({ exercise_id: 'fluent:incline', recipe: 'integrations/web/tests/generated/incline.json' });
writeFileSync(resolve(generated, 'mapping.json'), JSON.stringify(mapping));
execFileSync(python, [resolve(integration, 'export_bundle.py'),
  '--mapping', resolve(generated, 'mapping.json'), '--out', resolve(generated, 'bundle'),
  '--fps', '12'], { stdio: 'inherit' });
execFileSync(python, [resolve(integration, 'package_preview.py'),
  '--out', resolve(generated, 'package')], { stdio: 'inherit' });
await build({ entryPoints: [resolve(here, 'fixtures/react.jsx')], bundle: true, splitting: true,
  format: 'esm', outdir: resolve(generated, 'react'), jsx: 'automatic', sourcemap: true });
