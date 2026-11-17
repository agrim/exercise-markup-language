# Linux test-fixture correction — 17 November 2026

The first [Linux browser workflow](https://github.com/agrim/exercise-markup-language/actions/runs/44042856166) on source `7dfdf1d` reported **41 passes, two failures and one skip**. Both failures were the whole-document horizontal-overflow assertion at 320 CSS pixels and 200% text.

The downloaded trace frames identify the overflowing content: the test fixture's unscoped **Exercise details** heading. The word **Exercise** extends past the right viewport edge before the preview opens, under Linux's system-font metrics. The original-media button wraps, and the preview controls remain inside the content width. These original trace frames were opened and visually inspected: [Chromium](chromium-linux-host-heading.jpeg), [WebKit](webkit-linux-host-heading.jpeg). The [original CI log](linux-initial-failure.log) is retained.

The correction is limited to test infrastructure:

- [Fixture CSS](../../tests/fixtures/fixture.css) allows the host `h1` to wrap with `overflow-wrap: anywhere`.
- [Browser test](../../tests/preview.spec.mjs) checks the enlarged host before opening and again with the camera controls open. Failure messages now include overflowing element names, text, bounds and scroll/client widths. The whole-document check remains; no overflow is hidden or clipped.

After regenerating the real bundle and package, the complete local macOS Chromium/WebKit matrix passed again: **43 passed, zero failed, one unsupported WebKit forced-colors skip**, across 22 scenarios in **47.565 seconds**. [Rerun log](macos-rerun.log), [per-scenario results and changed test-source hashes](summary.json).

The browser runtime, React adapter, preview CSS, renderer, exporter and packager hashes match the [original macOS receipt](../summary.json). That receipt and its 15 reviewed captures are preserved unchanged. This correction does not change the package already integrated into Simple Trainer.

The local rerun is not a claim that the corrected Linux workflow passed. Subsequent Linux results are available in the [browser workflow history](https://github.com/agrim/exercise-markup-language/actions/workflows/web-preview.yml).
