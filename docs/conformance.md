# EML reference verification

## EML 1.1

The 108 catalog IDs now use the v1.1 solver and posture profile. The [strict catalog run](evidence/v1.1/catalog.json) exercised 9,564 poses with all authored constraints enabled. The [baseline screen](evidence/v1.1/baseline.json), run against the published 1.0 catalog, flagged 56 of the 108 exercises for review. Fixes cover planted support, joint bending and roll, equipment clearance, apparatus fit, contact changes and motion rate. The [paired atlas images](evidence/v1.1/upper-body.jpg) show the side plank, lateral raise and dumbbell shoulder press at comparable poses.

- **Parameter ranges.** The [declared minimum and maximum assignments](evidence/v1.1/parameters.json) passed across 197 programs and 40,980 sampled poses at 24 Hz. Fifty-two additional combinations of simultaneous lower and upper parameter bounds passed. The minimum duration was raised on 21 catalog movements, with their 1.6 s defaults preserved.
- **Bodies and apparatus.** The [finite machine-part and cable screen](evidence/v1.1/apparatus.json) measured 4,403 equipment poses. Its deep torso-overlap threshold is 12 mm against conservative core proxies. Compare the [same screen on 1.0](evidence/v1.1/apparatus-before.json). Targeted regressions also measure plates, shaft paths, hand sockets, supports and actual atlas vertices. In the [full skinned-floor sweep](evidence/v1.1/floor.json), the lowest sampled vertex is 4.2 mm below the reference plane.
- **New programs.** The [92 standalone starting poses](evidence/v1.1/starting-poses.json) pass the rig checks. The deepest sampled skin point among those setups is 3.2 mm below the floor. The [portable setup map](upper-motion-setups.json) supplies compatible motions, including templates for planted ground exercises. The [custom paused squat](../examples/personal-paused-squat.json) demonstrates inherited foot pins at different depths.
- **Version compatibility.** The 1.0 schema, vocabulary, equipment and solver behavior remain available by document version. All 108 original recipes reproduced their v1.0.0 reference results at 1,715 compared samples, including joint and equipment transforms.

Reproduce the release checks from the repository root with `python -m unittest discover -s tests`, `python -m eml catalog --samples 17 -o catalog.json`, `python tools/audit_posture.py --parameter-limits --fps 24 -o posture.json`, `python tools/audit_apparatus.py --samples 17 -o apparatus.json`, and `python tools/audit_floor.py --samples 9 -o floor.json`. The latter requires NumPy and SciPy. These measurements cover sampled poses, selected extrema, and the reference geometry. They do not establish continuous collision freedom for every possible exercise, load or parameter combination.

## Archived EML 1.0 verification

The v1 catalog contains the 108 original Simple Trainer IDs, split into 104 repeating movements and four holds. The language accepts additional IDs and never dispatches motion by ID. The [baseline fixture](../tests/fixtures/catalog-baseline.json) checks inherited catalog identity and muscle assignments. A new contributor can add an exercise without expanding a hardcoded allowable ID list.

## What the exercise examples required

| Catalog case | Behavior that determined the interface |
| --- | --- |
| Goblet squat | Two independent hands grasp separate sockets on one kettlebell. Width, toe angle and depth can vary without editing a motion clip. |
| Deadlift and trap-bar deadlift | Distinct handles, starting grip widths and a lifted rigid implement. The lower-body tests check arm extension and straight-bar clearance. |
| Straight-arm pulldown | A straight line between equipment endpoints made the elbow bend too far. The bar can now follow a quadratic arc with a per-phase control position. |
| Bench press and machine stations | A socket belongs to an instance in its own coordinate frame. Open equipment frames and separately movable pads, handles or footplates make supports visible. |
| Walking lunge, bear crawl and burpee | Support changes during a rep. The previous foot or hand must release, swing and land continuously. In-place demonstrations can loop; a separate travel example accumulates world displacement. |
| Bird dog and dead bug | Alternating contralateral limbs have explicit phases, with shared setup restored at the end. |
| Hanging pull-up and assisted dip | The body moves around fixed handles, with grip widths and support geometry declared separately. |
| Ab-wheel rollout | A root anchor keeps the knee stationary while the rest of the body rotates, including between authored endpoints. The wheel and its two grips continue to move. |
| Wall sit, forearm plank, side plank and hollow-body hold | A held pose occupies time without requiring an invented rep. A bench, forearm or back support annotation can be meaningful without an IK target. |

## Verification performed for v1

* The reference checker sampled 17 positions in each of 343 phases (5,831 samples). All 108 recipes passed contact, transition and repetition tests. The catalog runner also checks ID uniqueness and filename consistency. [Per-recipe results](evidence/catalog.json)
* The skin audit sampled nine positions per phase using all vertices of the actual weighted mesh. The deepest sampled intersection with the floor was **4.2 mm** (incline push-up and plank). The report includes each exercise, including those intentionally above the floor. [Surface measurements](evidence/floor.json)
* We checked 112 additional assignments of declared catalog parameters at their minimums, maximums, and combined extremes. The custom stance/depth/turn example and unknown-ID reach also compile and play. Tests cover joint override precedence, pose inheritance, bilateral reflection, contact ordering and impossible requests.
* The WebGL viewer loaded the 108 catalog recipes and three custom examples. A changed squat depth visibly changes the pose at the same cycle time. The Metal wrapper export rendered four native frames for each of the 108 exercises. [Browser sheets](../viewer/review/README.md)
* A reader implemented independently can compare its quaternion outputs with the [portable conformance vector](../tests/fixtures/portable-vector.json), including the untouched opposite arm and the closed loop.

Run `python -m unittest discover -s tests -v` and `python -m eml catalog --samples 17 -o out/catalog.json` from the repository root. To reproduce the floor audit, install NumPy and SciPy as optional analysis dependencies and run `python tools/audit_floor.py --samples 9 -o out/floor.json`. The interpreter and the viewer do not require these analysis libraries.

These checks establish document compatibility, sampled motion, contact behavior and rendering on the reference anatomy. They do not establish physiological activation levels, independent coaching approval, contact-force estimates, physical-device performance, or collision-free movement at every possible parameter combination.
