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

### Accessible camera controls

Expand **Camera controls** for native buttons that rotate and zoom without dragging,
pinching, or a mouse wheel. They use the same pitch/zoom limits as pointer input;
the existing camera presets and Reset button are unchanged.

Run the focused, dependency-free regression checks with:

```sh
node --test viewer/camera-controls.test.mjs
```

### Local viewer resource policy

The viewer sends a Content Security Policy on successful and error responses:
modules, styles and API requests stay same-origin, the empty data favicon remains
allowed, and plugins, workers, framing, base-URL overrides and native form
navigation are blocked. A strict referrer policy prevents cross-origin URL-path
sharing, and a permissions policy disables unused camera, microphone, geolocation
and accelerometer access. Parameter updates and local-recipe previews still use
same-origin JSON requests. This is defense in depth, not authentication or a
complete audit of the local HTTP service. Do not expose this developer server to
a public interface.

Focused HTTP regression checks:

```sh
python -m unittest discover -s tests -p test_viewer_headers.py -v
```

Parameter errors appear after an edited field loses focus or a failed submit.
A shared polite live region delays blur feedback briefly so it does not compete
with the next field's focus announcement. Correcting the field, submitting native
validation, or changing recipes cancels pending feedback. Native validation still
focuses the first invalid parameter on submit. Automated tests cover state and
cancellation; actual screen-reader speech and browser combinations need separate
verification.

### Embedding and renderer lifetime

`Atlas` in `mesh.js` can render the same compiled clips in an optional host panel.
Keep the model, geometry and version-matched equipment registry together. The
renderer does not schedule animation frames; the host owns loading, playback,
visibility, reduced-motion behavior, accessible controls and its existing-media
fallback. The standalone viewer remains a developer tool, not a required server
for an embedded static clip.

Call `atlas.dispose()` when that panel unmounts, when a clip setup fails, or before
replacing its canvas. Disposal is idempotent: it removes pointer/wheel listeners,
releases captured pointers, disconnects its resize observer, and deletes owned
WebGL buffers, vertex arrays and programs. Shader objects are detached and deleted
once linking finishes. A failed constructor rolls back partially created resources
before rethrowing so the host can display its fallback. A disposed instance cannot
be reused; its drawing and camera/clip methods do nothing. Construct a new instance
for the next mount. Disposal does not force loss of a context owned by the canvas.

The host must cancel its own pending fetches and animation frames and remove its
own listeners/observers. On `webglcontextlost`, stop playback, dispose the renderer
and retain the ordinary media/text fallback; a user-initiated retry can mount a new
canvas. Do not make a lost GPU context start a workout or change exercise records.

```sh
node --test viewer/*.test.mjs
```

The lifecycle tests verify repeated mount/dispose, pointer capture loss, queued
resize callbacks after disposal, unavailable WebGL, and rollback after partial
shader, program, buffer, model, event-listener and observer failures. These mocked
resource checks complement real-browser rendering and host lifecycle verification;
they do not establish GPU memory usage or screen-reader speech.
