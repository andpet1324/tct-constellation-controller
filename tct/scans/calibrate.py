"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Instrument calibration: scope self-calibration and homing of the stage,
replacing CalibrateInstrumentsWorker
"""

from constellation.core.controller import SatelliteCommLink

from ..controller import TCTController
from ..prompts import readline_bool


def calibrate(
        ctrl: TCTController, 
        daq: SatelliteCommLink, 
        stage: SatelliteCommLink,
        run_scope: bool = True, 
        run_stage: bool = True) -> None:
    """Self-calibrate the scope and home the stage, raising if either fails. 0 Means it passed"""
    if run_scope:
        ctrl.log.status("Scope self-calibration...")
        response = daq.calibrate()
        if not response.success:
            raise RuntimeError(f"Scope calibration failed: {response.errmsg}")
        if response.payload != 0:
            print(response.payload)
            raise RuntimeError(f"Scope calibration returned status {response.payload}: {response.msg}")
        ctrl.log.status(response.msg + " (0 = passed)")

    if run_stage:
        ctrl.log.status("Homing stage...")
        response = stage.home()
        if not response.success:
            raise RuntimeError(f"Homing failed: {response.errmsg}")
        ctrl.log.status(response.msg)


def cmd_calibrate(tgt: dict[str, any]) -> None:
    print("Self-calibrate the scope and home the stage")
    scope = readline_bool("Calibrate the scope?", False)
    stage = readline_bool("Calibrate the stage?", False)
    try:
        calibrate(tgt["ctrl"], tgt["daq"], tgt["stage"], scope, stage)
    except Exception as err:
        print(f"Calibration ended with error: {err}")
    finally:
        print("Calibration ended")
        return