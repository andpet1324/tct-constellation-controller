"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Focus calibration: knife-edge scan in x at several z, replacing CalibrateFocusWorker

Unlike the old worker, acquisition and analysis are separate steps: the scan
only takes data, the fits run afterwards on the files. A failed fit therefore
never loses the data, and the analysis can be repeated with --analyse-only.
"""

import argparse
import json
import pathlib
from typing import Any

from ..analysis import focus, load_manifest
from ..controller import TCTController
from .common import add_common_arguments, bring_up, save_manifest, reconfigure, run_identifier, read_hv
from .motor_scan import SATELLITES, motor_scan

STAGE = "Standa.Stage"
HV = "Keithley.HV"
SCOPE = "LeCroySatellite.Scope"
WRITER = "H5DataWriter.Writer"
SATELLITES = [STAGE, HV, SCOPE, WRITER]


def focus_scan(
         ctrl: TCTController, 
         position: dict[float] | None, 
         triggers: float,     
         results: list[dict[str, Any]] | None = None,
         xmax: float,
         xstep: float,
         zmax: float,
         data_dir: pathlib.Path | None = None,
         csv_dir: pathlib.Path | None = None,
         channel: int = 0,
) -> list[dict[str, Any]]:
    run_id = run_identifier(position)
    collected = ctrl.take_run(run_id, triggers)

    for x in range(position[0], xmax, xstep):
        position["x"] = x
        point = {"run_id": run_id, "position": position, "triggers": collected, **read_hv(ctrl, HV)}
        results.append(point)

    # Analyze results
    results_ana = []
    for point in results:
        try:
            with Run.from_run_id(point["run_id"], data_dir) as run:
                integrals = run.integrals(channel)
        except (FileNotFoundError, KeyError) as err:
            print(f"Skipping {point['run_id']}: {err}")
            continue
        results_ana.append(
            {
                **point,
                "integral": float(integrals.mean()) if integrals.size else float("nan"),
                "integral_std": float(integrals.std()) if integrals.size else float("nan"),
                "num_waveforms": int(integrals.size),
            }
        )

    if csv_dir is not None:
        try:
            with Run.from_run_id(run_id, data_dir) as run:
                ctrl.log.status(f"Waveforms written to {run.to_csv(csv_dir, point)}")
        except Exception as err:
            ctrl.log.warning(f"Could not write {run_id} to csv: {err}")

    return results



def main(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Focus calibration: knife-edge scans in x at several z")
    add_common_arguments(parser)
    parser.add_argument("--x", type=float | None, default=None, help="Initial position in x")
    parser.add_argument("--z", type=float | None, default=None, help="Initial position in z")
    parser.add_argument("--y", type=float | None, default=None, help="Initial position in y")
    parser.add_argument('--x-max', type=float | None, default=2)
    parser.add_argument('--z-max', type=float | None, default=2)
    parser.add_argument('--x-step', type=float, default=0.1)
    parser.add_argument("--channel", type=int, default=1, help="Oscilloscope channel of the signal")
    parser.add_argument("--data-dir", type=pathlib.Path, required=True, help="output_directory of the H5DataWriter")
    parser.add_argument("--analyse-only", type=pathlib.Path, metavar="MANIFEST", help="Skip the scan, analyse this manifest")
    opts = parser.parse_args(args)

    position = None

    if opts.analyse_only:
        manifest_path = opts.analyse_only
    else:
        ctrl = TCTController(opts.group)
        if not opts.no_launch:
            bring_up(ctrl, opts.config, SATELLITES)
        if opts.channel:
            ctrl.set_channels(opts.channel)

        if not opts.x:
            response = ctrl.command("position_x")
            opts.x = response.pos_x
        if not opts.y:
            response = ctrl.command("position_y")
            opts.y = response.pos_y
        if not opts.z:
            response = ctrl.command("position_z")
            opts.z = response.pos_z

        # Move stages to initial positions.
        position = {
            "x" : opts.x,
            "y" : opts.y,
            "z" : opts.z
        }
        ctrl.log.status("Moving stages to initial positions")
        reconfigure(ctrl, STAGE, {"position": position})

        results: list[dict[str, Any]] = []

        delta_step = opts.z_max - opts.z
        current_width = 1e9 #change this
        while delta_step >= 0.01:
            focus_scan(ctrl, position, opts.trigger, results, opts.x_max, opts.x_step, opts.z_max)
            # Get width
            width = some_analyzer(results)
            if width < current_width:
                delta_step = abs(position["z"] - (position["z"] + opts.z_max/2))
                position["z"] = position["z"] + opts.z_max/2
                continue
            elif width >= current_width:
                delta_step = abs(position["z"] - (position["z"] - opts.z_max/2))
                position["z"] = position["z"] - opts.z_max/2
                continue

        # Fit widths
        

    return


if __name__ == "__main__":
    main()
