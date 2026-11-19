# Repository guidance

Read [README.md](README.md) and [CONTRIBUTING.md](CONTRIBUTING.md) for language, catalogue, compatibility and validation requirements. For Codex Cloud installation, checks and viewer startup, read [.codex/cloud/README.md](.codex/cloud/README.md).

For programmatic authoring, consult the [Python builder reference](docs/python-api.md) and the [machine-readable interface index](interface.json). Run `python -m eml interface --version 1.1` to discover schema fields, registered symbols and compatible setups for 1.1. Use the document's `eml` version when extending an existing recipe. The [incline push-up example](examples/fluent_incline_push_up.py) shows a complete chain with equipment, contacts and posture constraints.

Blender authoring uses the explicit 5.2.1 LTS environment baseline documented in the Cloud guide; verify startup and affected assets before changing versions. Blender is optional for ordinary source and EML checks.
