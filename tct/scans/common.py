"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Helpers shared by the scan scripts
"""

import argparse
import json
import pathlib
from datetime import datetime
from typing import Any

from constellation.core.controller_configuration import load_config
from constellation.core.protocol.cscp1 import SatelliteState

from ..controller import TCTController


def format_value(value: float) -> str:
    """Format a number for use in a run identifier.

    Run identifiers may only contain word characters and dashes, so the decimal
    point is replaced: 10.5 -> "10p500".
    """
    return f"{value:.3f}".replace(".", "p").replace("-", "m")


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Command line arguments every scan needs"""
    parser.add_argument("-c", "--config", type=pathlib.Path, default="tct.toml", help="Constellation configuration file")
    parser.add_argument("-g", "--group", default="tct", help="Constellation group name")
    parser.add_argument("-tr", "--triggers", type=int, default=1000, help="Triggers to collect per point")
    parser.add_argument("--manifest", type=pathlib.Path, help="Where to write the scan manifest (JSON)")
    parser.add_argument("--no-launch", action="store_true", help="Constellation is already in ORBIT, do not initialize")


def bring_up(ctrl: TCTController, config_path: pathlib.Path, satellites: list[str]) -> None:
    """Initialize and launch the constellation from a configuration file"""
    cfg = load_config(config_path)
    ctrl.await_satellites(satellites)

    ctrl.constellation.initialize(cfg)
    ctrl.await_state(SatelliteState.INIT)
    ctrl.constellation.launch()
    ctrl.await_state(SatelliteState.ORBIT)


def reconfigure(ctrl: TCTController, satellite: str, partial_config: dict[str, Any]) -> None:
    """Reconfigure one satellite and wait until it is back in ORBIT"""
    sat_type, sat_name = satellite.split(".", 1)
    response = ctrl.command("reconfigure", partial_config, sat_type, sat_name)
    if not response.success:
        raise RuntimeError(f"Reconfiguring {satellite} failed: {response.errmsg}")
    ctrl.await_state(SatelliteState.ORBIT)


def read_hv(ctrl: TCTController, satellite: str) -> dict[str, float]:
    """Voltage and current of the HV source, empty if it cannot be read"""
    sat_type, sat_name = satellite.split(".", 1)
    response = ctrl.command("read_output", None, sat_type, sat_name)
    if not response.success or not isinstance(response.payload, dict):
        ctrl.log.warning(f"Could not read HV output: {response}")
        return {}
    return {"voltage": response.payload["voltage"], "current": response.payload["current"]}


def save_manifest(path: pathlib.Path | None, scan: str, settings: dict[str, Any], points: list[dict[str, Any]]) -> pathlib.Path:
    """Write the list of runs taken in a scan and their settings as JSON.

    This is what links the run identifiers in the data directory back to the
    scan point they belong to, replacing the settings and currents entries of
    the old pickle output.
    """
    if path is None:
        path = pathlib.Path(f"{scan}_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(path, "w") as f:
        json.dump({"scan": scan, "settings": settings, "points": points}, f, indent=2)
    return path
