"""Author a portable EML document one phase or action at a time."""

import json
from copy import deepcopy
from typing import Self

from .data import Error, check_schema


def _array(value):
    return list(value) if isinstance(value, tuple) else value


def _options(**fields):
    return {key: _array(value) for key, value in fields.items() if value is not None}


def _names(value):
    return [value] if isinstance(value, str) else list(value)


def _point_target(target):
    return {"point": _array(target)} if isinstance(target, (list, tuple)) else target


def _collection(parent, key, default, parent_path):
    value = parent.setdefault(key, default)
    if not isinstance(value, type(default)):
        expected = "an array" if isinstance(default, list) else "an object"
        raise Error("schema", f"{parent_path}/{key}", f"Expected {expected}")
    return value


def _set_joint(parent, path, joint, angles, x, y, z):
    axes = _options(x=x, y=y, z=z)
    if (angles is None and not axes) or (angles is not None and axes):
        raise Error(
            "recipe-field", path + "/joints", "Supply a rotation triple or axis values"
        )
    joints = _collection(parent, "joints", {}, path)
    if angles is not None:
        joints[joint] = deepcopy(_array(angles))
        return
    current = joints.get(joint, {})
    if isinstance(current, list) and len(current) == 3:
        current = dict(zip("xyz", current))
    if not isinstance(current, dict):
        raise Error(
            "schema", f"{path}/joints/{joint}", "Expected a rotation triple or axes"
        )
    joints[joint] = deepcopy({**current, **axes})


def _check_json_keys(value, path=""):
    # The JSON encoder otherwise converts non-string keys, which can create duplicates.
    if isinstance(value, dict):
        for key, member in value.items():
            if not isinstance(key, str):
                raise Error("invalid-json", path, "Object keys must be strings")
            pointer = key.replace("~", "~0").replace("/", "~1")
            _check_json_keys(member, f"{path}/{pointer}")
    elif isinstance(value, list):
        for index, member in enumerate(value):
            _check_json_keys(member, f"{path}/{index}")


class Recipe:
    """A chainable authoring API for the same documents accepted by Program."""

    def __init__(self, id, title, *, version="1.1"):
        self._document = {
            "eml": version,
            "id": id,
            "title": title,
            "start": {"pose": "standing"},
            "phases": [],
            "repeat": {"mode": "once", "count": 1},
            "muscles": {"primary": [], "secondary": []},
        }

    @classmethod
    def from_document(cls, document) -> Self:
        """Start an independent chain from an existing EML document."""
        check_schema(document)
        recipe = cls(document["id"], document["title"], version=document["eml"])
        recipe._document = deepcopy(document)
        return recipe

    def instructions(self, text) -> Self:
        """Set the exercise's human-readable instructions."""
        self._document["instructions"] = text
        return self

    def schema_uri(self, uri) -> Self:
        """Set the optional JSON Schema URI for editor tooling."""
        self._document["$schema"] = uri
        return self

    def parameter(self, name, *, default, minimum, maximum) -> Self:
        """Declare or replace a named numeric parameter and its range."""
        parameters = _collection(self._document, "parameters", {}, "")
        parameters[name] = deepcopy(
            {"default": default, "min": minimum, "max": maximum}
        )
        return self

    @staticmethod
    def param(name) -> dict:
        """Create a reference to a named parameter for a numeric EML field."""
        return {"param": name}

    def start(self, pose, **fields) -> Self:
        """Set the starting pose and optional start fields such as stance."""
        self._document["start"] = deepcopy({"pose": pose, **fields})
        return self

    def stance(self, width, *, toe_out=None, factor=None) -> Self:
        """Set heel separation and toe-out, optionally scaling a named width."""
        if factor is not None:
            width = {"of": width, "factor": factor}
        self._document["start"]["stance"] = deepcopy(
            {"width": width, **_options(toeOut=toe_out)}
        )
        return self

    def start_root(self, position) -> Self:
        """Set the initial bind-relative root displacement."""
        self._document["start"]["root"] = deepcopy(_array(position))
        return self

    def start_joint(self, joint, angles=None, *, x=None, y=None, z=None) -> Self:
        """Set the setup rotation or selected axes of one joint."""
        _set_joint(self._document["start"], "/start", joint, angles, x, y, z)
        return self

    def define_pose(self, name, *, extends=None, root=None, fixed_points=None) -> Self:
        """Create or replace a local pose, optionally inheriting a base pose."""
        return self._define(
            "poses",
            name,
            _options(extends=extends, root=root, fixedPoints=fixed_points),
        )

    def define_motion(self, name, *, root=None, fixed_points=None) -> Self:
        """Create or replace a local motion with an optional root delta and pins."""
        return self._define(
            "motions", name, _options(root=root, fixedPoints=fixed_points)
        )

    def _define(self, category, name, fields):
        definitions = _collection(self._document, "definitions", {}, "")
        table = _collection(definitions, category, {}, "/definitions")
        table[name] = deepcopy(fields)
        return self

    def _definition(self, category, name):
        path = f"/definitions/{category}"
        definitions = self._document.get("definitions", {})
        if not isinstance(definitions, dict):
            raise Error("schema", "/definitions", "Expected an object")
        table = definitions.get(category, {})
        if not isinstance(table, dict):
            raise Error("schema", path, "Expected an object")
        if name not in table:
            raise Error("recipe-field", path, f"Define {name!r} before editing it")
        node = table[name]
        if not isinstance(node, dict):
            raise Error("schema", f"{path}/{name}", "Expected an object")
        return node, f"{path}/{name}"

    def pose_joint(self, name, joint, angles=None, *, x=None, y=None, z=None) -> Self:
        """Set rotation channels on a named local pose."""
        pose, path = self._definition("poses", name)
        _set_joint(pose, path, joint, angles, x, y, z)
        return self

    def motion_joint(self, name, joint, angles=None, *, x=None, y=None, z=None) -> Self:
        """Set rotation deltas on a named local motion."""
        motion, path = self._definition("motions", name)
        _set_joint(motion, path, joint, angles, x, y, z)
        return self

    def motion_action(self, name, use, amount=1) -> Self:
        """Compose a registered or local action into a named local motion."""
        motion, path = self._definition("motions", name)
        actions = _collection(motion, "actions", [], path)
        actions.append(deepcopy({"use": use, "amount": amount}))
        return self

    def equipment(
        self,
        id,
        kind,
        *,
        position=None,
        rotation=None,
        follow_joint=None,
        offset=None,
        grip=None,
    ) -> Self:
        """Add a world-positioned or joint-driven equipment instance."""
        item = {
            "id": id,
            "kind": kind,
            **_options(position=position, rotation=rotation),
        }
        if follow_joint is not None:
            item["follow"] = {
                "joint": follow_joint,
                "offset": [0, 0, 0] if offset is None else _array(offset),
                **_options(grip=grip),
            }
        elif offset is not None or grip is not None:
            raise Error(
                "recipe-field", "/equipment", "Offset and grip require a follow joint"
            )
        return self._append("equipment", item)

    def socket(self, item, socket, position) -> Self:
        """Override a registered socket on a named equipment instance."""
        instances = self._document.get("equipment", [])
        if not isinstance(instances, list):
            raise Error("schema", "/equipment", "Expected an array")
        for index, instance in enumerate(instances):
            if isinstance(instance, dict) and instance.get("id") == item:
                sockets = _collection(instance, "sockets", {}, f"/equipment/{index}")
                sockets[socket] = deepcopy(_array(position))
                return self
        raise Error(
            "unknown-item",
            "/equipment",
            f"Add equipment {item!r} before editing its sockets",
        )

    def connect(self, kind, from_item, from_socket, to_item, to_socket) -> Self:
        """Connect two equipment sockets with a rope, cable, band, or link."""
        return self._append(
            "connections",
            {
                "kind": kind,
                "from": {"item": from_item, "socket": from_socket},
                "to": {"item": to_item, "socket": to_socket},
            },
        )

    def contact(
        self,
        effector,
        target="start",
        *,
        socket=None,
        pole=None,
        rotation=None,
        engage=None,
        phase=False,
    ) -> Self:
        """Add a contact with a setup landmark, floor, world point, or item socket."""
        target = (
            {"item": target, "socket": socket}
            if socket is not None
            else _point_target(target)
        )
        contact = {
            "effector": effector,
            "target": target,
            **_options(pole=pole, rotation=rotation, engage=engage),
        }
        return self._append("contacts", contact, phase=phase)

    def clear_contacts(self, *, phase=False) -> Self:
        """Set an explicit empty contact list, releasing inherited pins for a phase."""
        scope, _ = self._scope(phase)
        scope["contacts"] = []
        return self

    def support(self, body, surface, *, phase=False) -> Self:
        """Label the bearing surface for a body part."""
        return self._append("supports", {"body": body, "surface": surface}, phase=phase)

    def clear_supports(self, *, phase=False) -> Self:
        """Set an explicit empty support list at the selected scope."""
        scope, _ = self._scope(phase)
        scope["supports"] = []
        return self

    def root_anchor(self, joint, target="start", *, phase=False) -> Self:
        """Anchor a joint at its setup position or an explicit world point."""
        scope, _ = self._scope(phase)
        scope["rootAnchor"] = deepcopy(
            {"joint": joint, "target": _point_target(target)}
        )
        return self

    def clear_root_anchor(self, *, phase=False) -> Self:
        """Remove the exercise anchor or release it within the current phase."""
        scope, _ = self._scope(phase)
        if phase:
            scope["rootAnchor"] = None
        else:
            scope.pop("rootAnchor", None)
        return self

    def camera(self, yaw, pitch) -> Self:
        """Set the viewer's initial camera angles in degrees."""
        self._document["camera"] = deepcopy([yaw, pitch])
        return self

    def side_focus(self, groups) -> Self:
        """Select the active muscle groups whose display can favor one side."""
        groups = _names(groups)
        focus = _collection(self._document, "sideFocus", {"intervals": []}, "")
        focus["groups"] = groups
        return self

    def focus_interval(self, side, start, end) -> Self:
        """Append a side focus interval on the normalized cycle timeline."""
        focus = self._document.get("sideFocus")
        if focus is None:
            raise Error(
                "recipe-field", "/sideFocus", "Select groups with .side_focus() first"
            )
        if not isinstance(focus, dict):
            raise Error("schema", "/sideFocus", "Expected an object")
        intervals = _collection(focus, "intervals", [], "/sideFocus")
        intervals.append(deepcopy({"side": side, "start": start, "end": end}))
        return self

    def _scope(self, phase):
        if not phase:
            return self._document, ""
        phases = self._document["phases"]
        if not phases:
            raise Error(
                "no-phase", "/phases", "Start a phase before editing phase settings"
            )
        return phases[-1], f"/phases/{len(phases) - 1}"

    def _append(self, field, value, *, phase=False):
        scope, path = self._scope(phase)
        _collection(scope, field, [], path).append(deepcopy(value))
        return self

    def configure(self, **fields) -> Self:
        """Set optional document fields using their EML names, such as contacts."""
        reserved = fields.keys() & {
            "eml",
            "id",
            "title",
            "start",
            "phases",
            "repeat",
            "muscles",
        }
        if reserved:
            name = min(reserved)
            raise Error(
                "recipe-field",
                f"/{name}",
                "Use the constructor or dedicated recipe method",
            )
        self._document.update(deepcopy(fields))
        return self

    def phase(self, seconds, *, id=None, **fields) -> Self:
        """Append an endpoint, with optional EML fields such as ease or contacts."""
        phases = self._document["phases"]
        if id is None:
            number = len(phases) + 1
            used_ids = [phase["id"] for phase in phases]
            while f"phase-{number}" in used_ids:
                number += 1
            id = f"phase-{number}"
        phase = {"id": id, "seconds": seconds, "actions": [], **fields}
        phases.append(deepcopy(phase))
        return self

    def action(self, use, amount=1) -> Self:
        """Compose a motion into the current phase's endpoint."""
        return self._append("actions", {"use": use, "amount": amount}, phase=True)

    def ease(self, value) -> Self:
        """Set the interpolation curve into the current phase's endpoint."""
        phase, _ = self._scope(True)
        phase["ease"] = value
        return self

    def phase_root(self, position) -> Self:
        """Set an absolute bind-relative root override on the current endpoint."""
        phase, path = self._scope(True)
        detail = _collection(phase, "detail", {}, path)
        detail["root"] = deepcopy(_array(position))
        return self

    def phase_joint(self, joint, angles=None, *, x=None, y=None, z=None) -> Self:
        """Override selected joint channels on the current endpoint."""
        phase, path = self._scope(True)
        detail = phase.get("detail", {})
        if not isinstance(detail, dict):
            raise Error("schema", path + "/detail", "Expected an object")
        _set_joint(detail, path + "/detail", joint, angles, x, y, z)
        phase["detail"] = detail
        return self

    def phase_item(
        self, item, *, position=None, rotation=None, offset=None, control_position=None
    ) -> Self:
        """Set one item's endpoint fields or its incoming path's Bézier control point."""
        phase, path = self._scope(True)
        items = _collection(phase, "items", {}, path)
        endpoint = _collection(items, item, {}, path + "/items")
        endpoint.update(
            deepcopy(
                _options(
                    position=position,
                    rotation=rotation,
                    offset=offset,
                    controlPosition=control_position,
                )
            )
        )
        return self

    def move(self, use, seconds, *, amount=1, id=None, **fields) -> Self:
        """Append a timed phase with one motion, ready for further actions."""
        if "actions" in fields:
            index = len(self._document["phases"])
            raise Error(
                "recipe-field", f"/phases/{index}/actions", "Add motions with .action()"
            )
        return self.phase(
            seconds, id=id, actions=[{"use": use, "amount": amount}], **fields
        )

    def return_to_start(self, seconds, *, id=None, **fields) -> Self:
        """Append an empty endpoint with optional timing and contact overrides."""
        for name in ("actions", "detail"):
            if name in fields:
                index = len(self._document["phases"])
                raise Error(
                    "recipe-field",
                    f"/phases/{index}/{name}",
                    "Use .phase() to specify a different endpoint",
                )
        return self.phase(seconds, id=id, **fields)

    def repeat(self, count, *, mode="loop", **fields) -> Self:
        """Set the playback mode, count and optional travel displacement."""
        if "travel" in fields:
            fields["travel"] = _array(fields["travel"])
        self._document["repeat"] = deepcopy({"mode": mode, "count": count, **fields})
        return self

    def muscles(self, primary=(), secondary=(), *, phase=False) -> Self:
        """Set each muscle role from a group name or an iterable of group names."""
        scope, _ = self._scope(phase)
        scope["muscles"] = {"primary": _names(primary), "secondary": _names(secondary)}
        return self

    def hinge_constraint(
        self, joint, axis, *, minimum, maximum, max_swing, child=None, phases=None
    ) -> Self:
        """Check twist range and off-axis swing for a solved joint or joint pair."""
        return self._constraint(
            "hinge",
            phases,
            joint=joint,
            axis=_array(axis),
            min=minimum,
            max=maximum,
            maxSwing=max_swing,
            **_options(child=child),
        )

    def orientation_constraint(
        self,
        joint,
        axis,
        direction,
        *,
        max_angle,
        relative_joint=None,
        relative_item=None,
        phases=None,
    ) -> Self:
        """Check a solved joint axis against a world, joint, or item direction."""
        if relative_joint is not None and relative_item is not None:
            raise Error(
                "recipe-field",
                "/constraints/relativeTo",
                "Choose one reference joint or item",
            )
        relative = _options(joint=relative_joint, item=relative_item)
        return self._constraint(
            "orientation",
            phases,
            joint=joint,
            axis=_array(axis),
            direction=_array(direction),
            maxAngle=max_angle,
            **_options(relativeTo=relative or None),
        )

    def clearance_constraint(
        self,
        item,
        start,
        end,
        *,
        radius,
        body_from,
        body_to,
        body_radius,
        minimum=None,
        phases=None,
    ) -> Self:
        """Check clearance between an item segment and a body segment."""
        return self._constraint(
            "clearance",
            phases,
            **{
                "item": item,
                "from": _array(start),
                "to": _array(end),
                "radius": radius,
                "bodyFrom": body_from,
                "bodyTo": body_to,
                "bodyRadius": body_radius,
                **_options(min=minimum),
            },
        )

    def support_constraint(
        self,
        landmark,
        surface="floor",
        *,
        minimum,
        maximum,
        part=None,
        offset=None,
        edge_tolerance=None,
        phases=None,
    ) -> Self:
        """Check signed distance to the floor or a finite equipment part."""
        if part is not None:
            surface = {"item": surface, "part": part}
        return self._constraint(
            "support",
            phases,
            landmark=landmark,
            surface=surface,
            min=minimum,
            max=maximum,
            **_options(offset=offset, edgeTolerance=edge_tolerance),
        )

    def _constraint(self, kind, phases, **fields):
        if phases is not None:
            fields["phases"] = _names(phases)
        return self._append("constraints", {"kind": kind, **fields})

    def build(self) -> dict:
        """Return an independent, structurally valid document with unbound parameters."""
        return json.loads(self.to_json(indent=None))

    def to_json(self, *, indent=2) -> str:
        """Serialize the structurally valid document as portable EML JSON."""
        check_schema(self._document)
        _check_json_keys(self._document)
        try:
            return json.dumps(self._document, allow_nan=False, indent=indent)
        except (TypeError, ValueError) as exc:
            raise Error("invalid-json", "", str(exc)) from exc
