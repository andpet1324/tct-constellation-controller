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
from .common import reconfigure, read_hv, data_directory, run_identifier, get_position, clear_h5


def motor_scan(
    ctrl: TCTController,
    stage: SatelliteCommLink,
    daq: SatelliteCommLink,
    hv: SatelliteCommLink,
    xrange: tuple[float, float, float],
    yrange: tuple[float, float, float],
    zrange: tuple[float, float, float],
    triggers: int,
    data_dir: pathlib.Path | None = None,
    csv_dir: pathlib.Path | None = None,
    voltages: tuple[int, int, int] | None = None
) -> None:
    """Take a run at every point of the x/y/z grid.
        We add 0.5 to every stop point to include it in the range
        range: (0 - 50 mm)
    """
        
    ctrl.log.status(f"Setting Alibava to RADSOURCE mode")
    reconfigure(ctrl, daq, {"run_type": "RADSOURCE"})

    points = [
        {"x": float(x), "y": float(y), "z": float(z)}
        for x in numpy.arange(*xrange)
        for y in numpy.arange(*yrange)
        for z in numpy.arange(*zrange)
    ]
    if not points:
        raise ValueError("Scan ranges contain no points")
    vrange = range(*voltages) if voltages is not None else [None]
    for v_index, voltage in enumerate(vrange, start=1):
        # Set HV
        if voltage is not None:
            ctrl.log.status(f"Voltage {v_index}/{len(vrange)}: {voltage}V")
            reconfigure(ctrl, hv, {"voltage": voltage}, timeout=120)

        for index, position in enumerate(points, start=1):
            # Change position
            ctrl.log.status(f"Point {index}/{len(points)}: {position}")
            reconfigure(ctrl, stage, {"position": position})

            try:
                run_id = run_identifier("motor_scan")
                collected = ctrl.take_run(run_id, triggers)

                point = {"run_id": run_id, "position": position, "triggers": collected, **read_hv(ctrl, hv)}

                if csv_dir is not None:
                    try:
                        with Run.from_run_id(run_id, data_dir, clear=True) as run:
                            ctrl.log.status(f"Data written to {run.to_csv_adc(csv_dir, point)}")
                    except Exception as err:
                        ctrl.log.warning(f"Could not write {run_id} to csv: {err}")
            except KeyboardInterrupt:
                if voltages is not None:
                    ctrl.log.status(f"Setting voltage to {voltages[0]}V")
                    reconfigure(ctrl, hv, {"voltage": voltages[0]}, timeout=120)
                clear_h5((pathlib.Path(data_dir) / f"data_{run_id}.h5"))
                return
    if voltages is not None:
        ctrl.log.status(f"Setting voltage to {voltages[0]}V")
        reconfigure(ctrl, hv, {"voltage": voltages[0]}, timeout=120)
    return


def cmd_motor_scan(tgt: dict[str, any]) -> None:
    tgt["ctrl"].log.status("Starting motor scan...")
    initial_pos = get_position(tgt["ctrl"], tgt["stage"])
    tgt["ctrl"].log.status(f"Stages currently at {initial_pos}")

    trgs = readline_int("Triggers", 1000)

    scan_hv = readline_bool("Scan voltage range", False)
    voltage = None
    if scan_hv:
        print("Before scanning make sure the leakage current is minimal at the extreme voltage!")
        vi = readline_int("Starting voltage", -100)
        vf = readline_int("Stopping voltage", -110)
        vstep = readline_int("Voltage stepsize", 1)
        if vstep == 0:
            raise ValueError("Voltage stepsize must be non-zero")
        vstep = abs(vstep)
        vstep = vstep if vf >= vi else -vstep # Negative steps
        voltage = (vi, vf + vstep, vstep) # Extra step to include last point

    xi = xf = initial_pos["x"]
    yi = yf = initial_pos["y"]
    zi = zf = initial_pos["z"]
    xstep = ystep = zstep = 1

    scan_x = readline_bool("Scan in x?", False)
    if scan_x:
        xi = readline_float("Starting x-position (min: 0.0)", initial_pos["x"])
        xf = readline_float("Stopping x-position (max: 50.0)", initial_pos["x"] + 2.0)
        xstep = readline_float("Stepsize in x", 0.01)
    else:
        xf = xf + 0.5
    scan_y = readline_bool("Scan in y?", False)
    if scan_y:
        yi = readline_float("" \
            "NOTE! Positive y points down! " \
            "\nStarting y-position (min: 0.0)", initial_pos["y"])
        yf = readline_float("Stopping y-position (max: 50.0)", initial_pos["y"] + 2.0)
        ystep = readline_float("Stepsize in y", 0.01)
    else:
        yf = yf + 0.5
    scan_z = readline_bool("Scan in z?", False)
    if scan_z:
        zi = readline_float("Starting z-position (min: 0.0)", initial_pos["z"])
        zf = readline_float("Stopping z-position (max: 50.0)", initial_pos["z"] + 2.0)
        zstep = readline_float("Stepsize in z", 0.01)
    else:
        zf = zf + 0.5

    csv_dir = readline_dir("data directory for csv (default is none)", None)
    data_dir = data_directory(tgt["cfg"], tgt["writer"]) if csv_dir else None
    try:
       motor_scan(
            tgt["ctrl"],
            tgt["stage"],
            tgt["daq"],
            tgt["hv"],
            (xi, xf, xstep), 
            (yi, yf, ystep), 
            (zi, zf, zstep), 
            trgs,
            data_dir, 
            csv_dir,
            voltage
        )
    except Exception as err:
        print(f"Motor scan interrupted with error: {err}")
    finally:
        print("Motor scan ended")
        return
