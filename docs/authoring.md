# Supply a new exercise

Start with [interface.json](../interface.json), which links the schema, the two movement libraries, the equipment vocabulary and the rig. From a checkout, `python -m eml interface -o interface-full.json` emits their definitions together. A programmatic author receives the same contract as a human author. The only executable input is a validated EML document; instructions written as prose are display text.

1. Choose a stable ID and a starting posture. Set the stance or support surfaces.
2. Give each implement its own instance ID. Choose whether its transform is controlled in the world or follows a joint. Specify which hands, feet or independent attachments use which sockets.
3. Define phases with durations and named motions. Compose motions or add local definitions for a new technique. Override only the joint axes that require refinement.
4. Choose the repeat mode and count. Color primary and secondary muscle groups. Describe a working side or different phase roles when relevant.
5. Validate the resulting document. Inspect at setup, deepest excursion, return and each support change. Save the document and any parameter values, including when using a remotely generated instruction.

[Paused goblet squat](../examples/paused-goblet-look-left.json) changes stance, depth, pause and head turn without changing the global squat motion. [Diagonal reach](../examples/diagonal-reach.json) defines its own posture and compound motion, then reaches a world point with the right hand. [Travel cycle](../examples/traveling-reach.json) illustrates accumulated root displacement.

```sh
python -m eml validate examples/paused-goblet-look-left.json --set depth=0.66 --set stance-width=0.42
python -m eml sample examples/paused-goblet-look-left.json --seconds 2.2
python -m eml compile examples/diagonal-reach.json --fps 18 -o out/reach.json
```

To send a new file programmatically:

```python
from eml import Program, load
from eml.checks import check

program = Program(load("examples/paused-goblet-look-left.json"), {"depth": 0.66})
report = check(program)
if report["issues"]:
    raise ValueError(report["issues"])
frame = program.playback(2.2)                 # finite repetitions and final hold
clip = program.compile(fps=18)               # a reusable cycle for a player
```

The CLI writes machine-readable diagnostics and returns a nonzero exit code for invalid input. Fields use the paths and units in the normative spec. For example, an unknown action reports `unknown-motion`, an impossible equipment relationship can report `cyclic-driver`, and an unreachable pinned grip reports `unreachable-contact`. The CLI compile path checks the requested sample frames as well. Never repair an unsupported instruction simply by changing its exercise ID.

For catalog entries add `exercises/<id>.json`. For a generally reusable pose or movement, contribute a library definition and at least two uses or a conformance fixture. An exercise can be authored completely locally before a catalog change.

Some starting symbols are immediately recognizable: `standing`, `seated`, `supine`, `kneeling`, `quadruped`, `high-plank`, `split-stance`, and `goblet-hold`. Useful action names include `squat-upright`, `hip-hinge`, `horizontal-press`, `row-to-torso`, and `rise-on-toes`. The specialist poses and motion definitions are also public and can be inspected in the interface.

For example, “a little wider than shoulder width, toes slightly out” can be authored as:

```json
{"pose":"goblet-hold","stance":{"width":{"of":"shoulder-width","factor":1.15},"toeOut":"slight-out"}}
```
