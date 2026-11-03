# EML reference dummy

The editable Blender master and indexed mesh live in this repository. The rigid equipment sockets, 51-joint rig, measured hand and foot landmarks, closed-hand poses and 28 highlightable muscle regions are the EML reference profile. The model contains 222,579 triangles. Its topology, rig and weights are shared by the browser viewer and native wrapper export.

`ExerciseDummy.blend` contains the anatomy mesh, its armature and the **historical** 108 Blender actions from the model project. The EML recipes and executable macro libraries are the source of the movements played by EML. Editing an old action in the Blender file will not update the corresponding recipe.

The source mesh assets were imported from [the anatomy-only model commit](https://github.com/agrim/3d-human-exercise-model/tree/0f4333381ceeb5cc0c11240c7761691ae26be8a8/Revision/Authoring). The artist master is 8.3 MB and can be opened directly after cloning. See the [atlas rebuild instructions](rebuild/README.md) for source registration, skinning, binary layout and the original upstream archive digests. Keep the [geometry credits and license](ATTRIBUTION.md) with distributed model copies.

The 1.1 runtime atlas marks the vertices that straddle a wrist. Metal and WebGL rotate the affected share around the measured hand pivot while preserving all other bone influences. This preserves volume under forearm roll. The XYZ coordinate frame, joint IDs, rest mesh, triangle indices and muscle groups are unchanged. The compiler separately solves and checks the posture.
