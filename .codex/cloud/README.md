# Codex Cloud setup

Select `agrim/exercise-markup-language`. For native adapter work, also select `agrim/3d-human-exercise-model`; the language and browser viewer run independently on Linux.

## Installation

Use Python 3.11 or newer and allow the package-manager preset for PyPI and wheel downloads. No credentials or external service are required for the compiler, catalogue checks or local viewer.

Set the environment's **Install script** to run from this repository:

```sh
bash .codex/cloud/setup.sh
```

This creates/reuses the ignored `.venv` and installs `requirements.txt`. It uses the repository's declared version constraints; the project does not currently have an exact dependency lock. Use `.venv/bin/python` explicitly in task commands, since shell activation during installation is not a persistent environment setting.

## Task startup and validation

No service needs to run for language or recipe edits. In the **Start skill**, use this repository as the working directory and run the relevant existing conformance checks:

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m eml catalog --samples 17 -o out/catalog-report.json
for recipe in examples/*.json; do .venv/bin/python -m eml validate "$recipe"; done
```

These mirror [.github/workflows/conformance.yml](../../.github/workflows/conformance.yml). Follow [CONTRIBUTING.md](../../CONTRIBUTING.md) when changing recipes or language behavior. Retain version 1.0 compatibility and anatomy attribution.

For a visual task, start `.venv/bin/python -m viewer` in a terminal that remains active. Check `http://127.0.0.1:8765/api/catalog` before opening the forwarded viewer in the Cloud workspace. It serves local assets and needs no production backend. Stop an existing server before starting another. A working endpoint does not establish WebGL rendering quality; inspect the browser for that evidence.

## Optional Blender and atlas rebuilding

Use **Blender 5.2.1 LTS** as the authoring environment baseline, matching the local installation checked with `--version` and a headless Python startup on macOS. Full anatomy rebuilds and Linux execution remain separate validation steps. Select the explicit Linux release for a Cloud authoring environment rather than assuming the operating-system `blender` package has the same version.

Blender is unnecessary for normal EML tests, recipe compilation or the WebGL viewer: those use the committed anatomy buffers. The separate [atlas rebuild workflow](../../anatomy/rebuild/README.md) uses **Python 3.14** with its pinned `anatomy/rebuild/requirements.txt`, in addition to Blender. Keep its environment separate from the standard EML `.venv`. Do not install the PyPI `bpy` package as a replacement for the Blender executable.

Set the saved environment variable `BLENDER` to the executable's absolute path when it is not on `PATH` (for example, the extracted Linux release's `blender`; on this Mac the app executable is `/Applications/Blender.app/Contents/MacOS/Blender`). Check version and background startup before downloading atlases or beginning a rebuild:

```sh
"${BLENDER:-blender}" --version
"${BLENDER:-blender}" --background --factory-startup --disable-autoexec --python-exit-code 1 \
  --python-expr 'import bpy; print(bpy.app.version_string)'
```

`prepare_sources.py` already invokes Blender in background mode, disables embedded scripts, verifies archive SHA-256 digests and propagates Python failures. Run it through the separate Python 3.14 environment described in the rebuild guide. Allow its upstream atlas hosts, `dbarchive.biosciencedbc.jp` and `raw.githubusercontent.com`, only when rebuilding; allow the official Blender download host if installing the tool during Cloud setup. Keep archive caches and generated candidates outside this checkout.

When changing the Blender version, first test headless startup and a read-only load of `anatomy/ExerciseDummy.blend`, then run the affected rebuild and audit in scratch space and inspect geometry before replacing committed assets. Record the exact release/build. The master's historical actions are not the executable source of EML movements. Native Metal/iOS validation still requires the wrapper and macOS/Xcode.


These files are explicit entry points, not an automatically loaded Cloud manifest. Commit and push reviewed files before GitHub-backed setup, test the prepared environment, then publish it through the Cloud setup UI. See [the official Cloud environment guide](https://learn.chatgpt.com/docs/environments/cloud-environments).
