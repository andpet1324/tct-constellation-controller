import pathlib
import matplotlib.pyplot as plt
import numpy

from constellation.core.controller import SatelliteCommLink

from ..controller import TCTController
from ..prompts import readline_int, readline_path, readline_float
from ..analysis.h5 import Run
from ..scans.common import read_hv, reconfigure, run_identifier, data_directory, get_position

def latency_scan(
    ctrl: TCTController,
    daq: SatelliteCommLink,
    trgs: int,
    chip: int,
    lmin: int,
    lmax: int,
    threshold: float,
    pedestal_data: pathlib.Path,
    data_dir: pathlib.Path,
) -> int:
    """Take data in LASER mode for an amount of triggers
    """
    lopt = 0

    #READ ORIGINAL PARAMETERS

    # ctrl.get_config()

    ctrl.log.status(f"Setting Alibava to RADSOURCE mode")
    reconfigure(ctrl, daq, {"run_type": "RADSOURCE"})

    pedestals_df = numpy.genfromtxt(pedestal_data, delimiter=",",
                        names=True, skip_header=1, dtype=float)
    pedestals = pedestals_df["pedestals"]
    ch = pedestals_df["channel"]
    mask = (ch >= chip * 128) & (ch < (chip + 1) * 128)
    pedestals = pedestals_df["pedestals"][mask]

    for latency in range(lmin, lmax+1):
        run_id = run_identifier(f"latency_scan_{latency}")

        # Set latency to new value
        reconfigure(ctrl, daq, {f"beetle_{chip}": {"latency":latency}})

        collected = ctrl.take_run(run_id, trgs)
        entries = numpy.array([])

        try:
            with Run.from_run_id(run_id, data_dir) as run:
                adcs = numpy.asarray(run.adc(chip))
                diff = adcs - pedestals
                entries = diff[numpy.abs(diff) > threshold]
        except Exception as err:
            ctrl.log.warning(f"Could not read data from {run_id}: {err}")
            continue

        fig, ax = plt.subplots()
        ax.hist(entries, bins=100, label=f"{len(entries)} hits, {collected} triggers")
        ax.set_xlabel("Signal [ADC]")
        ax.set_ylabel("Entries")
        ax.set_title(f"Latency {latency} and threshold {threshold}")
        ax.grid(True)
        ax.legend()
        fig.savefig(data_dir / f"{run_id}_signal_hist.png", dpi=150)
        plt.close(fig)
        ctrl.log.status(f"Signal plot of latency {latency} save to {run_id}_signal_hist.png")

    # RESET PARAMETERS TO ORIGINAL

    ctrl.log.status(f"Ended latency scan with optimal latency {lopt}")
    return lopt

def cmd_latency_scan(tgt: dict[str, any]) -> None:
    """Scans through the latency parameter to locate a signal"""
    trgs = readline_int("Triggers", 1000)
    chip = readline_int("Beetle chip to scan (0,1)", 0)
    lmin = readline_int("Start scan at (min = 10)", 100)
    lmax = readline_int("Stop scan at (max = 160)", 150)
    threshold = readline_float("Threshold for a signal", 100)
    pedestal_data = readline_path("Pedestal data file path")
    if pedestal_data == None:
        print("Pedestal data required for latency scan!")
        return
    data_dir = data_directory(tgt["cfg"], tgt["writer"])
    try:
        lopt = latency_scan(tgt["ctrl"], tgt["daq"], trgs, chip, lmin, lmax, threshold, pedestal_data, data_dir)
    except Exception as err:
        print(f"Latency interrupted with error: {err}")
    finally:
        print("Latency scan ended")
        return