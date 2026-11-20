# EML reference human

The reference viewer, offline browser exporter and native pack use the V3 MakeHuman-derived surface in this directory. It shares EML’s 51-joint rig, measured hand and foot landmarks, grip bindings and 28 muscle groups. The exercise recipes and motion libraries drive the skeleton. The editable Blender master and its reproducible export live in the model repository. [V3 master and authoring guide](https://github.com/agrim/3d-human-exercise-model/tree/main/V3) · [Runtime geometry credits](ATTRIBUTION.md)

Each vertex has a 40-byte little-endian record. Position and normal occupy bytes 0–23, four joint indices and their normalized byte weights occupy bytes 24–31, and bytes 32–35 contain the muscle group index. Byte 36 encodes ambient visibility. Tags 1 and 2 in byte 37 identify a wrist pivot and use bytes 38–39 for the forearm and hand weights. Tag 3 uses those two bytes as an unsigned little-endian rest-space fiber coordinate divided by 16,384. Other vertices use ordinary linear skinning. Triangle indices are unsigned 32-bit values.

`ExerciseDummy.blend` and the `rebuild` directory preserve the earlier BodyParts3D/Z-Anatomy atlas and its historical actions. Its credits also apply to the archived viewer captures made with that surface. [Historical atlas sources](rebuild/README.md) · [Historical atlas credits](rebuild/ATTRIBUTION.md)
