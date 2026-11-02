"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Bias scan: one run per voltage
"""

from typing import Any
import pathlib

from ..controller import TCTController, daq_type
from ..prompts import readline_int, readline_dir
from .common import reconfigure, read_hv, data_directory, run_identifier, get_position, clear_h5, open_run

from constellation.core.controller import SatelliteCommLink


def bias_scan(
    ctrl: TCTController,
    stage: SatelliteCommLink,
    daq: SatelliteCommLink,
    hv: SatelliteCommLink,
    voltages: list[float],
    triggers: int,
    data_dir: pathlib.Path,
    csv_dir: pathlib.Path,
) -> None:
    """
        Take a run at every voltage of the range.
        The range is (start, stop, step).
    """
    if daq_type(daq) == "ALIBAVA":
        ctrl.log.status(f"Setting Alibava to RADSOURCE mode")
        reconfigure(ctrl, daq, {"run_type": "RADSOURCE"})

    if not voltages:
        raise ValueError("Voltage range contains no points")

    for index, voltage in enumerate(voltages, start=1):
        ctrl.log.status(f"Voltage {index}/{len(voltages)}: {voltage}V")

        reconfigure(ctrl, hv, {"voltage": voltage})

        position = get_position(ctrl, stage)

        run_id = run_identifier("bias_scan")
        try:
            collected = ctrl.take_run(run_id, triggers)

            point = {"run_id": run_id, "position": position, "triggers": collected, **read_hv(ctrl, hv)}

            try:
                with open_run(run_id, data_dir, daq, clear=True) as run:
                    ctrl.log.status(f"Data written to {run.to_csv(csv_dir, point)}")
            except Exception as err:
                ctrl.log.warning(f"Could not write {run_id} to csv: {err}")
        except KeyboardInterrupt:
            clear_h5(pathlib.Path(data_dir) / f"data_{run_id}.h5")
            return

def cmd_bias_scan(tgt: dict[str, Any]) -> None:
    trgs = readline_int("Triggers", 1000)
    vi = readline_int("Start voltage", 0)
    vf = readline_int("Stop voltage", -100)
    vstep = readline_int("Voltage steps", 5)
    if vstep == 0:
        raise ValueError("Voltage stepsize must be non-zero")
    vstep = abs(vstep)
    vstep = vstep if vf >= vi else -vstep # Negative steps
    voltages = [float(v) for v in range(vi, vf, vstep)]
    csv_dir = readline_dir("data directory for csv")
    if csv_dir is None:
        print("CSV directory required!")
        return
    data_dir = data_directory(tgt["cfg"], tgt["writer"])
    try:
        bias_scan(
            tgt["ctrl"], tgt["stage"], tgt["daq"], tgt["hv"],
            voltages, trgs, data_dir, csv_dir)
    except Exception as err:
        print(f"Bias scan interrupted with error: {err}")
    finally:
        print("Bias scan ended")
        return
