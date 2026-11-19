# Supply a new exercise

Start with `python -m eml interface -o interface-full.json`. It emits the current structural schema, all pose and motion definitions, equipment kinds and socket coordinates, joint and muscle names, and the default posture profile. An application can consume this file when generating custom exercises. Its output is the same contract available to individual contributors. [Machine-readable discovery index](../interface.json)

For an upper-body movement, consult the 1.1 interface’s `compatibleSetups.setups` list. Each row names a starting pose, one or more motions and an example exercise. For example, pair `upper-overhand-hang-start` with `upper-vertical-body-pull`, then consult `pull-up` for its fixed bar and grip targets. The pair is tested at its default amplitude. Add the grip targets and geometry when equipment is part of the instruction. [Compatible upper-body setups](upper-motion-setups.json)

For a new exercise use `"eml": "1.1"`. For an existing document first read its own `eml` field, then request the matching interface. For example, `python -m eml interface --version 1.0` returns the historical schema and exact 1.0 macros and equipment. If editing a 1.0 file in place, keep its version. If upgrading it, review changes to pose definitions, macro endpoints and sockets in addition to any new posture findings. [Version and migration rules](specification.md#versions-and-migration)

1. Choose a stable ID and a starting posture. Set the stance or support surfaces.
2. Give each implement its own instance ID. Choose whether its transform is controlled in the world or follows a joint. Specify which hands, feet or independent attachments use which sockets.
3. Define phases with durations and named motions. Compose motions or add local definitions for a new technique. Override only the joint axes that require refinement.
4. Choose the repeat mode and count. Color primary and secondary muscle groups. Describe a working side or different phase roles when relevant.
5. Add a posture constraint when a specific relationship must hold, such as the chest resting on a bench pad or a hand facing along a handle. The rig checks solved wrists, elbows, knees, ground clearance and free weights automatically in 1.1. [Constraint kinds, examples and limits](posture.md)
6. Validate the resulting document. Inspect at setup, deepest excursion, return and each support change. Save the document and any parameter values, including when using a remotely generated instruction.

This complete 1.1 document demonstrates a three-rep standing curl using the published movement macro. At the endpoint of `return`, the empty action list restores the starting pose.

```json
{
  "eml": "1.1",
  "id": "my-standing-curl",
  "title": "Standing curl",
  "start": {"pose": "standing"},
  "phases": [
    {"id": "curl", "seconds": 1, "actions": [{"use": "bend-elbows", "amount": 0.8}]},
    {"id": "return", "seconds": 1, "actions": []}
  ],
  "repeat": {"mode": "loop", "count": 3},
  "muscles": {"primary": ["biceps"], "secondary": ["forearms"]}
}
```

[Paused goblet squat](../examples/paused-goblet-look-left.json) changes stance, depth, pause and head turn without changing the global squat motion. [Diagonal reach](../examples/diagonal-reach.json) defines its own posture and compound motion, then reaches a world point with the right hand. [Travel cycle](../examples/traveling-reach.json) illustrates accumulated root displacement.

## Chain movements in Python

Create a `Recipe` and supply one movement at a time. Each authoring method updates the same recipe and returns it, so you can build a chain or extend it across multiple statements. A new recipe defaults to EML 1.1, a standing start, one playback and empty muscle highlights. Pass `version="1.0"` to use the 1.0 schema and vocabulary. [Python API and JSON field mappings](python-api.md)

```python
from pathlib import Path

from eml import Program, Recipe

recipe = Recipe("curl-and-turn", "Standing curl with head turn")
recipe.move("bend-elbows", 1, amount=0.8, id="curl")
(
    recipe.phase(1, id="turn")
    .action("bend-elbows", 0.8)
    .action("turn-head", 0.25)
    .return_to_start(1, id="return")
    .muscles("biceps", "forearms")
    .repeat(3)
)

clip = Program(recipe).compile(fps=18)
Path("curl-and-turn.json").write_text(recipe.to_json() + "\n", encoding="utf-8")
```

`.move()` starts a new phase with one action. Use `.phase()` and successive `.action()` calls to combine movement macros at one endpoint. EML calculates each endpoint from the exercise's starting pose and interpolates from the preceding endpoint. The `turn` phase includes `bend-elbows` again to retain the curl while the head moves. The explicit return phase restores the setup for the next rep. [Phase and repetition rules](specification.md#phases-contacts-and-repetitions)

| To author | Use |
| --- | --- |
| A starting posture and stance | `.start("standing", stance={"width": "shoulder-width"})` |
| Phase timing and overrides | `.phase(seconds, id="lower", ease="linear", contacts=[])` or supply the same options to `.move()` |
| A return to the setup | `.return_to_start(seconds, id="return", ease="linear")`. Pass contact or support overrides here as needed. |
| Repeat mode, count or travel | `.repeat(3)` for a loop, or `.repeat(1, mode="hold")` for a held pose. A traveling loop can pass `travel=[x, y, z]`. |
| Equipment and a pin to its socket | `.equipment("platform", "incline-hand-platforms", position=[0, 0, 0.25]).contact("leftPalm", "platform", socket="leftPalm")` |
| Additional exercise-level fields | `.configure(**fields)` with standard EML field names and values |

Phase IDs default to `phase-N` when you omit `id`. Supply explicit IDs when referring to phases from a constraint. Use standard EML field names such as `rootAnchor` for phase overrides, and pass `contacts=[]` explicitly to release inherited contacts. `Recipe` accepts normal EML parameter references such as `amount={"param": "depth"}` in `.move()` or `.action()`, and `Program(recipe, {"depth": 0.65})` binds the value for that evaluation.

To extend an existing recipe, call `Recipe.from_document(load("exercise.json"))` with `load` imported from `eml`. The builder starts from an independent copy of the document, including its version, existing phases and optional fields.

`.build()` returns an independent, structurally validated EML dictionary with parameter references intact. `.to_json()` serializes the same recipe for the CLI, viewer and other EML consumers. `Program` accepts the builder or a recipe dictionary loaded from JSON. It resolves references and parameters, and strict compilation checks the solved movement in either case. For example, compiling a recipe that uses `.move("unknown-macro", 1)` raises the same `unknown-motion` error as loading a JSON recipe with that action.

The complete incline push-up example builds the catalog recipe with chained calls for the incline setup, palm contacts, pad geometry checks and intermediate phases. [Run the incline push-up example](python-api.md#author-a-supported-movement)

## Validate and compile

```sh
python -m eml validate examples/paused-goblet-look-left.json --set depth=0.66 --set stance-width=0.42
python -m eml sample examples/paused-goblet-look-left.json --seconds 2.2
python -m eml compile examples/diagonal-reach.json --fps 18 -o out/reach.json
```

Load and evaluate an existing JSON recipe from Python as follows.

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

The CLI writes machine-readable diagnostics and returns a nonzero exit code for invalid input. A solved 1.1 posture finding identifies the affected body part, source path, phase, time, repetition, measured value, exceeded limit and unit. Use the reported phase and time to locate the pose. The local viewer and `program.compile(fps=18, strict=False)` allow inspection of a structurally valid document with movement findings. A normal `compile` remains strict. Fields use the paths and units in the normative spec. For example, an unknown action reports `unknown-motion`, an impossible equipment relationship can report `cyclic-driver`, and an unreachable pinned grip reports `unreachable-contact`. The CLI compile path checks the requested sample frames as well. Never repair an unsupported instruction simply by changing its exercise ID.

## Ground movements and support

The compatible-setup map includes floor, incline and kneeling push-ups, quadruped reaches and diagonal bear steps. Each listed motion can be evaluated directly from its paired posture. The floor, kneeling and incline press macros declare `fixedPoints` for both palms. The straight-leg variants also pin both forefeet. These pins hold the attained setup positions during lowering and return. To specify the hand orientation and the actual bearing surface, or to alternate supporting limbs during a reach or crawl, copy the row’s complete `support` object into the document. It supplies ordinary EML fields, including phase-specific contacts that release a reaching limb. Existing exercise-level contacts continue to follow the normal replacement rules. [Verified setup and support templates](upper-motion-setups.json)

```python
from eml import Program, interface

rows = interface("1.1")["compatibleSetups"]["setups"]
setup = next(row for row in rows if row["pose"] == "high-plank")
doc = {
    "eml": "1.1", "id": "my-ground-press", "title": "Ground press",
    "start": {"pose": setup["pose"]}, "repeat": {"mode": "loop", "count": 3},
    "muscles": {"primary": ["pectorals"], "secondary": ["triceps"]},
    **setup["support"],
}
clip = Program(doc).compile(fps=24)
```

The incline template includes two raised pads with an open channel for the chest. Each hand has its own socket and a constraint that measures the skinned hand’s offset against that pad’s finite top face. Quadruped reaches and bear steps pin the supporting diagonal and let the opposite limbs move. When changing a supporting limb, surface, step order or equipment height, update its contact and support declarations and validate the new sequence.

For catalog entries add `exercises/<id>.json`. For a generally reusable pose or movement, contribute a library definition and at least two uses or a conformance fixture. An exercise can be authored completely locally before a catalog change.

The 1.1 `squat-down`, `squat-upright`, and `hip-hinge` motions hold the heels and balls of the feet at their setup positions. A new exercise can start from `standing` and describe a controlled half-depth rep with two phases.

```json
[
  {"id":"lower","seconds":1.5,"actions":[{"use":"squat-down","amount":0.5}]},
  {"id":"stand","seconds":1.5,"actions":[]}
]
```

Authors can publish the same behavior on a custom pose or motion with `"fixedPoints":["leftHeel","leftBall","rightHeel","rightBall"]`. A phase with `"contacts":[]` releases the inherited pins. An equipment or world-point contact on one foot takes precedence for that foot while the other foot can keep its inherited support.

Some starting symbols are immediately recognizable: `standing`, `seated`, `supine`, `kneeling`, `quadruped`, `high-plank`, `split-stance`, and `goblet-hold`. Useful action names include `squat-upright`, `hip-hinge`, `horizontal-press`, `row-to-torso`, and `rise-on-toes`. The specialist poses and motion definitions are also public and can be inspected in the interface.

For example, “a little wider than shoulder width, toes slightly out” can be authored as:

```json
{"pose":"goblet-hold","stance":{"width":{"of":"shoulder-width","factor":1.15},"toeOut":"slight-out"}}
```
