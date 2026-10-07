"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Helpers shared by the scan scripts
"""

import argparse
import json
import pathlib
import time
from datetime import datetime
from typing import Any

from constellation.core.controller_configuration import load_config
from constellation.core.protocol.cscp1 import SatelliteState

from ..controller import TCTController


def format_value(value: float) -> str:
    """Format a number for use in a run identifier.

    Precision down to nano meters. 
    The minimal step-size in x,y is 0.05 um (+- 0.05 um), and 0.1 um (+- 0.03 um) in z.
    """
    return f"{value:.9f}".replace(".", "p").replace("-", "m")


def run_identifier(position: dict[str, float]) -> str:
    """Run identifier encoding the position, e.g. x10p000000000_y20p000000000_z0p000000000"""
    return "_".join(f"{axis}{format_value(mm)}" for axis, mm in position.items())


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Command line arguments every scan needs"""
    parser.add_argument("-c", "--config", type=pathlib.Path, default="tct.toml", help="Constellation configuration file")
    parser.add_argument("-g", "--group", default="tct", help="Constellation group name")
    parser.add_argument("-tr", "--triggers", type=int, default=1000, help="Triggers to collect per point")
    parser.add_argument("--data", type=pathlib.Path, default=None, help="Directory for csv data")
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


def data_directory(config_path: pathlib.Path, writer: str = "H5DataWriter.Writer") -> pathlib.Path:
    """The output_directory the H5DataWriter.
    """
    cfg = load_config(config_path)
    return cfg.get_satellite_configuration(writer).get_path("output_directory")


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
