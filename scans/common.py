"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Helpers shared by scans
"""

import os
import pathlib
from datetime import datetime
from typing import Any

from constellation.core.controller_configuration import load_config
from constellation.core.protocol.cscp1 import SatelliteState
from constellation.core.controller import SatelliteCommLink

from ..alibava.h5_alibava import AlibavaRun
from ..lecroy.h5_lecroy import LeCroyRun
from ..data.run import Run
from ..controller import TCTController, daq_type

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


def clear_h5(path: pathlib.Path) -> None:
    if os.path.exists(path):
        os.remove(path)


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


def get_position(ctrl: TCTController, stage: SatelliteCommLink) -> dict[str, float]:
    """Position of the stage, raising if it cannot be read"""
    position = {}
    for axis, read in (("x", stage.position_x), ("y", stage.position_y), ("z", stage.position_z)):
        response = read()
        if not response.success:
            raise RuntimeError(f"Reading stage position {axis} failed: {response.errmsg}")
        try:
            position[axis] = float(response.payload)
        except (TypeError, ValueError) as err:
            raise RuntimeError(f"Stage position {axis} is not a number: {response.payload!r}") from err
    return position

_RUNS = {"ALIBAVA": AlibavaRun, "LECROY": LeCroyRun}

def open_run(run_id: str, data_dir: pathlib.Path | str, daq: SatelliteCommLink, clear: bool = False) -> Run:
    """Open the run with the reader of the DAQ"""
    canonical = str(daq)
    try:
        cls = _RUNS[daq_type(daq)]
    except KeyError:
        raise ValueError(f"No Run reader for DAQ '{canonical}'")
    return cls.from_run_id(run_id, data_dir, canonical, clear=clear)