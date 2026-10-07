"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Position scan: one run per stage position, replacing MotorScanWorker
"""

import argparse
from typing import Any
import pathlib

from ..controller import TCTController
from .common import add_common_arguments, bring_up, format_value, read_hv, reconfigure, save_manifest, data_directory
from ..analysis.h5 import Run

STAGE = "Standa.Stage"
HV = "Keithley.HV"
DAQ = "Alibava.DAQ"
WRITER = "H5DataWriter.Writer"
SATELLITES = [STAGE, HV, DAQ, WRITER]


def run_identifier(position: dict[str, float]) -> str:
    return "_".join(f"{axis}{format_value(mm)}" for axis, mm in position.items())


def manual_translation(
    ctrl: TCTController,
    triggers: int,
    results: list[dict[str, Any]] | None = None,
    data_dir: pathlib.Path | None = None,
    csv_dir: pathlib.Path | None = None,
) -> list[dict[str, Any]]:
    """Move the stage to positions entered by the user and take a run at each.
    """
    if results is None:
        results = []
    position = {"x": 0.0, "y": 0.0, "z": 0.0}

    # Get current positions
    sat_type, sat_name = STAGE.split(".", 1)
    for axis in position:
        response = ctrl.command(f"position_{axis}", None, sat_type, sat_name)
        if not response.success or response.payload is None:
            raise RuntimeError(f"Could not read {axis} position of {STAGE}: {response}")
        position[axis] = float(response.payload)
    ctrl.log.status(f"Stage currently at {position}")

    # Wait for user input and then move the stages
    while True:
        # Ask for new absolute coordinates in format x,y,z
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

        point = {"run_id": run_id, "position": position, "triggers": collected, **read_hv(ctrl, HV)}
        results.append(point)

        if csv_dir is not None:
            try:
                with Run.from_run_id(run_id, data_dir) as run:
                    ctrl.log.status(f"Waveforms written to {run.to_csv(csv_dir, point)}")
            except Exception as err:
                ctrl.log.warning(f"Could not write {run_id} to csv: {err}")

    ctrl.log.status(f"Ended translation at position: {position}")
    return results


def main(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Manual translation, one run per position entered by the user")
    add_common_arguments(parser)
    opts = parser.parse_args(args)

    ctrl = TCTController(opts.group)
    if not opts.no_launch:
        bring_up(ctrl, opts.config, SATELLITES)

    data_dir = data_directory(opts.config, WRITER) if opts.data else None

    settings = {"triggers": opts.triggers}
    results: list[dict[str, Any]] = []
    try:
        manual_translation(ctrl, opts.triggers, results, data_dir, opts.data)
    finally:
        path = save_manifest(opts.manifest, "manual_translation", settings, results)
        ctrl.log.status(f"Manifest of {len(results)} points written to {path}")


if __name__ == "__main__":
    main()
