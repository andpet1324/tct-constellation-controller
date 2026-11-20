"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Setters of satellite parameters by reconfiguration.
"""
from typing import Any

from .scans.common import reconfigure
from .prompts import readline_float, readline_int


def set_bias(tgt: dict[str, Any]) -> None:
    voltage: float = readline_float("New voltage")
    recfg = {"voltage": voltage}
    tgt["ctrl"].log.info(f"Setting bias to {voltage}")
    # EXTRACT THE TIME-STEP BETWEEN VOLTAGES, AND SET THE TIMEOUT TO BE
    # TIMEOUT = TIMEOUT + TIME-STEP * NR_STEPS 
    try:
        reconfigure(tgt["ctrl"], tgt["hv"], recfg, timeout=360) # Setting the bias takes time
    except TimeoutError as err:
        print(f"Waiting for state ORBIT failed with {err}")
        print("Check if the current reached compliance.")
        return

    new_voltage = (tgt["hv"].read_output().payload)["voltage"]
    tgt["ctrl"].log.status(f"Voltage set to {new_voltage}")
    return


def set_laser_dac(tgt: dict[str, Any]) -> None:
    dac: int = readline_int("New DAC value")
    recfg = {"dac": dac}
    tgt["ctrl"].log.info(f"Setting laser DAC to {dac}")
    try:
        reconfigure(tgt["ctrl"], tgt["laser"], recfg, timeout=60)
    except TimeoutError as err:
        print(f"Waiting for state ORBIT failed with {err}")
        return

    tgt["ctrl"].log.status(f"Voltage set to {dac}")
    return


def set_laser_frequency(tgt: dict[str, Any]) -> None:
    frequency: float = readline_float("New frequency value")
    recfg = {"frequency": frequency}
    tgt["ctrl"].log.info(f"Setting laser frequency to {frequency}")
    try:
        reconfigure(tgt["ctrl"], tgt["laser"], recfg, timeout=60)
    except TimeoutError as err:
        print(f"Waiting for state ORBIT failed with {err}")
        return

    tgt["ctrl"].log.status(f"Voltage set to {frequency}")
    return