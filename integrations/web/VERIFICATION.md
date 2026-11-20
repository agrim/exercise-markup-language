# Optional browser preview verification — 17 November 2026

The optional EML preview passed its final Chromium and WebKit matrix: **43 passes, zero failures, one explicitly unsupported emulation slot skipped**. The suite contains 22 scenarios run in both engines. The original media fixture remains usable throughout loading, failure, cancellation and unmount. This record covers the reusable browser component, its React adapter and the exported code package.

## Observed checks

| Check | Final result | Durable evidence |
| --- | --- | --- |
| Real-browser matrix | 43 passed, 0 failed, 1 skipped in 45.857 seconds. Chromium 159.0.8154.6 / Playwright revision 1255 and WebKit 27.2 / revision 2388, on macOS arm64. | [Browser log](review/browser-tests.log), [per-scenario results and source hashes](review/summary.json) |
| Reference-viewer JavaScript tests | 43 passed, 0 failed or skipped. Covers disposal, partial initialization failures, camera controls, playback and existing visibility behavior. | [Node log](review/viewer-node-tests.log) |
| Exporter and package tests | 19 passed, 0 failed or skipped. Covers strict export, source capture, IDs, paths, hashes, versions, output preservation and deterministic packaging. | [Python integration log](review/export-package-tests.log) |
| Existing core conformance suite | 84 executed: 83 passed, 0 failed, 1 existing optional-dependency skip. | [Core log](review/core-conformance-tests.log) |
| Rendered capture review | All 15 final images opened and visually inspected. Native controls and text remain legible in the selected standard, dark, forced-colors, narrow/enlarged and RTL states. | [Capture index](review/README.md), dimensions and hashes in [summary](review/summary.json) |

The browser skip is WebKit's forced-colors slot: Playwright cannot emulate that preference in WebKit. The Chromium forced-colors check passes using real keyboard focus. The core skip is `test_actual_torso_and_thigh_mesh_stays_out_of_support_pads_and_steel`, with the recorded reason “The skin-surface oracle uses the optional floor-audit dependencies.” It is not represented as a completed anatomy-surface check.

The final browser run uses Playwright 1.65.1 and axe-core 4.14.0 with a local static server. Its CSP permits only same-origin scripts, styles and connections, requires Trusted Types for script sinks in supporting browsers, and permits no Trusted Types policy. No permissive policy or inline HTML assignment is needed by the preview.

## Journeys and lifecycle evidence

- Unmapped, duplicate, numeric and missing-text-alternative inputs render no optional preview. React is disabled by default. No clip, binary mesh, renderer or GPU allocation occurs before **View movement**.
- Real EML 1.0 and 1.1 compiled assets render nonempty, multicolor geometry. The matching versioned equipment registry is requested. The copy-ready code package resolves its renderer imports inside the package and passes real render, play, pause and disposal checks.
- Native keyboard actions operate disclosure, Play/Pause, the position slider, camera rotation and Reset. Playback starts paused, runs one authored cycle, stops at its end and does not automatically repeat.
- Hide, unmount, exercise replacement, React StrictMode and repeated opens release owned WebGL buffers, vertex arrays, shaders and programs. Instrumentation wraps the browser's real resource APIs; it does not replace the renderer. Created/deleted resource counts match after cleanup, with no remaining scheduled animation frame or observed resize/intersection target.
- Pending loads are aborted and stale responses cannot reinsert the old exercise. Asset/hash/path failures, unavailable WebGL, an actual lost WebGL context and a forced partial shader-initialization failure preserve the original media control and allow an explicit retry.
- Reduced-motion changes pause explicit playback. Actual scrolling/intersection changes pause offscreen playback without automatically resuming when it returns. A deterministic synthetic `document.hidden`/`visibilitychange` signal separately checks background policy; that signal is not evidence of physical OS background behavior.
- Axe scans pass in dark appearance and a 320 CSS-pixel viewport with text enlarged to 200%. Long RTL labels reflow; current/total time retains its order. User-supplied descriptions remain plain text. Equal inline translation maps and changed callback identities do not close an open React preview.

The GPU assertions measure owned API resource lifetime, not browser-process heap consumption or physical-device GPU performance. Axe, accessibility-tree assertions and keyboard interaction do not establish VoiceOver/NVDA speech, every assistive-technology combination, or disabled-user usability research.

## Findings resolved during verification

The first real squat preview exposed a valid compiler output with an equal final sample timestamp. The browser reader now accepts nondecreasing sample times while still rejecting backwards or incomplete clips; the real squat fixture covers the case. No recipe or compiled clip was rewritten.

Visual RTL review found the numeric current/total clock displayed in reverse order; its visual clock now explicitly uses left-to-right direction. Dark-theme axe scans found the default blue attribution link had insufficient contrast against the host's dark background. The underlined link now inherits the host's text color, and both engines pass the final dark scan.

React review found that changing inline callback/translation object identities could unnecessarily reset a preview. The adapter now keeps callback identity out of the remount dependency and compares translated label values; the StrictMode and inline-prop tests pass. An initial forced-colors test used programmatic focus after mouse interaction; it was corrected to actual Tab navigation so it tests keyboard `:focus-visible` behavior.

The final host review also tightened the unavailable message: it now says **Movement preview unavailable.** It does not promise that the host's original media is itself available. Long translated instructions exposed another interaction issue: placing them before Play could scroll the canvas offscreen while reaching Play, immediately pausing it. Controls now directly follow the canvas; both engines verify sustained playback with a long German description at 390 × 844 CSS pixels.

## Compatibility with Simple Trainer's existing EML pin

The previous Simple Trainer export at `/tmp/simplifit-eml-web-demo-20261117` was compared with the final test export. Its two entries, `demo:squat` and `demo:plank`, are byte-for-byte compatible at 12 fps:

- The compiler-input fingerprint was independently recomputed from Simple Trainer's EML vendor revision `4a0c47b9cc9a3fd42455bb03bd963c8cb9f3ba43` and matches both bundles: `1ca7713a0c23c65fd97f450993023a4094691bde859a4fb5cbb8c1a965adbfe1`.
- All six shared assets—model, vertex/index buffers, 1.1 equipment registry, EML license and anatomy attribution—have identical bytes and hashes.
- Both complete mapping entries, original recipe bytes and compiled clip bytes are unchanged. Their individual hashes are retained in the [compatibility receipt](review/summary.json).
- A third test-only `legacy:reach` entry exercises EML 1.0 and its separate equipment registry; it does not change the original two mappings.

The test package was generated from the reviewed working changes before their commit. Its [packaging provenance](review/tested-package-provenance.json) therefore correctly records a modified source state; the per-file hashes identify the tested bytes. No schema, vocabulary, solver, exercise recipe, native workout store or workout ownership changes are part of this browser work.

## OpenGym host validation

The actual OpenGym guest sheet was tested in a disposable checkout of revision `e4a68a94c42a3c17cbd560d66ce2e46a7048ab99` using the proposed exact `0463` mapping and the final flat runtime package. **69 targeted host tests passed in 7 files**. All 25 locale files are synchronized at 5846 keys after 425 additions; rerunning the locale helper adds nothing. Default-off and enabled production builds both passed. The default-off build excludes the preview runtime, renderer chunks and CSS. See the [host receipt and logs](review/opengym/README.md) and [source hashes](review/opengym/summary.json).

English and German mobile-size journeys passed in Chrome 157.0.8103.78 using the actual Home → Exercises → front-plank detail sheet. They cover deferred loading, real WebGL rendering, paused startup, explicit play/pause, keyboard scrub and disclosure/camera controls, hide/reopen focus, and actual WebGL context-loss fallback. Scoped axe scans reported zero violations in both languages. The existing Media node remained connected; the guest store was byte-identical across all EML actions. [Preview and fallback captures](review/opengym/README.md) were visually inspected.

The first German journey found that a long text alternative placed before the controls could scroll the canvas offscreen when pressing Play. The final layout places compact playback controls immediately below the canvas and retains the full text alternative below them. Both languages now pass. The unavailable message was shortened so it does not promise that independently owned host media is playable.

These host runs use stubbed local API responses and no account/backend/native transport. Original stock animation assets were not checked out, so the existing Media tile stayed in its own unavailable state; existing media-selection tests pass, but stock clip playback is not claimed. German preview controls are translated while exercise text preserves the host's existing language fallback. The browser journeys used HTTP development mode, where OpenGym does not register its production service worker. A separate deterministic [production-list inspection](review/opengym/service-worker.json) confirms that enabled HTTPS installs precache the preview/renderer JS and CSS under OpenGym’s existing offline policy; no exported model/clip files appear in the install lists. Caching code does not execute it or allocate WebGL. Disabled builds contain no preview code/style chunks, but Vite still copies any staged public files: stage `public/eml-pilot/` only for enabled deployments. This inspection is not an HTTPS browser network test. No OpenGym deployment was changed. [Optional insertion and policy guide](OPENGYM.md).

## Reproduction and evidence scope

Run the commands in [the integration README](README.md#reproduce-verification). The full Playwright attachment report and original transient artifacts remain at `/tmp/eml-browser-validation-20261117`; compact results, source hashes, text logs and all 15 inspected captures are retained in `review/`. Test dependencies and generated assets remain ignored.

These are source, local browser and local packaging results. Physical mobile GPU behavior, screen-reader speech and public deployment remain separate evidence boundaries. The preview's native buttons, fallback and text alternative continue to work without changing exercise IDs, media precedence, workouts or confirmed results.

## Later Linux fixture correction

The initial Linux workflow found enlarged host-heading overflow outside the preview. A fixture-only wrapping correction and more precise overflow diagnostics passed a separate complete local rerun (43 passed, zero failed, one unsupported-emulation skip). The original receipt and captures above remain unchanged; [the correction record](review/ci-fixture-correction/README.md) preserves the failing Linux evidence, diagnosis and rerun results.
