# Optional EML preview for OpenGym

This is a contribution proposal and a reviewed example mapping, not an installed OpenGym feature. The proposed pilot maps exactly **`"0463"` → `exercises/plank.json`**. It neither rewrites exercise records nor supplies workout targets or confirmed results.

The reviewed OpenGym revision is [`e4a68a94c42a3c17cbd560d66ce2e46a7048ab99`](https://github.com/DuarteSantos8/openGym/tree/e4a68a94c42a3c17cbd560d66ce2e46a7048ab99). Its [`exercises-data.js`](https://github.com/DuarteSantos8/openGym/blob/e4a68a94c42a3c17cbd560d66ce2e46a7048ab99/frontend/src/lib/exercises-data.js) identifies `0463` as front plank, with bodyweight equipment and isometric semantics. Its [`English instructions`](https://github.com/DuarteSantos8/openGym/blob/e4a68a94c42a3c17cbd560d66ce2e46a7048ab99/frontend/src/instr/en.js) describe support on the forearms and toes with an extended trunk; the EML recipe demonstrates that setup. This comparison supports a proposed mapping, not coaching approval or a catalogue-wide equivalence rule. Keep IDs as strings, including the leading zero.

## Prepare the pilot

1. **Pin the reviewed EML source.** Run `python integrations/web/package_preview.py --out /tmp/eml-preview-package` and copy that complete directory to `frontend/src/vendor/eml-preview/`. Keep its renderer, component, styles, license and provenance together; the packager preserves their relative module paths. Copy the original `integrations/web/opengym/OptionalEMLMedia.jsx`, `integrations/web/opengym/EMLPilot.jsx` and `integrations/web/opengym/OptionalEMLMedia.test.jsx` files to `frontend/src/components/`. The reference Python viewer is a local authoring tool; deploying its server is unnecessary.

2. **Export the explicit mapping.** From the EML repository root, with its Python dependencies installed:

   ```sh
   python integrations/web/export_bundle.py \
     --mapping integrations/web/opengym-pilot.example.json \
     --out /tmp/opengym-eml-pilot --fps 12
   ```

   For the supplied adapter, copy its generated `manifest.json` to `frontend/src/components/optional-eml-manifest.json`. Stage the complete exported bundle at `frontend/public/eml-pilot/` only for a deployment built with `VITE_EML_PREVIEW=1`; omit that public directory from disabled deployments because Vite copies public files regardless of the flag. The manifest and assets must come from the same export. The generic component accepts the generated manifest as static imported JSON and its directory as `baseURL`. The preview itself requests no renderer or exported model/clip assets while disabled or closed. On enabled HTTPS web deployments, OpenGym’s existing service worker separately precaches JS/CSS chunks, including the optional preview and renderer code, at install. It does not precache the exported model/clip payload or execute the cached renderer. Keep that existing offline policy; [the generated-list receipt](review/opengym/service-worker.json) distinguishes code caching from preview activation. A new export uses a new destination. The recipe's five-second hold is a demonstration cycle, not the host's prescribed hold duration.

3. **Add one optional destination.** Import `OptionalEMLMedia` from `./components/OptionalEMLMedia.jsx` in `frontend/src/sheets.jsx`, and insert `<OptionalEMLMedia ex={ex} />` immediately after the existing `<Media ex={ex} />` in [`ExerciseDetail`](https://github.com/DuarteSantos8/openGym/blob/e4a68a94c42a3c17cbd560d66ce2e46a7048ab99/frontend/src/sheets.jsx), keeping that media component intact. It owns stock animation fallback, user-uploaded media and their precedence. Do not insert EML into all media consumers, workout cards or the workout store. The supplied adapter enables the pilot only with `VITE_EML_PREVIEW=1` at build time; its ordinary build excludes the preview runtime and styles. It suppresses the adjunct for the host's Hidden or Still only preference. Enable it only for an explicitly mapped, available, non-custom exercise and when the host's media policy permits it; do not infer custom status from a name or from the `custom` flag alone. OpenGym's existing `isCustomEx(ex)` handles imported custom records too.

4. **Retain the small host adapter.** `OptionalEMLMedia.jsx` is the default-off, lazy build-flag boundary; `EMLPilot.jsx` imports the static manifest and flat runtime. It supplies the exact catalogue ID, `exerciseNameFor(ex)`, `descFor(ex)` and `instrFor(ex)` from the existing host, subscribes to `useLang()`, and passes translated native-control labels. Its asset URL uses `import.meta.env.BASE_URL`, so the same layout also supports a deployment subpath. No new persisted setting is needed. `EMLPreview` itself defaults to `enabled={false}`; its optional `onUnavailable` callback may be omitted. Opening the adjunct must never write workouts, remove `Media`, or change own/stock media precedence.

5. **Keep translation and accessibility in the host flow.** The supplied adapter resolves the component's label map through OpenGym's translation system. Apply the 425 original additions for all 25 locale files with `node integrations/web/opengym/add-locales.mjs /path/to/openGym/frontend`; `--check` reports missing additions without writing. It preserves existing translations and validates placeholders. See [translation notes](opengym/TRANSLATIONS.md). Subscribe to the existing `useLang()` updates and pass the localized exercise name, description and instructions; do not replace them with English EML recipe text. Preserve the component's labelled native controls, visible focus, text alternative and credits. Check a long translation and RTL layout. It opens paused, plays one inspection cycle only after an explicit action, and pauses when hidden or offscreen. Camera buttons provide alternatives to dragging and pinching.

6. **Verify the optional boundary in OpenGym.** Exercise disabled, unmapped, missing and custom cases; existing own/stock media selection; load failure and unavailable WebGL; opening/closing repeatedly; changing exercise while loading; backgrounding and reduced motion; keyboard-only operation and narrow/zoomed layouts. Confirm that the existing media component and localized instructions remain intact, no exported model/clip requests or WebGL allocation occur before opening (allow the host’s documented code/style precache), and no workout/store writes occur. Run the component's browser and lifecycle checks from the [web integration guide](README.md). In `openGym/frontend`, run:

   ```sh
   VITE_EML_PREVIEW=1 npm exec vitest run src/components/OptionalEMLMedia.test.jsx src/components/Media.test.jsx src/components/Animations.test.jsx src/sheets.aliases.test.jsx src/sheets.custom-edit.test.jsx src/sheets.history.test.jsx src/lib/pt-br-locale.test.js
   node scripts/check-locales.mjs
   npm run build
   VITE_EML_PREVIEW=1 npm run build
   ```

   The reviewed host results are recorded in [verification](VERIFICATION.md#opengym-host-validation); a standalone component test is not evidence that the host sheet integration passed.

7. **Retain attribution and payload semantics.** Ship the exported license and anatomy attribution, with a visible credits route. The V3 credits identify the MakeHuman core art, its CC0 dedication and the EML rig profile. Keep model/equipment files paired with the compiled clip's EML version. Authored muscle highlights describe the demonstration; they are not physiological measurements, workout results or replacements for OpenGym's own muscle data.

8. **Propose the small patch for review.** Include the exact source revisions, one-entry mapping, export command, test results, screenshots and the chosen enablement policy. Recheck the current OpenGym ID, instructions, media flow and contribution requirements before submission. Ask maintainers to review the one movement before adding mappings. No account, backend, schema migration, language upgrade or catalogue import is required.

No OpenGym source, dataset or media is included in this EML contribution kit. The linked source informed this proposal; maintainers still decide whether to adopt it.
