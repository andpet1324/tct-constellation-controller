"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Instrument calibration: scope self-calibration and homing of the stage,
replacing CalibrateInstrumentsWorker
"""

import argparse

from ..controller import TCTController
from .common import add_common_arguments, bring_up
from .motor_scan import SATELLITES, STAGE

SCOPE = "LeCroySatellite.Scope"


def calibrate(ctrl: TCTController, scope: bool = True, stage: bool = True) -> None:
    """Self-calibrate the scope and home the stage, raising if either fails"""
    if scope:
        ctrl.log.status("Scope self-calibration, this takes a while...")
        sat_type, sat_name = SCOPE.split(".", 1)
        response = ctrl.command("calibrate", None, sat_type, sat_name)
        if not response.success:
            raise RuntimeError(f"Scope calibration failed: {response.errmsg}")
        if response.payload != 0:
            raise RuntimeError(f"Scope calibration returned status {response.payload}: {response.msg}")
        ctrl.log.status(response.msg)

    if stage:
        ctrl.log.status("Homing stage...")
        sat_type, sat_name = STAGE.split(".", 1)
        response = ctrl.command("home", None, sat_type, sat_name)
        if not response.success:
            raise RuntimeError(f"Homing failed: {response.errmsg}")
        ctrl.log.status(response.msg)


def main(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Self-calibrate the scope and home the stage")
    add_common_arguments(parser)
    parser.add_argument("--no-scope", action="store_true", help="Skip the scope self-calibration")
    parser.add_argument("--no-stage", action="store_true", default=True, help="Skip homing the stage")
    opts = parser.parse_args(args)

    ctrl = TCTController(opts.group)
    if not opts.no_launch:
        bring_up(ctrl, opts.config, SATELLITES)

    calibrate(ctrl, scope=not opts.no_scope, stage=not opts.no_stage)


if __name__ == "__main__":
    main()
