from typing import Any
import pathlib

from constellation.core.controller import SatelliteCommLink

from ..controller import TCTController
from ..prompts import readline_int, readline_dir
from ..analysis.h5 import Run
from .common import read_hv, reconfigure, run_identifier, data_directory, get_position


def pedestal_scan(
    ctrl: TCTController,
    stage: SatelliteCommLink,
    daq: SatelliteCommLink,
    hv: SatelliteCommLink,
    triggers: int,
    results: list[dict[str, Any]] | None = [],
    data_dir: pathlib.Path | None = None,
    csv_dir: pathlib.Path | None = None,
) -> list[dict[str, Any]]:
    """Take data in PEDESTAL mode for an amount of triggers
    """

    ctrl.log.status(f"Setting Alibava to PEDESTAL mode")
    reconfigure(ctrl, daq, {"run_type": "PEDESTAL"})

    run_id = run_identifier("pedestal_scan")
    collected = ctrl.take_run(run_id, triggers)

    point = {"run_id": run_id, "position": get_position(ctrl, stage), "triggers": collected, **read_hv(ctrl, hv)}
    results.append(point)

    if csv_dir is not None:
        try:
            with Run.from_run_id(run_id, data_dir) as run:
                ctrl.log.status(f"Data written to {run.to_csv_pedestals(csv_dir, point)}")
        except Exception as err:
            ctrl.log.warning(f"Could not write {run_id} to csv: {err}")

    return results

def cmd_pedestal_scan(tgt: dict[str, any]) -> None:
    trgs = readline_int("triggers", 1000)
    csv_dir = readline_dir("data directory for csv (default is none)", None)
    data_dir = data_directory(tgt["cfg"], tgt["writer"]) if csv_dir else None
    results = []
    try:
        pedestal_scan(tgt["ctrl"], tgt["stage"], tgt["daq"], tgt["hv"], trgs, results, data_dir, csv_dir)
    except Exception as err:
        print(f"Pedestal scan interrupted with error: {err}")
    finally:
        print("Pedestal scan ended")
        return
