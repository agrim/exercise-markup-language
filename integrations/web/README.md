# Optional EML browser preview

A small, static exercise preview for an existing exercise library. It uses the reference renderer, has no runtime framework dependency, and never writes workout data. The React adapter uses the receiving application's React installation. Existing media stays alongside it and remains usable when EML is disabled, unmapped, loading or unavailable.

Start with one explicitly reviewed mapping. [OpenGym pilot and insertion guide](OPENGYM.md).

## Prepare assets and component

From the EML repository root, with Python 3.11+ and `requirements.txt` installed:

```sh
python integrations/web/export_bundle.py \
  --mapping integrations/web/manifest.example.json --out /tmp/eml-assets --fps 12
python integrations/web/package_preview.py --out /tmp/eml-preview
```

Both destinations must be new. The first command strictly compiles the mapped recipes and copies their matching model, equipment and attribution. The second packages the browser modules and license without geometry or a server. Copy that package into your application's source and the complete asset bundle into an application-owned static directory. Import the generated manifest from that same bundle; use a same-origin directory URL ending in `/` for `baseURL`. Preserve your application's base path when deployed below a subdirectory.

The example IDs `demo:squat` and `demo:plank` are fictional. IDs are exact strings: `"0017"` is different from `"17"` and from the number `17`. The mapping never infers equivalence from exercise names. Parameter names/ranges come from the recipe; changed parameters require a new export.

## Mount it

Import the packaged stylesheet once and give the preview its own empty host element:

```js
import {mountEMLPreview} from './eml-preview/preview.js';
import './eml-preview/preview.css';

const preview = mountEMLPreview(hostElement, {
  manifest, baseURL: '/eml-assets/', exerciseID: 'demo:plank',
  title: 'Forearm plank',
  description: 'Rest on your forearms and toes. Keep your trunk extended and feet planted.',
});
// On route/sheet close or exercise change:
preview.dispose();
```

Or use the adapter alongside the application's original media:

```jsx
import EMLPreview from './eml-preview/EMLPreview.jsx';

<>
  <ExistingMedia exercise={exercise} />
  <EMLPreview enabled={previewAllowed} manifest={manifest}
    baseURL="/eml-assets/" exerciseID={exercise.id}
    title={localizedName} description={localizedInstructions}
    labels={localizedPreviewLabels} />
</>
```

`enabled` defaults to false in React. The host owns whether preview is allowed, including existing media-off, missing exercise and custom-media policies. The plain JavaScript caller simply does not mount when disabled. Unmapped/ambiguous/non-string IDs and missing text alternatives render no preview. Keep the manifest object stable (for example, a static JSON import). Equal inline label maps and changing callback identities do not close an open React preview. Changed exercise/content props dispose the old instance before mounting another; React StrictMode is supported.

All labels are plain strings. Import `defaultLabels` to translate every key, including `seconds`, whose `{current}` and `{total}` placeholders are substituted into the slider's spoken value. Empty/non-string overrides use the English default. The host supplies a localized title and meaningful text description; recipe names are not an adequate movement alternative. An optional `onUnavailable(error)` callback may report a local media failure but must not change workouts or remove original media. It is never required for fallback.

## Behavior and lifecycle

- Initially one **View movement** button. The component itself requests no renderer, binary mesh or clip before activation. A host service worker may independently prefetch code/styles; OpenGym’s enabled production worker does this without executing the renderer or fetching its model/clip payload (see the [host policy](OPENGYM.md)). Opening renders a paused initial pose; **Play** runs one authored inspection cycle and stops. It never claims to execute the recipe's entire repeat/travel policy, prescribe training duration, count a repetition or complete a set.
- Native **Play/Pause**, a labelled position slider and a collapsed **Camera** disclosure provide keyboard and single-pointer control. Camera buttons offer every rotate/zoom action available through gestures plus Reset. Visible instructions and an anatomy-credit link accompany the canvas. The disclosure button remains stable during loading, errors and close; controls that disappear on an error return focus to it.
- There is no autoplay. Explicit Play remains available with reduced motion. Changing to reduced motion, backgrounding, page hiding or scrolling the canvas out of view pauses playback; returning never restarts it automatically. No animation frame remains scheduled while paused. Time announcements belong to the slider, not a continuously speaking live region.
- Hide/unmount aborts fetches, rejects stale async results, cancels the animation frame, disconnects intersection/resize observers, removes all event listeners, releases pointer captures and deletes GPU programs, buffers and vertex arrays. The host releases its canvas context to avoid exhausting browser context slots during repeated mounts. Disposal is idempotent, including partial setup failure.
- Unavailable WebGL, context loss, failed/redirected fetches, invalid clips and hash mismatches show a brief unavailable status. Original media remains untouched. Close/open gives an explicit retry with a fresh canvas; there is no retry loop or silent auto-resume.

## Asset and semantic contract

`eml-web-map-v1` has `entries` containing `exercise_id`, a relative `recipe` inside EML, and optional numeric `parameters`. Duplicate IDs/JSON keys, path escapes, unsupported parameters and strict compiler diagnostics fail export. Rates are integer 1–120 fps, with a conservative maximum of 3,600 samples per cycle. Outputs are staged before publication and existing destinations are preserved. The captured recipe bytes are the bytes compiled and published, even if their source is edited during compilation.

`eml-web-bundle-v1` is an integration asset index, not a new EML language version. It preserves host IDs, EML IDs/versions, untouched recipes, effective parameters, complete compiled clips, SHA-256 hashes, compiler-input fingerprint and version-keyed equipment paths. The browser verifies loaded clip/model/mesh/equipment hashes, clip identity/version and sampled structure before rendering. Assets must be same-origin bundle-relative paths, with no traversal or redirects. Serve over HTTPS or localhost for Web Crypto; no credentials beyond same-origin asset delivery are needed.

Clips retain local XYZW joint quaternions, world positions, root displacement, equipment, connections, muscle roles and side focus. Use the paired renderer/model/equipment version together. Authored muscle roles are instructional labels, not activation percentages or workout measurements. [Specification](../../docs/specification.md) · [Authoring](../../docs/authoring.md) · [Conformance](../../docs/conformance.md).

Code uses the repository's MIT license. The exporter copies the V3 geometry credits from `anatomy/ATTRIBUTION.md`. Keep that file accessible through the preview’s credits link. The code package does not relicense anatomy assets. No OpenGym source or media is copied into this integration.

## Reproduce verification

```sh
python -m unittest discover -s integrations/web -p 'test_*.py' -v
node --test viewer/*.test.mjs
cd integrations/web
npm ci
npx playwright install --with-deps chromium webkit
npm run test:prepare
npm test
```

Set `EML_PYTHON=/path/to/venv/bin/python` for `test:prepare` when needed. Node dependencies are development-only; the delivered component has no npm-install requirement beyond the host's React if using that adapter. Real-browser tests use exported EML 1.0/1.1 clips, actual WebGL drawing, keyboard and accessibility-tree checks, axe, failure injection and resource accounting. The suite also exercises StrictMode, stale loads, rapid replacement, repeated mounts, reduced motion, visibility, narrow text layouts and translations. Renderer unit tests cover partial initialization failures that are hard to force reliably on a real GPU. See the dated verification report for observed results and remaining evidence boundaries; passing automation does not establish screen-reader speech or every host application's integration.
