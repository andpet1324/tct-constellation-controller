"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Position scan: one run per stage position
               also includes bias scan option
"""
from typing import Any
import pathlib

from constellation.core.controller import SatelliteCommLink

from ..controller import TCTController, daq_type
from ..prompts import readline_int, readline_dir
from .h5_alibava import AlibavaRun
from ..scans.common import read_hv, reconfigure, run_identifier, data_directory, get_position, clear_h5


def pedestal_scan(
    ctrl: TCTController,
    stage: SatelliteCommLink,
    daq: SatelliteCommLink,
    hv: SatelliteCommLink,
    triggers: int,
    data_dir: pathlib.Path,
    csv_dir: pathlib.Path,
) -> None:
    """Take data in PEDESTAL mode for an amount of triggers"""
    if daq_type(daq) == "ALIBAVA":
        ctrl.log.status(f"Setting Alibava to PEDESTAL mode")
        reconfigure(ctrl, daq, {"run_type": "PEDESTAL"})

    position = get_position(ctrl, stage)

    run_id = run_identifier("pedestal_scan")
    try:
        collected = ctrl.take_run(run_id, triggers)
    except KeyboardInterrupt:
        clear_h5(pathlib.Path(data_dir) / f"data_{run_id}.h5")
        return

    point = {"run_id": run_id, "position": position, "triggers": collected, **read_hv(ctrl, hv)}

    try:
        with AlibavaRun.from_run_id(run_id, data_dir, str(daq), clear=True) as run:
            ctrl.log.status(f"Data written to {run.to_csv_pedestals(csv_dir, point)}")
    except Exception as err:
        ctrl.log.warning(f"Could not write {run_id} to csv: {err}")

def cmd_pedestal_scan(tgt: dict[str, Any]) -> None:
    trgs = readline_int("triggers", 1000)
    csv_dir = readline_dir("data directory for csv")
    if csv_dir is None:
        print("CSV directory required!")
        return
    data_dir = data_directory(tgt["cfg"], tgt["writer"])
    try:
        pedestal_scan(tgt["ctrl"], tgt["stage"], tgt["daq"], tgt["hv"], trgs, data_dir, csv_dir)
    except Exception as err:
        print(f"Pedestal scan interrupted with error: {err}")
    finally:
        print("Pedestal scan ended")
        return
