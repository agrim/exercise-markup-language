"""Load the portable v1 interface, including strict JSON and symbolic registries."""

import json
import sysconfig
from functools import cache, lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

def _resource_root():
    package_root = Path(__file__).resolve().parents[1]
    marker = Path("share/exercise-markup-language/interface.json")
    for path in (package_root / "interface.json", package_root / marker):
        if path.is_file():
            return path.parent

    # A wheel may be installed into a user prefix different from the interpreter's.
    from importlib.metadata import PackageNotFoundError, files

    try:
        records = files("exercise-markup-language") or ()
    except PackageNotFoundError:
        records = ()
    for record in records:
        if record.parts[-3:] == marker.parts:
            path = Path(record.locate()).resolve()
            if path.is_file():
                return path.parent
    return Path(sysconfig.get_path("data")) / marker.parent


ROOT = _resource_root()


class Error(ValueError):
    def __init__(self, code, path, message):
        self.code, self.path, self.message = code, path, message
        super().__init__(f"{code} at {path or '/'}: {message}")

    def as_dict(self):
        return {"code": self.code, "path": self.path, "message": self.message}


def _unique(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise Error("duplicate-key", "", key)
        data[key] = value
    return data


def load(path):
    def nonfinite(token):
        raise Error("non-finite", "", token)

    try:
        return json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_unique,
            parse_constant=nonfinite,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Error("invalid-json", "", str(exc)) from exc


VERSIONS = {"1.0": "exercise-v1.schema.json", "1.1": "exercise-v1.1.schema.json"}


@lru_cache(maxsize=2)
def schema(version="1.1"):
    return load(ROOT / "schema" / VERSIONS[version])


@cache
def registry(version="1.1"):
    if version not in VERSIONS:
        raise Error("version", "/eml", "Unsupported EML version")
    directory = ROOT / ("compat/1.0/library" if version == "1.0" else "library")
    if not directory.is_dir():
        raise Error("registry", "/eml", f"Missing {version} vocabulary directory")
    poses, motions = {}, {}
    for file in sorted(directory.glob("*.json")):
        if file.name == "equipment.json":
            continue
        values = load(file)
        for group, table in (("poses", poses), ("motions", motions)):
            for key, value in values.get(group, {}).items():
                if key in table:
                    raise Error("duplicate-name", str(file), key)
                table[key] = value
    return (
        poses,
        motions,
        load(directory / "equipment.json"),
        load(ROOT / "anatomy/model.json"),
    )


@lru_cache(maxsize=2)
def validator(version="1.1"):
    return Draft202012Validator(schema(version))


def check_schema(data):
    version = data.get("eml") if isinstance(data, dict) else None
    if not isinstance(version, str) or version not in VERSIONS:
        raise Error("schema", "/eml", "Expected a supported EML version: 1.0 or 1.1")
    error = next(validator(version).iter_errors(data), None)
    if error:
        path = "/".join(
            str(p).replace("~", "~0").replace("/", "~1") for p in error.absolute_path
        )
        raise Error("schema", "/" + path, error.message)


def interface(version="1.1"):
    from .posture import PROFILE

    poses, motions, kit, model = registry(version)
    out = {
        "eml": version,
        "versions": list(VERSIONS),
        "schema": schema(version),
        "poses": poses,
        "motions": motions,
        "equipment": kit,
        "joints": [j["name"] for j in model["joints"]],
        "effectors": sorted(model["landmarks"]),
        "muscles": [
            g
            for g in model["groups"]
            if g not in ("neutral", "bone", "tendon", "shell")
        ],
    }
    if version == "1.1":
        out["compatibleSetups"] = load(ROOT / "docs/upper-motion-setups.json")
        out["postureProfile"] = {
            "id": "studio-humanoid/1.1",
            "angularBudgetsDegrees": PROFILE,
            "floorAllowanceMetres": 0.012,
            "corePenetrationAllowanceMetres": 0.005,
            "constraintKinds": ["hinge", "orientation", "support", "clearance"],
        }
    return out
