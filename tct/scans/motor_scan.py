"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Position scan: one run per stage position, replacing MotorScanWorker
"""

import argparse
import pathlib
from typing import Any

import numpy

from ..controller import TCTController
from .common import add_common_arguments, bring_up, read_hv, reconfigure, save_manifest, data_directory, run_identifier

STAGE = "Standa.Stage"
HV = "Keithley.HV"
SCOPE = "LeCroySatellite.Scope"
WRITER = "H5DataWriter.Writer"
SATELLITES = [STAGE, HV, SCOPE, WRITER]


def motor_scan(
    ctrl: TCTController,
    xrange: tuple[float, float, float],
    yrange: tuple[float, float, float],
    zrange: tuple[float, float, float],
    triggers: int,
    results: list[dict[str, Any]] | None = None,
    data_dir: pathlib.Path | None = None,
    csv_dir: pathlib.Path | None = None,
) -> list[dict[str, Any]]:
    """Take a run at every point of the x/y/z grid.

    Ranges are (start, stop, step) as for numpy.arange. Returns one entry per
    point with the run identifier, position, trigger count and HV reading. The
    entries are appended to `results` as they are taken, so that a caller keeps
    the points taken so far if the scan is interrupted.
    """
    if results is None:
        results = []
    points = [
        {"x": float(x), "y": float(y), "z": float(z)}
        for x in numpy.arange(*xrange)
        for y in numpy.arange(*yrange)
        for z in numpy.arange(*zrange)
    ]
    if not points:
        raise ValueError("Scan ranges contain no points")

    for index, position in enumerate(points, start=1):
        ctrl.log.status(f"Point {index}/{len(points)}: {position}")

        # The reconfigure only returns once the stage has stopped moving
        # This does not work right now!
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

    return results


def main(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Position scan, one run per point")
    add_common_arguments(parser)
    parser.add_argument("--x", type=float, nargs=3, default=(0.0, 40.1, 10.0), metavar=("START", "STOP", "STEP"))
    parser.add_argument("--y", type=float, nargs=3, default=(0.0, 40.1, 10.0), metavar=("START", "STOP", "STEP"))
    parser.add_argument("--z", type=float, nargs=3, default=(0.0, 1.0, 1.0), metavar=("START", "STOP", "STEP"))
    opts = parser.parse_args(args)

    ctrl = TCTController(opts.group)
    if not opts.no_launch:
        bring_up(ctrl, opts.config, SATELLITES)

    data_dir = data_directory(opts.config, WRITER) if opts.data else None

    settings = {"xrange": opts.x, "yrange": opts.y, "zrange": opts.z, "triggers": opts.triggers}
    results: list[dict[str, Any]] = []
    try:
        motor_scan(ctrl, tuple(opts.x), tuple(opts.y), tuple(opts.z), opts.triggers, results, data_dir, opts.data)
    finally:
        # Also on interruption: keep what was taken so far
        path = save_manifest(opts.manifest, "motor_scan", settings, results)
        ctrl.log.status(f"Manifest of {len(results)} points written to {path}")


if __name__ == "__main__":
    main()
