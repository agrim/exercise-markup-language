# Posture and clearance in EML 1.1

A v1.1 recipe receives the `studio-humanoid/1.1` animation profile automatically. A strict compile rejects a failing measurement. A non-strict preview supplies the pose and its diagnostics so an author can locate and correct it. The same file ID can describe different motion, and no check branches on an exercise ID. A v1.0 recipe retains its published vocabulary, equipment and solver behavior and does not acquire the new fields or validation rules.

These are geometric budgets for this educational rig, not clinical limits, exercise advice, proof of safe technique or a simulation of forces. An adapter must retain the reported unit. Degrees cannot be converted to millimetres.

| Automatic check | What is measured on the solved frame |
| --- | --- |
| Wrist | In the parent forearm's rest frame, compare its longitudinal axis (forearm centre to hand centre) with that axis after the **local hand** rotation. Deflection over 95° or absolute axial twist over 95° fails. Twist uses swing–twist decomposition about the shaft axis. Shoulder orientation, forearm pronation and turning the entire body do not by themselves count as wrist twist. A 180° singular swing fails deflection. |
| Elbow | Compare the bind wrist direction with its solved direction in the upper arm's frame, projected perpendicular to the rig's +X hinge. Signed bend must lie in [−165°, +25°], and the change in inclination out of that plane must not exceed 55°. Negative is flexion on this rig. Twisting around the forearm bone without moving its direction does not bend the elbow. |
| Knee | Apply the corresponding test from the shin joint toward the ankle. Signed bend must lie in [−12°, +165°], with up to 45° change in inclination. Positive is flexion. |
| Floor | No solved joint centre or measured rig landmark may be more than 12 mm below world Y = 0. |
| Equipment core | For free-weight visual components, reconstruct shaft capsules and ball/bell cores in their actual item space and track their parent transform. Test them against deep torso, neck, thigh and shin capsules. More than 5 mm penetration into an inner core fails. This deliberately distinguishes crossing the body from touching its surface. |

Core endpoints are pelvis–chest (65 mm radius), chest–neck (72 mm), neck–head (45 mm), thigh–shin (42 mm) and shin–foot (27 mm). A straight bar or dumbbell's shaft uses the viewer’s 14.5 mm radius. A rod's capsule fits inside its flat ends. A ball's core uses its smallest radius. A kettlebell's core follows the location of its rendered bell, not the centre of the handle. No whole-rack bounding box is treated as solid. Default core checks omit plates, handles, fixed stations, hands and unmodeled soft tissue. An authored capsule can represent an additional feature where its dimensions matter.

## Authoring assertions

Add an optional `constraints` array to a v1.1 exercise. A constraint applies throughout each rep unless its `phases` list names only certain phases. Missing phases, joints, sockets or parts are errors. Numeric sockets accept either literal numbers or declared parameter references and are checked again after binding. Bounds constrain measured post-IK geometry; they neither clamp an authored pose nor release a grip. For the four kinds:

- **hinge** measures a joint's signed directional bend and off-plane deviation as described above. `axis` is in the parent's bind space. `child` is optional if the joint has exactly one child; specify a direct child for any branching joint. `joint:"bothForearm"` expands to both actual joints using the same declared axis. A bone aimed along its hinge axis has no projected bend; where a signed limit is required this is reported.
- **orientation** measures the angle from a solved joint's rotated local `axis` to a `direction`. The direction is in world space unless `relativeTo` identifies a joint or item, in which case it rotates with that reference. Axes need not be unit length but must be nonzero. One direction constrains two rotational degrees of freedom; add a second noncollinear direction when twist matters. A correctly oriented palm is not inferred from a met grip point.
- **clearance** measures the shortest distance from a rigid item's transformed segment to a body segment, minus the two capsule radii. `from` and `to` are local metric triples or registered item socket names. `bodyFrom` and `bodyTo` are joint centres or measured landmarks. Repeated endpoints make a sphere. The optional `min` signed gap defaults to 0 metres. Negative gaps mean overlap. With a swept shaft use the actual endpoints, not just its centre.
- **support** measures a landmark or joint plus an optional local `offset` against `floor` or a finite pad. `min` and `max` bound signed normal distance in metres; an equipment surface uses the transformed +Y face of the box at the named zero-based `part` index in its registry `visual`. Distance outside that face's X/Z rectangle must be within `edgeTolerance` (default 0). A floating body or a level but misplaced pad fails. The existing `supports` list remains a teaching annotation. Use this geometric constraint to verify a point of support, and an EML contact if IK must move an effector there.

For example, an author may test a curling hand relative to its forearm, a straight bar against the left shin and a heel against a pad. The item IDs, phase ID, rod dimensions and pad index must refer to the actual authored exercise.

```json
"constraints": [
  {"kind":"orientation","joint":"leftHand","axis":[0,-1,0],"direction":[0,-1,0],"relativeTo":{"joint":"leftForearm"},"maxAngle":25,"phases":["curl"]},
  {"kind":"clearance","item":"bar","from":[-0.5,0,0],"to":[0.5,0,0],"radius":0.0145,"bodyFrom":"leftShin","bodyTo":"leftFoot","bodyRadius":0.04},
  {"kind":"support","landmark":"leftHeel","surface":{"item":"platform","part":0},"min":-0.005,"max":0.012,"edgeTolerance":0.01}
]
```

## Diagnostics and catalog audit

A failing frame contains `reason`, `effector`, `phase`, `time` in cycle-local seconds, and zero-based `cycle`. `path` is the recipe field that introduced the check or `/eml` for the automatic profile. `unit` is `m` or `deg`, `measured` is the actual value, `limit` is the violated bound, and `residual` is the amount beyond it. A geometrically undefined hinge has a reason and unit but no measured value or bound. Existing point-contact checks also retain their world target and achieved point. Strict validation samples phase interiors and both sides of every boundary at least 24 times per second for v1.1, adds exported sample times during compile and evaluates later travelling reps against world-fixed geometry. Ordinary repeats replay the same cycle. Verification is bounded to 120,000 evaluations in each pass. Sampling is not exact continuous collision detection.

Run `python tools/audit_posture.py -o posture.json` from the repo, optionally with `--parameter-limits` for each parameter's minimum/maximum in isolation. Results include per-exercise coverage, worst pose, affected phase, residual and units. Each phase is sampled at least nine times and at 24 Hz by default. It also analyses v1.0 clips without modifying them. The authoring report applies additional *advisory* screens:

- Detect hard pins slipping more than 12 mm within a phase, measuring an equipment pin in its item's local space. An effector moving intentionally during a reach is not a planted pin.
- Compare both sides of boundaries and loop seams, including item transforms. Flag excessive local rotation rates (over 720°/s **and** over 8° in one sampled interval). This is a review threshold, not a ban on fast athletic movement.
- Compare annotated supported body segments with floor or actual finite padded faces, allowing coarse tissue radii and 60 mm extra uncertainty. An authored support for the same landmark and surface takes precedence and measures its specified face and offset instead. Surfaces lacking either measurement are listed as unmeasured. This estimate cannot establish load bearing or balance.
- Measure the lowest illustrated free-weight component against the floor with a 12 mm allowance. This includes tilted shafts and plates, dumbbell heads, trap-bar rails, balls, boxes and the kettlebell bell and handle.
- Screen deep forearm-through-torso and paired load overlap using interior proxies. Review planned hand/chest contact and paired equipment in context. These are screening findings, with neither mesh collision nor multi-body dynamics implied.

Collision coverage is explicitly limited. For example, a clear shaft does not prove the plates clear the rack or the fingers are comfortable, and these checks cannot grade breathing, load, muscle physiology, fatigue or exercise appropriateness. Use the actual viewer at the identified phases. The mesh floor audit in `tools/audit_floor.py` provides a distinct skinned-surface measurement.

### Rate between solved poses

Strict v1.1 validation and compiled preview frames measure the angular change between consecutive poses of each major joint. A rate over 720 degrees per second yields `fast-local-rotation` with the measured rate, phase, time and joint. Increase the phase duration or shorten the movement. This limit is a reference playback envelope rather than a training or medical threshold. Single-pose samples have no interval to measure.
