"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Bias scan: one run per voltage, replacing BiasScanWorker
"""

from typing import Any
import pathlib

from ..controller import TCTController
from ..prompts import readline_int, readline_dir
from .common import read_hv, reconfigure, save_manifest, data_directory, run_identifier

from constellation.core.controller import SatelliteCommLink


def bias_scan(
    ctrl: TCTController,
    daq: SatelliteCommLink,
    hv: SatelliteCommLink,
    voltages: list[float],
    triggers: int,
    data_dir: pathlib.Path | None = None,
    csv_dir: pathlib.Path | None = None,
) -> list[dict[str, Any]]:
    """Take a run at every voltage of the range.

    The range is (start, stop, step).
    """
    ctrl.log.status(f"Setting Alibava to RADSOURCE mode")
    reconfigure(ctrl, daq, {"run_type": "RADSOURCE"})

    if not voltages:
        raise ValueError("Voltage range contains no points")

    for index, voltage in enumerate(voltages, start=1):
        ctrl.log.status(f"Voltage {index}/{len(voltages)}: {voltage}V")

        reconfigure(ctrl, hv, {"voltage": voltage})

        run_id = run_identifier("bias_scan")
        collected = ctrl.take_run(run_id, triggers)

    return

def cmd_bias_scan(tgt: dict[str, any]) -> None:
    trgs = readline_int("Triggers", 1000)
    vi = readline_int("Start voltage", 0)
    vf = readline_int("Stop voltage", 100)
    vstep = readline_int("Voltage steps", 5)
    voltages = [float(v) for v in range(vi, vf, vstep)]
    csv_dir = readline_dir("data directory for csv (default is none)", None)
    data_dir = data_directory(tgt["cfg"], tgt["Writer"]) if csv_dir else None
    try:
        bias_scan(
            tgt["ctrl"], tgt["daq"], tgt["hv"], 
            voltages, trgs, data_dir, csv_dir)
    except Exception as err:
        print(f"Bias scan interrupted with error: {err}")
    finally:
        print("Bias scan ended")
        return
