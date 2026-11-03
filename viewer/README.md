# Inspect an EML recipe on the anatomy dummy

From the repository root, use the Python environment with the EML dependencies installed.

```sh
python -m viewer
```

Open **http://127.0.0.1:8765** in a WebGL 2 browser. The viewer serves the local atlas, compiles recipes using the reference implementation, and draws the weighted anatomy mesh. Select any catalog exercise or choose **Open a local recipe** to preview your own JSON document. The latter compiles an in-memory copy and preserves the source file. The address bar supports direct selections such as `/?id=goblet-squat`. Reload the page after adding a catalog file. Changes to a schema or shared vocabulary take effect on the next compile.

Drag to orbit, scroll or pinch to zoom, and use **Exercise view** to restore the recipe's camera. **Play** repeats one authored cycle for inspection. The slider and phase label expose each movement's timing. Coral highlights the primary muscle groups and amber highlights the secondary groups. When a recipe declares parameters, change their values and choose **Apply to model** to compare the same moment of the cycle. The Atlas credits link lists the geometry authors and license.

The viewer uses sampled skeletal and equipment transforms from `Program.compile()`. It applies the same named muscle roles and side weights included in each frame. Equipment uses the registry's local component geometry and socket positions. Cable, band, rope, and link connections are drawn as segments between the current world sockets. The viewer displays contact diagnostics from the compiler to help identify unreachable poses. Annotations for a bench or floor support are descriptive unless an explicit contact constrains a landmark.

Use `python -m viewer --fps 24` for finer sampling or `--port 9000` to choose another local port. The viewer previews at most 3,600 samples per cycle. Saved EML documents remain portable between engines; the local tool only needs the standard's reference Python dependencies. Geometry and adaptations are credited in [the atlas notice](../anatomy/ATTRIBUTION.md).

[Open the visual review sheets for all 108 catalog exercises and a parameter variation.](review/README.md)
