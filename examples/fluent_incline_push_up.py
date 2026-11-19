"""Author the catalog incline push-up with EML's fluent API.

From the repository root, run
`python -m examples.fluent_incline_push_up OUTPUT.json`.
"""

import argparse
from pathlib import Path

from eml import Error, Program, Recipe


def recipe() -> Recipe:
    """Build an incline push-up with hands on a raised platform."""
    return (
        Recipe("incline-push-up", "Incline Push-Up")
        .instructions(
            "Place one palm on each raised pad and anchor the toes on the floor. "
            "Lower the chest between the hands, then press back to the incline plank."
        )
        .start("upper-inclined-plank")
        .start_root([0, -0.23428, -0.30244])
        .equipment("platform", "incline-hand-platforms", position=[0, 0, 0.25])
        .contact(
            "leftBall", "start", pole=[-0.33, -0.727, 0.602], rotation=[62.0, 0, 0]
        )
        .contact(
            "rightBall", "start", pole=[0.33, -0.727, 0.602], rotation=[62.0, 0, 0]
        )
        .contact(
            "leftPalm",
            "platform",
            socket="leftPalm",
            rotation=[-73.2, -10.28, 176.92],
            pole=[0.15, 0, -1],
        )
        .contact(
            "rightPalm",
            "platform",
            socket="rightPalm",
            rotation=[-73.64, 10.29, -177.0],
            pole=[-0.15, 0, -1],
        )
        .support("bothHand", "platform")
        .support("bothFoot", "floor")
        .support_constraint(
            "leftPalm",
            "platform",
            minimum=-0.005,
            maximum=0.012,
            part=0,
            offset=[-0.0114, -0.0878, 0.0549],
        )
        .support_constraint(
            "rightPalm",
            "platform",
            minimum=-0.005,
            maximum=0.012,
            part=1,
            offset=[0.0114, -0.0878, 0.0549],
        )
        .move("upper-supported-push-midrange", 0.8, id="lower-midrange")
        .ease("ease-in")
        .move("upper-supported-push", 0.8, id="lower")
        .ease("ease-out")
        .move("upper-supported-push-midrange", 0.8, id="press-midrange")
        .ease("ease-in")
        .return_to_start(0.8, id="press")
        .ease("ease-out")
        .repeat(1)
        .muscles(
            ["pectorals", "upperPectorals"],
            ["triceps", "anteriorDeltoids", "abdominals", "obliques"],
        )
        .camera(64, 17)
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Export a validated incline push-up recipe."
    )
    parser.add_argument("output", type=Path, help="Path for the EML JSON document")
    args = parser.parse_args(argv)
    try:
        authored = recipe()
        Program(authored).compile(fps=18)
        args.output.write_text(authored.to_json() + "\n", encoding="utf-8")
    except (Error, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
