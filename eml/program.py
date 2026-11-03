"""Expand levels of detail into rig poses and evaluate a single timeline."""

import copy
import math
from bisect import bisect_left

from .data import Error, check_schema, registry
from .kinematics import Kinematics

ZERO = [0.0, 0.0, 0.0]


def mix(a, b, t):
    return [x + (y - x) * t for x, y in zip(a, b)]


def parameter_values(doc, supplied):
    declared = doc.get("parameters", {})
    unknown = supplied.keys() - declared.keys()
    if unknown:
        raise Error("unknown-parameter", "/parameters", ", ".join(sorted(unknown)))
    result = {}
    for name, rule in declared.items():
        value = supplied.get(name, rule["default"])
        if not rule["min"] <= rule["default"] <= rule["max"]:
            raise Error(
                "parameter-range", "/parameters/" + name, "Default is outside its range"
            )
        if (
            type(value) not in (float, int)
            or not math.isfinite(value)
            or not rule["min"] <= value <= rule["max"]
        ):
            raise Error(
                "parameter-range",
                "/parameters/" + name,
                "Value is outside its declared range",
            )
        result[name] = value
    return result


def substitute(value, params):
    if isinstance(value, list):
        return [substitute(x, params) for x in value]
    if isinstance(value, dict):
        if set(value) == {"param"}:
            if value["param"] not in params:
                raise Error("unknown-parameter", "/parameters", value["param"])
            return params[value["param"]]
        return {k: substitute(v, params) for k, v in value.items()}
    return value


def channels(values, names, destination, gain=None):
    # Bilateral declarations apply first; an explicit side/channel wins within a layer.
    for key in sorted(values, key=lambda k: not k.startswith("both")):
        given = values[key]
        components = dict(zip("xyz", given)) if isinstance(given, list) else given
        expanded = (
            ["left" + key[4:], "right" + key[4:]] if key.startswith("both") else [key]
        )
        for joint in expanded:
            if joint not in names:
                raise Error("unknown-joint", "/joints", key)
            vector = destination.setdefault(joint, ZERO.copy())
            for i, axis in enumerate("xyz"):
                if axis not in components:
                    continue
                sign = (
                    -1
                    if key.startswith("both") and joint.startswith("right") and i > 0
                    else 1
                )
                value = components[axis] * sign
                vector[i] = value if gain is None else vector[i] + gain * value


class Program:
    def __init__(self, recipe, parameters=None):
        check_schema(recipe)
        self.values = parameter_values(recipe, parameters or {})
        doc = self.doc = substitute(recipe, self.values)
        check_schema(doc)  # Bound parameters must also fit their receiving sockets.
        poses, motions, self.kit, self.model = registry()
        self.names = {j["name"] for j in self.model["joints"]}
        self.solver = Kinematics(self.model, self.kit)
        self.tables = []
        for key, table in (("poses", poses), ("motions", motions)):
            local = doc.get("definitions", {}).get(key, {})
            if local.keys() & table.keys():
                raise Error(
                    "reserved-name",
                    "/definitions/" + key,
                    "Cannot shadow a registered name",
                )
            self.tables.append(dict(table, **local))
        self.poses, self.motions = self.tables
        self.motion_cache = {}
        self.equipment = doc.get("equipment", [])
        self.items = {x["id"]: x for x in self.equipment}
        if len(self.items) != len(self.equipment):
            raise Error("duplicate-item", "/equipment", "Instance IDs must be unique")
        for item in self.equipment:
            kind = item["kind"]
            if kind not in self.kit:
                raise Error("unknown-equipment", "/equipment", kind)
            for socket in item.get("sockets", {}):
                self.socket(item["id"], socket)
            if "follow" in item:
                if (
                    "position" in item
                    or item["follow"]["joint"] not in self.names
                    or (
                        item["follow"].get("grip")
                        and item["follow"]["joint"] not in ("leftHand", "rightHand")
                    )
                ):
                    raise Error("invalid-driver", "/equipment", item["id"])
        for line in doc.get("connections", []):
            for end in (line["from"], line["to"]):
                self.socket(end["item"], end["socket"])
        if len({p["id"] for p in doc["phases"]}) != len(doc["phases"]):
            raise Error("duplicate-phase", "/phases", "Phase IDs must be unique")
        self.start = self.pose(doc["start"]["pose"])
        self.start[0][:] = doc["start"].get("root", self.start[0])
        channels(doc["start"].get("joints", {}), self.names, self.start[1])
        self.stance = []
        self.base = self.raw(self.start, self.equipment, [], None)
        if "stance" in doc["start"]:
            self.fit_stance(doc["start"]["stance"])
        self.anchors = dict(self.base["landmarks"])
        self.targets = [self.start]
        self.end_times, self.item_states = [], [self.equipment]
        self.duration = 0.0
        self.roles(doc["muscles"])
        for phase in doc["phases"]:
            self.roles(phase.get("muscles", doc["muscles"]))
            end = copy.deepcopy(self.start)
            for act in phase["actions"]:
                self.action(act["use"], act.get("amount", 1), end)
            detail = phase.get("detail", {})
            if "root" in detail:
                end[0][:] = detail["root"]
            channels(detail.get("joints", {}), self.names, end[1])
            self.targets.append(end)
            self.item_states.append(self.item_endpoint(phase.get("items", {})))
            self.duration += phase["seconds"]
            self.end_times.append(self.duration)
        self.focus = doc.get("sideFocus")
        if self.focus:
            groups = set(self.focus["groups"])
            active = set(doc["muscles"]["primary"] + doc["muscles"]["secondary"])
            if not groups <= active or len(groups) != len(self.focus["groups"]):
                raise Error(
                    "side-focus",
                    "/sideFocus/groups",
                    "Groups must be distinct exercise muscle roles",
                )
            last = 0
            for part in self.focus["intervals"]:
                if not last <= part["start"] < part["end"]:
                    raise Error(
                        "side-focus",
                        "/sideFocus/intervals",
                        "Overlapping or reversed intervals",
                    )
                last = part["end"]
        self.repeat = doc["repeat"]
        if self.repeat["mode"] == "once" and self.repeat["count"] != 1:
            raise Error("repeat", "/repeat/count", "A one-shot program plays once")
        if "travel" in self.repeat and self.repeat["mode"] != "loop":
            raise Error("repeat", "/repeat/travel", "Travel requires a loop")
        for container in (doc, *doc["phases"]):
            if (
                container.get("rootAnchor")
                and container["rootAnchor"]["joint"] not in self.names
            ):
                raise Error(
                    "unknown-joint",
                    "/rootAnchor/joint",
                    container["rootAnchor"]["joint"],
                )
            for support in container.get("supports", []):
                channels({support["body"]: ZERO}, self.names, {})
                if (
                    support["surface"] != "floor"
                    and support["surface"] not in self.items
                ):
                    raise Error("unknown-support", "/supports", support["surface"])
            for contact in container.get("contacts", []):
                target = contact["target"]
                if isinstance(target, dict) and "item" in target:
                    self.socket(target["item"], target["socket"])
        # Bind every declared definition, including unused local definitions.
        for name in doc.get("definitions", {}).get("poses", {}):
            self.pose(name)
        for name in doc.get("definitions", {}).get("motions", {}):
            self.action(name, 1, [ZERO.copy(), {}])
        self.entry_cache = {}
        for phase in doc["phases"]:
            effectors = [c["effector"] for c in self.effective_contacts(phase)]
            if len(set(effectors)) != len(effectors):
                raise Error(
                    "duplicate-effector",
                    "/contacts",
                    "A landmark can have only one target in a phase",
                )

    def socket(self, item_id, socket):
        item = self.items.get(item_id)
        if item is None or socket not in self.kit[item["kind"]]["sockets"]:
            raise Error("unknown-socket", "/equipment", f"{item_id}.{socket}")

    def roles(self, roles):
        known = set(self.model["groups"]) - {"neutral", "tendon", "shell", "bone"}
        p, s = set(roles["primary"]), set(roles["secondary"])
        if p & s or not p | s <= known:
            raise Error(
                "muscle-role", "/muscles", "Unknown group or conflicting muscle role"
            )

    def pose(self, name, trail=()):
        if name in trail or len(trail) >= 16:
            raise Error("cyclic-definition", "/definitions/poses", name)
        node = self.poses.get(name)
        if node is None:
            raise Error("unknown-pose", "/start/pose", name)
        result = (
            self.pose(node["extends"], trail + (name,))
            if "extends" in node
            else [ZERO.copy(), {}]
        )
        if "root" in node:
            result[0][:] = node["root"]
        channels(node.get("joints", {}), self.names, result[1])
        return result

    def action(self, name, amount, end, trail=()):
        if name in trail or len(trail) >= 16:
            raise Error("cyclic-definition", "/definitions/motions", name)
        node = self.motions.get(name)
        if node is None:
            raise Error("unknown-motion", "/phases/actions", name)
        if name not in self.motion_cache:
            expanded = [ZERO.copy(), {}]
            for child in node.get("actions", []):
                self.action(
                    child["use"], child.get("amount", 1), expanded, trail + (name,)
                )
            for i, x in enumerate(node.get("root", ZERO)):
                expanded[0][i] += x
            normalized = {}
            channels(node.get("joints", {}), self.names, normalized)
            channels(normalized, self.names, expanded[1], 1)
            self.motion_cache[name] = expanded
        vector, joints = self.motion_cache[name]
        for i, x in enumerate(vector):
            end[0][i] += amount * x
        channels(joints, self.names, end[1], amount)

    def raw(self, pose, items, contacts, anchors):
        try:
            return self.solver.sample(pose[0], pose[1], items, contacts, anchors)
        except (ValueError, KeyError) as exc:
            raise Error("invalid-constraint", "/contacts", str(exc)) from exc

    def fit_stance(self, stance):
        # Lower the pelvis only as far as needed for both legs to reach the stance.
        width = stance["width"]
        if isinstance(width, (str, dict)):
            basis = width if isinstance(width, str) else width["of"]
            factor = 1 if isinstance(width, str) else width["factor"]
            joint = "UpperArm" if basis == "shoulder-width" else "Thigh"
            bind = {j["name"]: j["position"] for j in self.model["joints"]}
            width = factor * abs(bind["left" + joint][0] - bind["right" + joint][0])
        if not 0.08 <= width <= 1.10:
            raise Error(
                "stance-range",
                "/start/stance/width",
                "Resolved width is outside the reference range",
            )
        angle = stance.get("toeOut", 0)
        if isinstance(angle, str):
            angle = {"forward": 0, "slight-out": 12, "out": 25}[angle]
        drop = 0
        for side, sign in (("left", 1), ("right", -1)):
            heel = self.base["landmarks"][side + "Heel"]
            foot = self.base["positions"][side + "Foot"]
            hip = self.base["positions"][side + "Thigh"]
            shin = self.base["positions"][side + "Shin"]
            yaw = sign * angle
            p = [self.start[0][0] + sign * width / 2, 0, heel[2]]
            self.stance.append(
                {
                    "effector": side + "Heel",
                    "target": {"point": p},
                    "rotation": [0, yaw, 0],
                }
            )
            length = math.dist(hip, shin) + math.dist(shin, foot) - 0.003
            a = math.radians(yaw)
            x = heel[0] - foot[0]
            z = heel[2] - foot[2]
            ankle = [
                p[0] - x * math.cos(a) - z * math.sin(a),
                foot[1] - heel[1],
                p[2] + x * math.sin(a) - z * math.cos(a),
            ]
            run = (ankle[0] - hip[0]) ** 2 + (ankle[2] - hip[2]) ** 2
            drop = max(drop, hip[1] - ankle[1] - math.sqrt(max(0, length**2 - run)))
        self.start[0][1] -= drop
        self.base = self.raw(self.start, self.equipment, self.stance, None)

    def item_endpoint(self, changes):
        if not changes.keys() <= self.items.keys():
            raise Error(
                "unknown-item", "/phases/items", str(changes.keys() - self.items.keys())
            )
        items = copy.deepcopy(self.equipment)
        for item in items:
            delta = changes.get(item["id"], {})
            if ("offset" in delta and "follow" not in item) or (
                bool({"position", "controlPosition"} & delta.keys())
                and "follow" in item
            ):
                raise Error("invalid-driver", "/phases/items", item["id"])
            for key, v in delta.items():
                if key == "offset":
                    item["follow"]["offset"] = v
                elif key != "controlPosition":
                    item[key] = v
        return items

    def interpolate_items(self, i, t):
        result = []
        for a, b in zip(self.item_states[i], self.item_states[i + 1]):
            item = dict(a)
            for k in ("position", "rotation"):
                if k in a or k in b:
                    item[k] = mix(a.get(k, ZERO), b.get(k, ZERO), t)
            control = (
                self.doc["phases"][i]
                .get("items", {})
                .get(a["id"], {})
                .get("controlPosition")
            )
            if control is not None:
                item["position"] = mix(
                    mix(a.get("position", ZERO), control, t),
                    mix(control, b.get("position", ZERO), t),
                    t,
                )
            if "follow" in a:
                item["follow"] = {
                    **a["follow"],
                    "offset": mix(a["follow"]["offset"], b["follow"]["offset"], t),
                }
            result.append(item)
        return result

    def effective_contacts(self, phase):
        if "contacts" in phase:
            return phase["contacts"]
        base = self.doc.get("contacts", [])
        explicit = {c["effector"] for c in base}
        return [c for c in self.stance if c["effector"] not in explicit] + base

    def sample(self, seconds, cycle=0):
        if not math.isfinite(seconds) or not 0 <= seconds <= self.duration + 1e-8:
            raise Error("time", "/time", "Time is outside the cycle")
        i = min(bisect_left(self.end_times, seconds), len(self.end_times) - 1)
        start = self.end_times[i - 1] if i else 0
        u = min(1, max(0, (seconds - start) / (self.end_times[i] - start)))
        return self.segment(i, u, cycle)

    def segment(self, i, u, cycle=0):
        phase = self.doc["phases"][i]
        ease = phase.get("ease", "smooth")
        if ease == "ease-in":
            t = 1 - math.cos(math.pi * u / 2)
        elif ease == "ease-out":
            t = math.sin(math.pi * u / 2)
        elif ease == "linear":
            t = u
        else:
            t = u * u * (3 - 2 * u)
        a, b = self.targets[i : i + 2]
        travel = self.repeat.get("travel", ZERO)
        offset = [cycle * x for x in travel]
        root = [p + d for p, d in zip(mix(a[0], b[0], t), offset)]
        joints = {
            j: mix(a[1].get(j, ZERO), b[1].get(j, ZERO), t)
            for j in a[1].keys() | b[1].keys()
        }
        items = self.interpolate_items(i, t)
        anchors = {
            k: [x + d for x, d in zip(v, offset)] for k, v in self.anchors.items()
        }
        anchor = phase.get("rootAnchor", self.doc.get("rootAnchor"))
        if anchor:
            joint = anchor["joint"]
            anchor_target = (
                [v + d for v, d in zip(self.base["positions"][joint], offset)]
                if anchor["target"] == "start"
                else anchor["target"]["point"]
            )
            current = self.raw([root, joints], items, [], anchors)["positions"][joint]
            root = [v + goal - at for v, goal, at in zip(root, anchor_target, current)]
        contacts = []
        for c in self.effective_contacts(phase):
            target = c["target"]
            if c in self.stance and cycle:
                target = {
                    "point": [x + d for x, d in zip(c["target"]["point"], offset)]
                }
            if c.get("engage") == "reach" and u < 1:
                key = (i, cycle)
                if key not in self.entry_cache:
                    self.entry_cache[key] = (
                        self.segment(i - 1, 1, cycle)["landmarks"]
                        if i
                        else self.raw(
                            [
                                root
                                if u == 0
                                else [x + d for x, d in zip(self.start[0], offset)],
                                self.start[1],
                            ],
                            self.equipment,
                            [],
                            anchors,
                        )["landmarks"]
                    )
                if target in ("start", "floor"):
                    goal = anchors[c["effector"]].copy()
                    if target == "floor":
                        goal[1] = 0
                elif "point" in target:
                    goal = target["point"]
                else:
                    goal = self.raw([root, joints], items, [], anchors)["equipment"][
                        target["item"]
                    ]["sockets"][target["socket"]]
                target = {"point": mix(self.entry_cache[key][c["effector"]], goal, t)}
            contacts.append({**c, "target": target})
        frame = self.raw([root, joints], items, contacts, anchors)
        if anchor:
            actual = frame["positions"][joint]
            residual = math.dist(actual, anchor_target)
            if residual > self.solver.tolerance:
                frame["diagnostics"].append(
                    {
                        "effector": joint,
                        "reason": "conflicting-root-anchor",
                        "target": anchor_target,
                        "achieved": actual,
                        "residual": residual,
                    }
                )
        elapsed = (self.end_times[i - 1] if i else 0) + u * phase["seconds"]
        frame.update(
            time=elapsed,
            phase=phase["id"],
            muscles=phase.get("muscles", self.doc["muscles"]),
            supports=phase.get("supports", self.doc.get("supports", [])),
        )
        if self.focus:
            p = (elapsed / self.duration) % 1
            side = next(
                (
                    x["side"]
                    for x in self.focus["intervals"]
                    if x["start"] <= p < x["end"]
                ),
                None,
            )
            frame["sideWeights"] = [int(side != "right"), int(side != "left")]
        return frame

    def frames(self, fps):
        if not 1 <= fps <= 120:
            raise Error("fps", "/fps", "Expected 1 through 120")
        n = math.ceil(self.duration * fps)
        if n + len(self.end_times) > 20000:
            raise Error(
                "frame-budget",
                "/fps",
                "Lower the frame rate or divide this program into shorter sequences",
            )
        # Include every authored transition, even when fps doesn't divide its time.
        times = sorted(
            set([self.duration * i / n for i in range(n + 1)] + self.end_times)
        )
        for t in times:
            yield self.sample(t)

    def playback(self, seconds):
        """Absolute time over the requested repetitions. At finish, keep the final pose."""
        if not math.isfinite(seconds) or seconds < 0:
            raise Error("time", "/time", "Expected nonnegative finite time")
        count = self.repeat["count"]
        if seconds >= self.duration * count:
            return self.sample(self.duration, count - 1)
        cycle = int(seconds / self.duration)
        return self.sample(seconds - self.duration * cycle, cycle)

    def compile(self, fps, strict=True):
        if strict:
            from .checks import check

            issues = check(self)["issues"]
            if issues:
                issue = issues[0]
                raise Error(issue["code"], issue["path"], issue["message"])
        out = {k: self.doc[k] for k in ("eml", "id", "title", "muscles", "repeat")}
        out.update(
            joints=[j["name"] for j in self.model["joints"]],
            duration=self.duration,
            equipment=self.equipment,
            connections=self.doc.get("connections", []),
            camera=self.doc.get("camera", [35, 12]),
            frames=list(self.frames(fps)),
        )
        if strict:
            for frame in out["frames"]:
                if frame["diagnostics"]:
                    issue = frame["diagnostics"][0]
                    raise Error(
                        issue["reason"],
                        "/contacts",
                        f"{issue['effector']} at {frame['time']:.4f} s",
                    )
        if self.focus:
            out["sideFocus"] = self.focus
        return out
