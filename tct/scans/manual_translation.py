"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Position scan: one run per stage position, replacing MotorScanWorker
"""

import argparse
from typing import Any

import numpy

from ..controller import TCTController
from .common import add_common_arguments, bring_up, format_value, read_hv, reconfigure, save_manifest

STAGE = "Standa.Stage"
HV = "Keithley.HV"
SCOPE = "LeCroySatellite.Scope"
WRITER = "H5DataWriter.Writer"
SATELLITES = [STAGE, HV, SCOPE, WRITER]


def run_identifier(position: dict[str, float]) -> str:
    """Run identifier encoding the position, e.g. x10p000_y20p000_z0p000"""
    return "_".join(f"{axis}{format_value(mm)}" for axis, mm in position.items())


def manual_translation(
    ctrl: TCTController,
    triggers: int,
    results: dict{str, int}
) -> dict[str, Any]:
    """
      Using user input, translate the stages along the given axis.
    """
    position = {"x" : 0.0, "y" : 0.0, "z" : 0.0}

    # Get current positions
    for index, position in enumerate(positions):
        position_call = "position_" + position.key
        current_position = ctrl.command(position_call, None, Stage.type, Stage.name)
        position[position] = current_position

    # Wait for user input and then move the stages
    while True:
        #Ask for new absolute coordinates in format x,y,z
        input_position = input("New position as x,y,z in mm (empty to stop): ").strip()

        if not input_position:
            break

        try:
            values = [float(v) for v in input_position.split(",")]
            if len(values) != len(position):
                raise ValueError(f"expected {len(position)} values, got {len(values)}")
        except ValueError as err:
            ctrl.log.warning(f"Invalid position '{input_position}': {err}")
            continue
        position = dict(zip(position, values))

        ctrl.log.status(f"Moving to position {position}")
        reconfigure(ctrl, STAGE, {"position": position})

        run_id = run_identifier(position)
        collected = ctrl.take_run(run_id, triggers)

        results.append({"run_id": run_id, "position": position, "triggers": collected, **read_hv(ctrl, HV)})

    ctrl.log.status(f"Ended translation at position: {position}")
    return results


def main(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Position scan, one run per point")
    add_common_arguments(parser)
    opts = parser.parse_args(args)

    ctrl = TCTController(opts.group)
    if not opts.no_launch:
        bring_up(ctrl, opts.config, SATELLITES)

    settings = {"triggers": opts.triggers}
    results: dict[str, Any] = {}
    try:
        manual_translation(ctrl, opts.triggers, results)
    finally:
        # Also on interruption: keep what was taken so far
        path = save_manifest(opts.manifest, "manual_translation", settings, results)
        ctrl.log.status(f"Manifest of {len(results)} points written to {path}")


if __name__ == "__main__":
    main()
