import pathlib
import matplotlib.pyplot as plt
import numpy

from constellation.core.controller import SatelliteCommLink

from ..controller import TCTController
from ..analysis.h5 import Run
from ..scans.common import reconfigure, run_identifier, data_directory, clear_h5
from ..prompts import readline_int, readline_float, readline_path, readline_bool


def monitor_pedestals(
    ctrl: TCTController,
    daq: SatelliteCommLink,
    triggers: int,
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
            ctrl.take_run(run_id, triggers)

            try:
                with Run.from_run_id(run_id, data_dir, clear=True) as run:
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
        clear_h5((pathlib.Path(data_dir) / f"data_{run_id}.h5"))
        return

MAX_ON_PLOTS = 10000
DELAY_INTERVAL = 8

def monitor_adc(
    ctrl: TCTController,
    daq: SatelliteCommLink,
    triggers: int,
    data_dir: pathlib.Path,
    delay: float,
    pedestals: pathlib.Path,
    hit_threshold: float,
    ch_min: int | None,
    ch_max: int | None,
) -> None:
    """Take data in RADSOURCE mode for an amount of triggers
    """

    ctrl.log.status(f"Setting Alibava to RADSOURCE mode")
    reconfigure(ctrl, daq, {"run_type": "RADSOURCE"})

    pedestals_df = numpy.genfromtxt(pedestals, delimiter=",",
                names=True, skip_header=1, dtype=float)
    pedestals = pedestals_df["pedestals"]
    ch = pedestals_df["channel"]

    plt.ion()
    fig, ax = plt.subplots(1,1)
    fig_hits, ax_hits = plt.subplots(1,1)
    plt.show(block=False)
    plt.pause(0.1)

    ax.grid(True)
    ax.set_xlabel("Channel")
    ax.set_ylabel("ADC")

    ax_hits.grid(True)
    ax_hits.set_xlabel("Channel")
    ax_hits.set_ylabel("# Hits")

    lines: dict[int, dict[str, any]] = {}
    lines_hits: dict[int, dict[str, any]] = {}

    count = 0
    try:
        while plt.fignum_exists(fig.number):
            run_id = run_identifier("monitor_signal_scan" + str(count))
            ctrl.take_run(run_id, triggers)
            try:
                with Run.from_run_id(run_id, data_dir) as run:
                    channels = run.channels
                    for chip in range(run.n_chips):
                        ch_mask = (ch >= chip * 128) & (ch < (chip + 1) * 128)
                        chip_ch = ch[ch_mask]
                        pedestals = pedestals_df["pedestals"][ch_mask]

                        adc = run.adc(chip)
                        times = run.times()

                        time_mask = numpy.abs(times - delay) < DELAY_INTERVAL
                        if not time_mask.any():
                            count += 1
                            continue

                        if ch_min is not None and ch_max is not None:
                            ch_range = (chip_ch >= ch_min) & (chip_ch <= ch_max)
                            if not ch_range.any():
                                continue
                            chip_ch = chip_ch[ch_range]
                            pedestals = pedestals[ch_range]
                            adc = adc[:, ch_range]
                            ax.set_xlim(ch_min, ch_max)
                            ax_hits.set_xlim(ch_min, ch_max)
                        else:
                            ax.set_xlim(0, run.n_chips * len(channels))
                            ax_hits.set_xlim(0, run.n_chips * len(channels))

                        adc = adc[time_mask]
                        
                        diff = adc - pedestals
                        mask = numpy.abs(diff) > hit_threshold
                        hits = numpy.count_nonzero(mask, axis=0)

                        if chip not in lines:
                            (wadc,) = ax.plot([], [], "-", color="#64B5CD")
                            lines[chip] = {
                                "adc": wadc
                            }
                        if chip not in lines_hits:
                            hhits = ax_hits.stairs([0], [0, 1], color="#BF3535")
                            lines_hits[chip] = {
                                "hits": hhits
                            }

                        n_ev, n_ch = adc.shape
                        x = chip_ch

                        X = numpy.full((n_ev, n_ch + 1), numpy.nan)
                        Y = numpy.full((n_ev, n_ch + 1), numpy.nan)
                        X[:, :n_ch] = x
                        Y[:, :n_ch] = adc

                        lines[chip]["adc"].set_data(X.ravel(), Y.ravel())

                        # hits per channel
                        edges = numpy.append(x, x[-1] + 1) - 0.5
                        lines_hits[chip]["hits"].set_data(values=hits, edges=edges)

                        ax.set_title(f"{n_ev} events")
                        ax_hits.set_title(f"{n_ev} events, {hit_threshold} hit threshold, {delay} delay")


                    ax.relim()
                    ax.autoscale_view()
                    ax_hits.relim()
                    ax_hits.autoscale_view()
                    # ax.legend()
                    fig.canvas.draw_idle()
                    fig_hits.canvas.draw_idle()
                    plt.pause(0.1)
            except Exception as err:
                ctrl.log.warning(f"Could not get data from {run_id}: {err}")
            count += 1
    except KeyboardInterrupt:
        return

def cmd_monitor_pedestals(tgt: dict[str, any]) -> None:
    """Takes data and updates a plot with adc and noise until interrupted"""
    triggers = readline_int("Triggers", 100)
    data_dir = data_directory(tgt["cfg"], tgt["writer"])
    try:
        monitor_pedestals(tgt["ctrl"], tgt["daq"], triggers, data_dir)
    except Exception as err:
        print(f"Monitor pedestals interrupted with error: {err}")
    finally:
        print("Monitor pedestals ended")
        return

def cmd_monitor_adc(tgt: dict[str, any]) -> None:
    """Takes data and updates a plot with adc and noise until interrupted"""
    data_dir = data_directory(tgt["cfg"], tgt["writer"])
    triggers = readline_int("Triggers", 100)
    delay = readline_float("Delay in latency window", 50.0)
    hit_threshold = readline_float("Hit threshold", 50.0)
    pedestal_data = readline_path("Pedestal data file path")
    ch_min = ch_max = None
    bmask = readline_bool("Chose a channel range?", False)
    if bmask:
        ch_min = readline_int("Lower bound for channel range", 70)
        ch_max = readline_int("Upper bound for channel range", 120)
    try:
        monitor_adc(
            tgt["ctrl"], tgt["daq"], 
            triggers, data_dir, delay, 
            pedestal_data, hit_threshold, 
            ch_min=ch_min, ch_max=ch_max)
    except Exception as err:
        print(f"Monitor pedestals interrupted with error: {err}")
    finally:
        print("Monitor pedestals ended")
        return