import pathlib

from constellation.core.controller import SatelliteCommLink

from ..controller import TCTController
from ..analysis.h5 import Run
from ..prompts import readline_int, readline_dir, readline_bool
from ..scans.common import reconfigure, run_identifier, data_directory, get_position, read_hv


def laser_scan(
    ctrl: TCTController,
    daq: SatelliteCommLink,
    stage: SatelliteCommLink,
    hv: SatelliteCommLink,
    triggers: int,
    results: list[dict[str, any]] | None = [],
    data_dir: pathlib.Path = None,
    csv_dir: pathlib.Path = None,
) -> None:
    """Take data in RADSOURCE mode for an amount of triggers
        The TCT laser is a RADSOURCE to Alibava. Don't get it
        confused with the LASER mode which relies on internal 
        Alibava pulsing (I think).
    """
    ctrl.log.status(f"Setting Alibava to RADSOURCE mode")
    reconfigure(ctrl, daq, {"run_type": "RADSOURCE"})

    run_id = run_identifier("laser_scan")
    collected = ctrl.take_run(run_id, triggers)

    point = {"run_id": run_id, "position": get_position(ctrl, stage), "triggers": collected, **read_hv(ctrl, hv)}
    results.append(point)

    if csv_dir is not None:
        try:
            with Run.from_run_id(run_id, data_dir) as run:
                ctrl.log.status(f"Data written to {run.to_csv_adc(csv_dir, point)}")
        except Exception as err:
            ctrl.log.warning(f"Could not write {run_id} to csv: {err}")

    return results

    
def cmd_laser_scan(tgt: dict[str, any]) -> None:
    """
    Scans along the x-axis, plotting the hit-profile and calcualting 
    the width of the gaussian across channels
    """
    if (readline_bool("Did you align the laser on the sensor?", True)):
        triggers = readline_int("Triggers per run", 10000)
        csv_dir = readline_dir("data directory for csv")
        data_dir = data_directory(tgt["cfg"], tgt["writer"])

        try:
            laser_scan(tgt["ctrl"], tgt["stage"], tgt["hv"], triggers, data_dir, csv_dir)
        except Exception as err:
            print(f"Laser scan interrupted with error: {err}")
        finally:
            print("Laser scan ended")
            return
    return