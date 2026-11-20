# Optional browser preview capture review

Partial browser review captured on 17 November 2026. All fifteen PNGs were opened and inspected after the final passing browser matrix. They are selected states from standalone integration fixtures, not a claim that OpenGym's full product UI was visually reviewed or deployed. Existing review history is unchanged.

| Captures | Observed state |
| --- | --- |
| [Chromium paused](captures/chromium-paused-render.png), [WebKit paused](captures/webkit-paused-render.png) | Original media remains alongside an explicitly opened, initially paused EML 1.1 squat preview. |
| [Chromium enlarged](captures/chromium-narrow-enlarged-controls.png), [WebKit enlarged](captures/webkit-narrow-enlarged-controls.png) | 320 CSS-pixel viewport, 200% text, camera controls expanded; labels and controls wrap without horizontal overflow. |
| [Chromium RTL](captures/chromium-rtl-long-labels.png), [WebKit RTL](captures/webkit-rtl-long-labels.png) | Long Arabic control labels and RTL flow; numeric current/total clock preserves its order. The fixture intentionally supplies only some translations. |
| [Chromium dark](captures/chromium-dark-paused.png), [WebKit dark](captures/webkit-dark-paused.png) | Paused after explicit playback; instructions, slider and attribution remain readable against the host's dark background. Different captured times reflect the test's explicit pause, not an engine synchronization assertion. |
| [Chromium forced colors](captures/chromium-forced-colors.png) | Keyboard Play focus remains visible, with native control affordances and readable text. WebKit forced-colors emulation is not available. |
| [Chromium legacy](captures/chromium-legacy-render.png), [WebKit legacy](captures/webkit-legacy-render.png) | EML 1.0 diagonal-reach clip with its matching equipment registry and text alternative. |
| [Chromium packaged](captures/chromium-packaged-preview.png), [WebKit packaged](captures/webkit-packaged-preview.png) | The copy-ready package renders through its own relative renderer imports, then pauses after explicit playback. |
| [Chromium mobile](captures/chromium-mobile-long-instructions.png), [WebKit mobile](captures/webkit-mobile-long-instructions.png) | 390 × 844 CSS-pixel viewport with long host instructions; Play remains adjacent to the visible canvas and playback advances before explicit Pause. |

The [summary](summary.json) records each capture's test name, engine, dimensions and SHA-256, plus the inspected source hashes and verification limits. [Verification report](../VERIFICATION.md).

The code uses EML's MIT license. Anatomy imagery retains the model's separate [BodyParts3D attribution and CC BY-SA terms](../../../anatomy/rebuild/ATTRIBUTION.md); these captures do not relicense those assets. No OpenGym exercise media is included.
