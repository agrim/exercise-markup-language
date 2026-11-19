# EML Python authoring API

Use `eml.Recipe` to build an exercise a few calls at a time. The result is an ordinary versioned EML document. `eml.Program` evaluates a builder or a document dictionary through the same solver. The viewer and CLI consume the exported JSON. [JSON authoring guide](authoring.md) · [EML specification](specification.md)

[Quickstart](#quickstart) · [Discover symbols](#discover-symbols) · [Method reference](#method-reference) · [Examples](#examples) · [Validate and share](#validate-and-share)

## Quickstart

Run with Python 3.11 or later from a checkout with `requirements.txt` installed, or install the library with `python -m pip install .` from the checkout.

```python
from pathlib import Path

from eml import Program, Recipe

squat = (
    Recipe("half-depth-squat", "Half-depth squat")
    .move("squat-down", 1.5, amount=0.5, id="lower")
    .return_to_start(1.5, id="stand")
    .repeat(3)
    .muscles(["quadriceps", "glutes"])
)

clip = Program(squat).compile(fps=24)
Path("half-depth-squat.json").write_text(squat.to_json() + "\n", encoding="utf-8")
```

The builder defaults to EML 1.1, the `standing` pose, one playback and empty muscle roles. The example adds a half-amplitude descent, an explicit return and three repetitions. The compiled clip contains one cycle and its repeat policy. Use `Program(squat).playback(seconds)` to sample across repetitions.

Each `.move()` appends a timed phase. Add further `.action()` calls to the current phase to combine macros at the same endpoint. Each endpoint is calculated from the original setup, and playback interpolates from the preceding endpoint. For example, keeping a curl while turning the head takes both `bend-elbows` and `turn-head` in the new endpoint. [Curl and head-turn example](authoring.md#chain-movements-in-python) · [Phase and repetition rules](specification.md#phases-contacts-and-repetitions)

## Discover symbols

Use the interface for the recipe's `eml` version to look up pose and motion names, rig joints, effectors, muscle groups, equipment kinds and their sockets. The interface also includes the JSON Schema for optional fields and the 1.1 compatible setup map. Its `pythonAuthoring` object gives the builder's import name in `builder`, plus the `guide` and `example` paths relative to the EML resource directory. Find the catalog recipe for a tested pose and motion pairing and inspect its contacts, apparatus, timing and amplitude together. [Compatible setup map](upper-motion-setups.json) · [Interface index](../interface.json)

```sh
python -m eml interface --version 1.1 -o interface-full.json
python -m eml interface --version 1.0 -o interface-1.0.json
```

```python
from eml import interface

vocabulary = interface("1.1")
standing = vocabulary["poses"]["standing"]
squat_down = vocabulary["motions"]["squat-down"]
pads = vocabulary["equipment"]["incline-hand-platforms"]["sockets"]
```

Times are in seconds, distances in metres and authored rotations in degrees. The model faces +Z with Y up and +X toward its own left. Phase and starting pose roots are displacements from the bind pelvis. A motion definition's root adds a displacement to the setup. Use world coordinates for a fixed equipment position or direct contact point, and item-local coordinates for socket offsets. [Coordinate and angle conventions](specification.md#body-time-and-equipment-coordinates)

## Method reference

Authoring methods update and return the same `Recipe`. You can start a phase in one statement and add actions or overrides to it in later statements. `Recipe.param(name)` creates a parameter reference. `build()` and `to_json()` provide terminal representations. For raw JSON fields accepted as keyword arguments, use the versioned field names such as `rootAnchor` and `sideFocus` with JSON-shaped values. Vector arguments in the dedicated methods accept lists or tuples.

### Document, metadata and values

| Call | EML field and behavior |
| --- | --- |
| `Recipe(id, title, *, version="1.1")` | Writes `id`, `title` and `eml`. Pass `version="1.0"` for its historical schema, vocabulary and solver. |
| `Recipe.from_document(document)` | Starts an independent builder from a structurally valid document. Retains the existing version, phases and optional fields. |
| `.instructions(text)` | Sets `instructions`. |
| `.schema_uri(uri)` | Sets the optional `$schema` string for editor tooling. The `eml` field selects the actual EML version. |
| `.parameter(name, *, default, minimum, maximum)` | Writes `parameters[name]` with `default`, `min` and `max`. |
| `Recipe.param(name)` | Returns `{"param": name}` for a numeric field that accepts a parameter reference. |
| `.repeat(count, *, mode="loop", **fields)` | Sets `repeat.mode` and `repeat.count`. A traveling loop can pass `travel=(x, y, z)` in metres. Use `mode="once"` with a count of 1 or `mode="hold"` with a static pose. |
| `.muscles(primary=(), secondary=(), *, phase=False)` | Sets the two role arrays at the document or current phase. Each argument can be a single group name or an iterable of names. |
| `.camera(yaw, pitch)` | Sets `camera` to `[yaw, pitch]` in degrees. |
| `.side_focus(groups)` | Sets `sideFocus.groups` to active exercise muscle groups, then use `.focus_interval()` to assign time ranges. |
| `.focus_interval(side, start, end)` | Adds to `sideFocus.intervals`. Use `"left"` or `"right"` and ascending, non-overlapping intervals in normalized cycle time from 0 to 1. |
| `.configure(**fields)` | Sets optional document fields by their JSON names. A supplied field replaces that whole field. Use the constructor and dedicated methods for `eml`, `id`, `title`, `start`, `phases`, `repeat` and `muscles`. |

### Setup and local definitions

Declare a local pose or motion before adding its joints or nested actions. Joint setters accept either an XYZ triple or one or more named axes. A triple replaces the entry for that joint. Named axes merge with the axes already authored there.

| Call | EML field and behavior |
| --- | --- |
| `.start(pose, **fields)` | Sets `start.pose` and replaces the start object. Optional start fields are `stance`, `root` and `joints`. |
| `.stance(width, *, toe_out=None, factor=None)` | Sets `start.stance`. Width can be in metres, relative to `"shoulder-width"` or `"hip-width"`, or an EML width object. `factor` turns a named width into a scaled width. `toe_out` writes `toeOut` in degrees or as `"forward"`, `"slight-out"` or `"out"`. |
| `.start_root(position)` | Sets `start.root` to an XYZ position relative to bind. |
| `.start_joint(joint, angles=None, *, x=None, y=None, z=None)` | Writes `start.joints[joint]` using an XYZ rotation triple or named axes. |
| `.define_pose(name, *, extends=None, root=None, fixed_points=None)` | Declares `definitions.poses[name]`. `extends` names a registered or local pose. `fixed_points` writes `fixedPoints` in 1.1. |
| `.pose_joint(name, joint, angles=None, *, x=None, y=None, z=None)` | Writes `definitions.poses[name].joints[joint]` for a local pose. |
| `.define_motion(name, *, root=None, fixed_points=None)` | Declares `definitions.motions[name]` with an optional root delta and 1.1 `fixedPoints`. |
| `.motion_joint(name, joint, angles=None, *, x=None, y=None, z=None)` | Writes `definitions.motions[name].joints[joint]` as a joint delta in the local motion. |
| `.motion_action(name, use, amount=1)` | Appends to `definitions.motions[name].actions`. The referenced motion contributes a scaled delta before the local motion's own deltas. |

### Phases

Phase methods select the last appended phase. Omitted phase IDs are generated as `phase-N`. Use explicit IDs to keep phase references readable as the movement changes.

| Call | EML field and behavior |
| --- | --- |
| `.phase(seconds, *, id=None, **fields)` | Appends a phase with an empty action list by default. Accepts raw `actions`, `detail`, `ease`, `items`, `contacts`, `supports`, `muscles` and `rootAnchor` fields. |
| `.move(use, seconds, *, amount=1, id=None, **fields)` | Appends a phase with one initial action and optional phase fields such as `ease` or `detail`. Add more motions with `.action()`, or use `.phase()` to supply a raw `actions` list. |
| `.action(use, amount=1)` | Appends to the current phase's `actions`. Amount is a multiplier and defaults to 1. |
| `.return_to_start(seconds, *, id=None, **fields)` | Appends an empty authored endpoint. Pass phase options such as `ease`, `contacts` or `rootAnchor`. Use `.phase()` for an endpoint with `actions` or `detail`. |
| `.ease(value)` | Sets phase `ease` to `"smooth"`, `"linear"`, `"ease-in"` or `"ease-out"`. The EML default is `"smooth"`. |
| `.phase_root(position)` | Sets `detail.root` for the current phase. |
| `.phase_joint(joint, angles=None, *, x=None, y=None, z=None)` | Writes `detail.joints[joint]` for the current phase after its action deltas have been applied. |
| `.phase_item(item, *, position=None, rotation=None, offset=None, control_position=None)` | Writes `items[item]` overrides for the current phase. Calls for the same item merge supplied fields. `control_position` writes `controlPosition` for a world-driven item's curved path into the endpoint. |

### Equipment, contacts and supports

For methods that accept `phase=`, the default targets the document regardless of call order. Use `phase=True` to target the last appended phase. The first contact or support added to a phase starts that phase's replacement list. Include every contact or support required by the phase. A phase without its own list uses the exercise-level rules. [Contact inheritance and release](specification.md#phases-contacts-and-repetitions)

| Call | EML field and behavior |
| --- | --- |
| `.equipment(id, kind, *, position=None, rotation=None, follow_joint=None, offset=None, grip=None)` | Adds an `equipment` instance for a registered kind. Use `position` for world placement or `follow_joint` with optional `offset` (zero by default) and `grip` to create `follow`. The item's `rotation` is relative to its driving joint when it follows one and in world space otherwise. |
| `.socket(item, socket, position)` | Writes the named `equipment` instance's `sockets` map with an item-local override for a registered socket. |
| `.connect(kind, from_item, from_socket, to_item, to_socket)` | Appends `connections` with item/socket endpoints. Use `"rope"`, `"cable"`, `"band"` or `"link"`. |
| `.contact(effector, target="start", *, socket=None, pole=None, rotation=None, engage=None, phase=False)` | Adds to `contacts`. Use `"start"`, `"floor"`, a world XYZ point, or an item ID with `socket=`. Optional `pole` guides the bend, `rotation` sets world orientation, and `engage="reach"` interpolates into contact. |
| `.clear_contacts(*, phase=False)` | Writes an empty `contacts` list at the selected scope. A phase-level empty list releases inherited contacts, including stance and motion pins. |
| `.support(body, surface, *, phase=False)` | Adds a `supports` teaching label. `body` names a joint or bilateral shorthand. `surface` is `"floor"` or an item ID. |
| `.clear_supports(*, phase=False)` | Writes an empty `supports` list at the selected scope. |
| `.root_anchor(joint, target="start", *, phase=False)` | Sets `rootAnchor` with a rig joint and setup or world XYZ target. |
| `.clear_root_anchor(*, phase=False)` | Removes the document anchor or writes `rootAnchor: null` in the current phase to release it there. |

### Posture constraints in EML 1.1

These methods append a `constraints` entry. Pass `phases="phase-id"` or an iterable of phase IDs to limit a check to those phases. Each assertion measures the solved pose. Use a contact when the solver should place an effector, and a support constraint when the resulting surface relationship should be checked. [Posture measurements and diagnostic units](posture.md)

| Call | EML field and behavior |
| --- | --- |
| `.hinge_constraint(joint, axis, *, minimum, maximum, max_swing, child=None, phases=None)` | Adds a `hinge` with `min`, `max` and `maxSwing` in degrees. Specify `child` when the joint branches. |
| `.orientation_constraint(joint, axis, direction, *, max_angle, relative_joint=None, relative_item=None, phases=None)` | Adds an `orientation` with `maxAngle` in degrees. Use `relative_joint` or `relative_item` to write `relativeTo` and measure the direction in that frame. |
| `.clearance_constraint(item, start, end, *, radius, body_from, body_to, body_radius, minimum=None, phases=None)` | Adds `clearance` with item-local `from` and `to` points or socket names. `bodyFrom` and `bodyTo` are rig joints or landmarks. `radius`, `bodyRadius` and optional `min` gap are in metres. |
| `.support_constraint(landmark, surface="floor", *, minimum, maximum, part=None, offset=None, edge_tolerance=None, phases=None)` | Adds a `support` with distances `min`, `max`, local `offset` and `edgeTolerance` in metres. For an equipment face, give the item ID and the zero-based box `part` index. |

### Export and execution

| Call | Result |
| --- | --- |
| `recipe.build()` | Independent, structurally validated EML dictionary with parameter references intact. |
| `recipe.to_json(*, indent=2)` | The same recipe serialized as JSON text. Open the resulting file as UTF-8. |
| `load(path)` | Load a recipe from UTF-8 JSON into a Python dictionary. |
| `Program(recipe_or_document, parameters=None)` | Resolve symbols and bind parameter values or defaults in a builder or dictionary. |
| `check(program)` from `eml.checks` | Return a conformance report with an `issues` list, including contact and posture findings. |
| `program.compile(fps, strict=True)` | Produce one resolved animation cycle and repeat metadata. Strict compilation checks solved motion and raises `eml.Error` on failure. |
| `program.playback(seconds)` | Sample absolute time across finite repeats and hold the final pose once playback ends. |

## Examples

### Compose and tune a local motion

Register a local macro with a parameterized curl and a fixed head angle. Move to that endpoint and back, then bind a depth for this evaluation.

```python
from eml import Program, Recipe

recipe = (
    Recipe("tunable-curl", "Tunable curl with a glance")
    .parameter("depth", default=0.8, minimum=0.4, maximum=0.9)
    .define_motion("curl-with-glance")
    .motion_action("curl-with-glance", "bend-elbows", Recipe.param("depth"))
    .motion_joint("curl-with-glance", "head", y=14)
    .move("curl-with-glance", 1.2, id="curl")
    .return_to_start(1.2, id="lower")
    .muscles("biceps", "forearms")
    .repeat(3)
)

clip = Program(recipe, {"depth": 0.65}).compile(fps=24)
```

### Author a supported movement

The incline push-up chain places two palms on raised pads, anchors both forefeet, measures contact against the finite pad faces and authors distinct lowering and pressing phases. The script runs strict compilation, then writes the same EML document as the catalog recipe. [Python source](../examples/fluent_incline_push_up.py) · [Catalog JSON](../exercises/incline-push-up.json)

```sh
python -m examples.fluent_incline_push_up incline-push-up.generated.json
python -m eml validate incline-push-up.generated.json
```

### Extend a JSON recipe

This example adjusts repetitions on an existing 1.0 recipe and evaluates it at a chosen depth. The builder retains the recipe's equipment, contacts, phases and 1.0 vocabulary.

```python
from eml import Program, Recipe, load

existing = load("examples/paused-goblet-look-left.json")
variant = Recipe.from_document(existing).repeat(2)
clip = Program(variant, {"depth": 0.65}).compile(fps=24)
```

## Validate and share

1. Use `recipe.build()` to inspect the document or `recipe.to_json()` to export it. Both enforce the versioned structure and preserve parameter declarations and references. Keep the override values alongside a parameterized file when sharing a specific evaluation.
2. Construct `Program(recipe, parameters)` to resolve pose and motion references, bind parameters and check the bound fields. `eml.Error.as_dict()` gives `code`, `path` and `message`. For example, a structurally valid `.move("unknown-macro", 1)` fails with `unknown-motion` at `/phases/actions` during reference resolution.
3. Run `check(program)` to inspect conformance issues or `program.compile(fps=24)` for strict compilation. Use `program.compile(fps=24, strict=False)` or the viewer to inspect a resolved clip with frame diagnostics. For a 1.1 posture issue, consult the phase, time, unit, measured value and limit in the report. [Posture diagnostics](posture.md#diagnostics-and-catalog-audit)

To preview an exported recipe, start `python -m viewer` from the repository root and open the JSON file in the viewer. To check or compile the same file in automation, use the CLI.

```sh
python -m eml validate half-depth-squat.json
python -m eml compile half-depth-squat.json --fps 24 -o half-depth-squat.clip.json
```
