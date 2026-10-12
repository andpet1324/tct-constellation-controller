"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Position scan: one run per stage position, replacing MotorScanWorker
"""

import argparse
from typing import Any
import pathlib

from ..controller import TCTController
from .common import read_hv, reconfigure, run_identifier, data_directory
from ..prompts import readline_int, readline_dir
from ..analysis.h5 import Run
from ..menu_meta import SATELLITES

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
    stage = SATELLITES["STAGE"]
    sat_type, sat_name = stage.split(".", 1)
    for axis in position:
        response = ctrl.command(f"position_{axis}", None, sat_type, sat_name)
        if not response.success or response.payload is None:
            raise RuntimeError(f"Could not read {axis} position of {stage}: {response}")
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
        reconfigure(ctrl, stage, {"position": position})

        run_id = run_identifier("manual_scan")
        collected = ctrl.take_run(run_id, triggers)

        point = {"run_id": run_id, "position": position, "triggers": collected, **read_hv(ctrl, SATELLITES["HV"])}
        results.append(point)

        if csv_dir is not None:
            try:
                with Run.from_run_id(run_id, data_dir) as run:
                    ctrl.log.status(f"Waveforms written to {run.to_csv(csv_dir, point)}")
            except Exception as err:
                ctrl.log.warning(f"Could not write {run_id} to csv: {err}")

    ctrl.log.status(f"Ended translation at position: {position}")
    return results

def cmd_manual_translation(tgt: dict[str, any]) -> None:
    trgs = readline_int("triggers", 1000)
    csv_dir = readline_dir("data directory for csv (default is none)", None)
    data_dir = data_directory(tgt["cfg"], SATELLITES["WRITER"]) if csv_dir else None
    results = []
    try:
        manual_translation(tgt["ctrl"], trgs, results, data_dir, csv_dir)
    except Exception as err:
        print(f"Manual translation interrupted with {err}")
    finally:
        print("Manual translation ended")
        return
