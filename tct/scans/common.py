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
from constellation.core.controller import SatelliteCommLink

from ..controller import TCTController

def format_value(value: float) -> str:
    """Format a number for use in a run identifier.
    The minimal step-size in x,y is 0.05 um (+- 0.05 um), and 0.1 um (+- 0.03 um) in z.
    """
    return f"{value:.9f}".replace(".", "p").replace("-", "m")


def format_date(date: str) -> str:
    """Format date for data output"""
    table = str.maketrans({
        ":" : "_",
        "-" : "_",
        " " : "_",
    })
    return (date.split(".")[0]).translate(table)


def run_identifier(type: str) -> str:
    """Run identifier with the type of scan and datetime"""
    return (type + "_" + format_date(str(datetime.now())))


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Command line arguments every scan needs"""


def data_directory(config_path: pathlib.Path, writer: SatelliteCommLink) -> pathlib.Path:
    """The output_directory the H5DataWriter"""
    writer_name = str(writer)
    cfg = load_config(config_path)
    return cfg.get_satellite_configuration(writer_name).get_path("output_directory")


def reconfigure(ctrl: TCTController, satellite: SatelliteCommLink, partial_config: dict[str, Any], timeout: int = 60) -> None:
    """Reconfigure one satellite and wait until it is back in ORBIT"""
    response = satellite.reconfigure(partial_config)
    if not response.success:
        raise RuntimeError(f"Reconfiguring {satellite} failed: {response.errmsg}")
    ctrl.await_state(SatelliteState.ORBIT, timeout = timeout)


def read_hv(ctrl: TCTController, hv: SatelliteCommLink) -> dict[str, float]:
    """Voltage and current of the HV source, empty if it cannot be read"""
    response = hv.read_output()
    if not response.success or not isinstance(response.payload, dict):
        ctrl.log.warning(f"Could not read HV output: {response}")
        return {}
    return {"voltage": response.payload["voltage"], "current": response.payload["current"]}


def save_manifest(path: pathlib.Path | None, scan: str, settings: dict[str, Any], points: list[dict[str, Any]]) -> pathlib.Path:
    """Write the list of runs taken in a scan and their settings as JSON"""
    if path is None:
        path = pathlib.Path(f"{scan}_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(path, "w") as f:
        json.dump({"scan": scan, "settings": settings, "points": points}, f, indent=2)
    return path

def get_position(ctrl: TCTController, stage: SatelliteCommLink) -> dict[str, float]:
    """Position of the stage, empty if it cannot be read"""
    try:
        position = {
            "x": float(stage.position_x().payload), 
            "y": float(stage.position_y().payload), 
            "z": float(stage.position_z().payload)
        }
    except ValueError as err:
        print(f"Getting stage positions failed with {err}")
        return {}
    return position