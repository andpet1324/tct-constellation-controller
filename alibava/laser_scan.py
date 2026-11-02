import pathlib
from typing import Any

from constellation.core.controller import SatelliteCommLink

from .h5_alibava import AlibavaRun
from ..controller import TCTController
from ..prompts import readline_int, readline_dir, readline_bool
from ..scans.common import reconfigure, run_identifier, data_directory, get_position, read_hv, clear_h5


def laser_scan(
    ctrl: TCTController,
    daq: SatelliteCommLink,
    stage: SatelliteCommLink,
    hv: SatelliteCommLink,
    triggers: int,
    data_dir: pathlib.Path = None,
    csv_dir: pathlib.Path = None,
    results: list[dict[str, Any]] | None = [],
) -> None:
    """
        Take data in RADSOURCE mode for an amount of triggers
        The TCT laser is a RADSOURCE to Alibava. Don't get it
        confused with the LASER mode which relies on internal 
        Alibava pulsing (I think).
    """
    ctrl.log.status(f"Setting Alibava to RADSOURCE mode")
    reconfigure(ctrl, daq, {"run_type": "RADSOURCE"})

    position = get_position(ctrl, stage)

    run_id = run_identifier("laser_scan")
    try:
        collected = ctrl.take_run(run_id, triggers)
    except KeyboardInterrupt:
        if data_dir is not None:
            clear_h5(pathlib.Path(data_dir) / f"data_{run_id}.h5")
        return results

    point = {"run_id": run_id, "position": position, "triggers": collected, **read_hv(ctrl, hv)}
    results.append(point)

    if csv_dir is not None:
        try:
            with AlibavaRun.from_run_id(run_id, data_dir, str(daq), clear=True) as run:
                ctrl.log.status(f"Data written to {run.to_csv(csv_dir, point)}")
        except Exception as err:
            ctrl.log.warning(f"Could not write {run_id} to csv: {err}")

    return results

    
def cmd_laser_scan(tgt: dict[str, Any]) -> None:
    """
        Do a RADSOURCE run in one position and save the data to csv for analysis
        THIS IS ACTUALLY THE SAME AS MANUAL SCAN WITH LESS FUNCTIONALITY
    """
    if (readline_bool("Did you align the laser on the sensor?", True)):
        triggers = readline_int("Triggers per run", 10000)
        csv_dir = readline_dir("data directory for csv")
        data_dir = data_directory(tgt["cfg"], tgt["writer"])
        try:
            laser_scan(
                tgt["ctrl"], tgt["daq"], tgt["stage"], tgt["hv"], 
                triggers, data_dir, csv_dir
            )
        except Exception as err:
            print(f"Laser scan interrupted with error: {err}")
        finally:
            print("Laser scan ended")
            return
    return