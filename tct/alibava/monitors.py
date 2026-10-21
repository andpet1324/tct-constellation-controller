import pathlib
import matplotlib.pyplot as plt
import numpy

from constellation.core.controller import SatelliteCommLink

from ..controller import TCTController
from ..scans.common import reconfigure, run_identifier
from ..prompts import readline_int


def run_pedestals(
    ctrl: TCTController,
    daq: SatelliteCommLink,
    triggers: int,
) -> None:
    """
        Take data in PEDESTAL mode for an amount of triggers
    """

    ctrl.log.status(f"Setting Alibava to PEDESTAL mode")
    reconfigure(ctrl, daq, {"run_type": "PEDESTAL"})

    count = 0
    try:
        while True:
            run_id = run_identifier("monitor_pedestal_scan" + str(count))
            ctrl.take_run(run_id, triggers)
            count += 1
    except KeyboardInterrupt:
        return

def run_adc(
    ctrl: TCTController,
    daq: SatelliteCommLink,
    triggers: int
) -> None:
    """
        Take data in RADSOURCE mode for an amount of triggers
    """

    ctrl.log.status(f"Setting Alibava to RADSOURCE mode")
    reconfigure(ctrl, daq, {"run_type": "RADSOURCE"})

    count = 0
    try:
        while True:
            run_id = run_identifier("monitor_signal_scan" + str(count))
            ctrl.take_run(run_id, triggers)
            count += 1
    except KeyboardInterrupt:
        return

def cmd_run_pedestals(tgt: dict[str, any]) -> None:
    """Continously takes data for use with monitor pedestals"""
    triggers = readline_int("Triggers", 100)
    try:
        run_pedestals(tgt["ctrl"], tgt["daq"], triggers)
    except Exception as err:
        print(f"Monitor pedestals interrupted with error: {err}")
    finally:
        print("Monitor pedestals ended")
        return

def cmd_run_adc(tgt: dict[str, any]) -> None:
    """Continously takes data for use with monitor of adc"""
    triggers = readline_int("Triggers", 100)
    try:
        run_adc(tgt["ctrl"], tgt["daq"], triggers)
    except Exception as err:
        print(f"Monitor pedestals interrupted with error: {err}")
    finally:
        print("Monitor pedestals ended")
        return