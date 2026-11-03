"""Load the portable v1 interface, including strict JSON and symbolic registries."""

import json
import sysconfig
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "interface.json").is_file():
    ROOT = Path(sysconfig.get_path("data")) / "share/exercise-markup-language"


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


@lru_cache(maxsize=1)
def schema():
    return load(ROOT / "schema/exercise-v1.schema.json")


@lru_cache(maxsize=1)
def registry():
    poses, motions = {}, {}
    for file in sorted((ROOT / "library").glob("*.json")):
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
        load(ROOT / "library/equipment.json"),
        load(ROOT / "anatomy/model.json"),
    )


@lru_cache(maxsize=1)
def validator():
    return Draft202012Validator(schema())


def check_schema(data):
    error = next(validator().iter_errors(data), None)
    if error:
        path = "/".join(
            str(p).replace("~", "~0").replace("/", "~1") for p in error.absolute_path
        )
        raise Error("schema", "/" + path, error.message)


def interface():
    poses, motions, kit, model = registry()
    return {
        "eml": "1.0",
        "schema": schema(),
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
