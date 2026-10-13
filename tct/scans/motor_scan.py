"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Position scan: one run per stage position, replacing MotorScanWorker
"""

import pathlib
from typing import Any
import numpy

from constellation.core.controller import SatelliteCommLink

from ..controller import TCTController
from ..analysis.h5 import Run
from ..prompts import readline_dir, readline_int, readline_bool, readline_float
from .common import reconfigure, read_hv, save_manifest, data_directory, run_identifier


def motor_scan(
    ctrl: TCTController,
    stage: SatelliteCommLink,
    hv: SatelliteCommLink,
    xrange: tuple[float, float, float],
    yrange: tuple[float, float, float],
    zrange: tuple[float, float, float],
    triggers: int,
    results: list[dict[str, Any]] | None = None,
    data_dir: pathlib.Path | None = None,
    csv_dir: pathlib.Path | None = None,
) -> list[dict[str, Any]]:
    """Take a run at every point of the x/y/z grid.
        We add 0.5 to every stop point to include it in the range
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

        reconfigure(ctrl, stage, {"position": position})

        run_id = run_identifier("motor_scan")
        collected = ctrl.take_run(run_id, triggers)

        point = {"run_id": run_id, "position": position, "triggers": collected, **read_hv(ctrl, hv)}
        results.append(point)

        if csv_dir is not None:
            try:
                with Run.from_run_id(run_id, data_dir) as run:
                    ctrl.log.status(f"Waveforms written to {run.to_csv(csv_dir, point)}")
            except Exception as err:
                ctrl.log.warning(f"Could not write {run_id} to csv: {err}")
    return results


def cmd_motor_scan(tgt: dict[str, any]) -> None:
    tgt["ctrl"].log.status("Starting motor scan...")

    trgs = readline_int("Triggers", 1000)

    xi = xf = tgt["stage"].position_x().payload
    yi = yf = tgt["stage"].position_y().payload
    zi = zf = tgt["stage"].position_z().payload
    xstep = ystep = zstep = 1

    scan_x = readline_bool("Scan in x?", False)
    if scan_x:
        xi = readline_float("Starting x-position", 0.0)
        xf = readline_float("Stopping x-position", 10.0)
        xstep = readline_float("Stepsize in x", 1.0)
    scan_y = readline_bool("Scan in y?", False)
    if scan_y:
        yi = readline_float("Starting y-position", 0.0)
        yf = readline_float("Stopping y-position", 10.0)
        ystep = readline_float("Stepsize in y", 1.0)
    scan_z = readline_bool("Scan in z?", False)
    if scan_z:
        zi = readline_float("Starting z-position", 0.0)
        zf = readline_float("Stopping z-position", 10.0)
        zstep = readline_float("Stepsize in z", 1.0)

    csv_dir = readline_dir("data directory for csv (default is none)", None)
    data_dir = data_directory(tgt["cfg"], tgt["Writer"]) if csv_dir else None
    settings = {
        "xrange": (xi, xf+0.5, xstep), 
        "yrange": (yi, yf+0.5, ystep), 
        "zrange": (zi, zf+0.5, zstep), 
        "triggers": trgs
    }
    results: list[dict[str, Any]] = []
    try:
       motor_scan(
            tgt["ctrl"],
            tgt["stage"],
            tgt["hv"],
            (xi, xf+0.5, xstep), 
            (yi, yf+0.5, ystep), 
            (zi, zf+0.5, zstep), 
            trgs, 
            results, 
            data_dir, 
            csv_dir
        )
    except Exception as err:
        print(f"Motor scan interrupted with error: {err}")
    finally:
        path = save_manifest(data_dir, "motor_scan", settings, results)
        tgt["ctrl"].log.status(f"Manifest of {len(results)} points written to {path}")
        print("Motor scan ended")
        return
