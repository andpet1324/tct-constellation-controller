"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Instrument calibration: scope self-calibration and homing of the stage,
replacing CalibrateInstrumentsWorker
"""

import argparse

from ..controller import TCTController
from ..menu_meta import SATELLITES
from ..prompts import readline_bool

def calibrate(ctrl: TCTController, scope: bool = True, stage: bool = True) -> None:
    """Self-calibrate the scope and home the stage, raising if either fails"""
    if scope:
        ctrl.log.status("Scope self-calibration, this takes a while...")
        sat_type, sat_name = SATELLITES["SCOPE"].split(".", 1)
        response = ctrl.command("calibrate", None, sat_type, sat_name)
        if not response.success:
            raise RuntimeError(f"Scope calibration failed: {response.errmsg}")
        if response.payload != 0:
            raise RuntimeError(f"Scope calibration returned status {response.payload}: {response.msg}")
        ctrl.log.status(response.msg)

    if stage:
        ctrl.log.status("Homing stage...")
        sat_type, sat_name = SATELLITES["STAGE"].split(".", 1)
        response = ctrl.command("home", None, sat_type, sat_name)
        if not response.success:
            raise RuntimeError(f"Homing failed: {response.errmsg}")
        ctrl.log.status(response.msg)


def cmd_calibrate(tgt: dict[str, any]) -> None:
    print("Self-calibrate the scope and home the stage")
    scope = readline_bool("Calibrate the scope?", False)
    stage = readline_bool("Calibrate the stage?", False)
    try:
        calibrate(tgt["ctrl"], scope, stage)
    except Exception as err:
        print(f"Failed calibrating with {err}")
    finally:
        return