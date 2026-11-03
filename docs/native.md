# Test an EML movement in the Apple wrapper

The reference interpreter produces resolved animation. The optional Metal adapter converts its body and equipment transforms into the native player's EXM1 buffers. It writes a disposable workspace and leaves the source checkouts alone. The anatomical mesh, weights, motion and equipment geometry in that workspace come from this repository. The Swift view, shader and app target come from [the model wrapper](https://github.com/agrim/3d-human-exercise-model).

Clone the two repositories as siblings. From the EML checkout, run:

```sh
python tools/metal_preview.py --wrapper ../3d-human-exercise-model --out /tmp/eml-metal-demo \
  exercises/goblet-squat.json examples/paused-goblet-look-left.json
open /tmp/eml-metal-demo/HumanExerciseModels.xcodeproj
```

Select the HumanExerciseModels scheme and run. Omit the recipe paths to compile the entire catalog. Use a new output directory per export. For only the resources, `python -m eml native exercises/goblet-squat.json -o out/native-pack` produces the mesh, manifest and tracks without copying a wrapper.

The existing wrapper demonstrates one repeating cycle, uses clip-level muscle palettes and requires at least one primary muscle. The adapter rejects traveling repeats, one-shot actions, per-phase palettes and empty primary roles. Finite rep playback, holds, travel accumulation and phase-specific roles are defined in EML and available through the reference player. Displayed station geometry is illustrative. The native adapter samples a cycle offline so the iPhone can animate it without a Python interpreter.
