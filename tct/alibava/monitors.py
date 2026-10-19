import pathlib
import matplotlib.pyplot as plt
import numpy

from constellation.core.controller import SatelliteCommLink

from ..controller import TCTController
from ..analysis.h5 import Run
from ..scans.common import reconfigure, run_identifier, data_directory

TRIGGERS = 100

def monitor_pedestals(
    ctrl: TCTController,
    daq: SatelliteCommLink,
    data_dir: pathlib.Path,
) -> None:
    """Take data in PEDESTAL mode for an amount of triggers
    """

    ctrl.log.status(f"Setting Alibava to PEDESTAL mode")
    reconfigure(ctrl, daq, {"run_type": "PEDESTAL"})

    plt.ion()
    fig, ax = plt.subplots(1,2)
    ax[0].grid(True)
    ax[1].grid(True)
    plt.show(block=False)
    plt.pause(0.1)

    fig.supxlabel("Channel")
    ax[0].set_ylabel("Pedestal [ADC]")
    ax[1].set_ylabel("Noise [ADC]")

    lines: dict[int, dict[str, any]] = {}
    palette = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    count = 0
    try:
        while plt.fignum_exists(fig.number):
            # fig.clear()
            run_id = run_identifier("monitor_pedestal_scan" + str(count))
            ctrl.take_run(run_id, TRIGGERS)

            try:
                with Run.from_run_id(run_id, data_dir) as run:
                    channels = run.channels
                    for chip in range(run.n_chips):
                        pedestals = run.pedestals(chip)
                        glob_pedestal = run.global_pedestal(chip)
                        noise = run.noise(chip)
                        x = channels + chip * len(channels)
                        color = f"C{chip}"
                        nmax = 0

                        if chip not in lines:
                            (wped,) = ax[0].plot([], [], color=color, label=f"Beetle {chip}")
                            (wnoise,) = ax[1].plot([], [], color=color, label=f"Beetle {chip}")
                            lines[chip] = {
                                "pedestals": wped,
                                "noise": wnoise,
                                "glob_pedestal": ax[0].axhline(glob_pedestal, ls="--", color=color),
                            }
                            if (pedestals.max() > nmax):
                                nmax = pedestals.max()
                                ax[0].set_ylim(pedestals.min() * 0.8, nmax * 1.2)
                            ax[1].set_ylim(noise.min(), noise.max() * 2)

                        if count%100 == 0: # re-center plot after a while
                            ax[0].set_ylim(pedestals.min() * 0.8, pedestals.max() * 1.2)
                            ax[1].set_ylim(0, noise.max() * 2)
                        for a in ax:
                            a.set_xlim(0, run.n_chips * len(channels))

                        lines[chip]["pedestals"].set_data(x, pedestals)
                        lines[chip]["noise"].set_data(x, noise)
                        lines[chip]["glob_pedestal"].set_ydata([glob_pedestal, glob_pedestal])
                        lines[chip]["glob_pedestal"].set_label(
                            f"Beetle {chip} global pedestal = {glob_pedestal:.1f}")

                    for a in ax:
                        a.legend()
                    fig.canvas.draw_idle()
                    plt.pause(0.05)
            except Exception as err:
                ctrl.log.warning(f"Could not get data from {run_id}: {err}")
            count += 1
    except KeyboardInterrupt:
        return

MAX_ON_PLOTS = 10000

def monitor_adc(
    ctrl: TCTController,
    daq: SatelliteCommLink,
    data_dir: pathlib.Path,
) -> None:
    """Take data in RADSOURCE mode for an amount of triggers
    """

    ctrl.log.status(f"Setting Alibava to RADSOURCE mode")
    reconfigure(ctrl, daq, {"run_type": "RADSOURCE"})

    plt.ion()
    fig, ax = plt.subplots(1,1)
    plt.show(block=False)
    plt.pause(0.1)

    ax.set_xlabel("Channel")
    ax.set_ylabel("ADC")

    lines: dict[int, dict[str, any]] = {}

    count = 0
    try:
        while plt.fignum_exists(fig.number):
            run_id = run_identifier("monitor_signal_scan" + str(count))
            ctrl.take_run(run_id, TRIGGERS)
            try:
                with Run.from_run_id(run_id, data_dir) as run:
                    channels = run.channels
                    for chip in range(run.n_chips):
                        adc = run.adc(chip)

                        x = channels + chip * len(channels)

                        if chip not in lines:
                            (wadc,) = ax.plot([], [], "--", color="#64B5CD")
                            lines[chip] = {
                                "adc": wadc
                            }

                        ax.set_xlim(0, run.n_chips * len(channels))
                        n_ev, n_ch = adc.shape
                        x = numpy.arange(n_ch) + chip * n_ch

                        X = numpy.full((n_ev, n_ch + 1), numpy.nan)
                        Y = numpy.full((n_ev, n_ch + 1), numpy.nan)
                        X[:, :n_ch] = x
                        Y[:, :n_ch] = adc

                        lines[chip]["adc"].set_data(X.ravel(), Y.ravel())

                    ax.relim()
                    ax.autoscale_view()
                    # ax.legend()
                    fig.canvas.draw_idle()
                    plt.pause(0.05)
            except Exception as err:
                ctrl.log.warning(f"Could not get data from {run_id}: {err}")
            count += 1
    except KeyboardInterrupt:
        return

def cmd_monitor_pedestals(tgt: dict[str, any]) -> None:
    """Takes data and updates a plot with adc and noise until interrupted"""
    data_dir = data_directory(tgt["cfg"], tgt["writer"])
    try:
        monitor_pedestals(tgt["ctrl"], tgt["daq"], data_dir)
    except Exception as err:
        print(f"Monitor pedestals interrupted with error: {err}")
    finally:
        print("Monitor pedestals ended")
        return

def cmd_monitor_adc(tgt: dict[str, any]) -> None:
    """Takes data and updates a plot with adc and noise until interrupted"""
    data_dir = data_directory(tgt["cfg"], tgt["writer"])
    try:
        monitor_adc(tgt["ctrl"], tgt["daq"], data_dir)
    except Exception as err:
        print(f"Monitor pedestals interrupted with error: {err}")
    finally:
        print("Monitor pedestals ended")
        return