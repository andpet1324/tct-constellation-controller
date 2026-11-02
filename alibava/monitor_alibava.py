"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Live display of the ADC counts from Alibava per channel.

"""

import pathlib
import numpy
from typing import Any

import matplotlib.pyplot as plt

from .h5_alibava import AlibavaRun
from ..monitor_base import Monitor
from ..prompts import readline_int, readline_float, readline_path, readline_bool

DELAY_INTERVAL = 8

class AlibavaMonitor(Monitor):
    """Live plots of the pedestals, noise and ADC counts of the Alibava"""

    def __init__(self, name: str, group: str, daq: str) -> None:
        super().__init__(name, group, daq)

    def monitor_pedestals(self, interval: float = 0.5) -> None:
        """Show the plot or plots and keep it updated until the window is closed"""

        self.log.info("Starting plot monitoring...")
        plt.ion()
        fig, ax = plt.subplots(1,2)
        ax[0].grid(True)
        ax[1].grid(True)
        plt.show(block=False)
        plt.pause(0.1)

        fig.supxlabel("Channel")
        ax[0].set_ylabel("Pedestal [ADC]")
        ax[1].set_ylabel("Noise [ADC]")

        fig.canvas.mpl_connect("key_press_event", lambda event: self.reset() if event.key == "r" else None)

        lines: dict[int, dict[str, Any]] = {}
        count = 0
        try:
            while plt.fignum_exists(fig.number):
                self._process_tasks()
                if self.dirty:
                    self.log.info("Recieved data")
                    with self._lock:
                        self._dirty = False
                        with AlibavaRun.from_run_id(self._run_id, self._data_dir, self._daq, clear=False) as run:
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
                plt.pause(interval)
                count += 1
        except KeyboardInterrupt:
            return

    def monitor_adc(
        self,
        delay: float,
        pedestals: pathlib.Path,
        hit_threshold: float,
        ch_min: int | None,
        ch_max: int | None,
        interval: float = 0.5,
    ) -> None:
        """Take data in RADSOURCE mode for an amount of triggers"""

        pedestals_df = numpy.genfromtxt(pedestals, delimiter=",",
                    names=True, skip_header=1, dtype=float)
        pedestals = pedestals_df["pedestals"]
        ch = pedestals_df["channel"]

        plt.ion()
        # ADC
        fig, ax = plt.subplots(1,1)
        # HITS
        fig_hits, ax_hits = plt.subplots(1,1)
        # HITS IN TIME
        fig_time, ax_time = plt.subplots(1,1) 
        plt.show(block=False)
        plt.pause(0.1)

        ax.grid(True)
        ax.set_xlabel("Channel")
        ax.set_ylabel("ADC")

        ax_hits.grid(True)
        ax_hits.set_xlabel("Channel")
        ax_hits.set_ylabel("# Hits")

        ax_time.grid(True)
        ax_time.set_xlabel("Time [ns]")
        ax_time.set_ylabel("# Hits")

        lines: dict[int, dict[str, Any]] = {}
        lines_hits: dict[int, dict[str, Any]] = {}
        lines_time: dict[int, dict[str, Any]] = {}

        count = 0
        try:
            while plt.fignum_exists(fig.number):
                self._process_tasks()
                if self.dirty:
                    self.log.info("Recieved data")
                    with self._lock:
                        self._dirty = False
                        with AlibavaRun.from_run_id(self._run_id, self._data_dir, self._daq) as run:
                            channels = run.channels
                            for chip in range(run.n_chips):
                                ch_mask = (ch >= chip * 128) & (ch < (chip + 1) * 128)
                                chip_ch = ch[ch_mask]
                                pedestals = pedestals_df["pedestals"][ch_mask]

                                adc = run.adc(chip)
                                times = run.times()

                                diff = adc - pedestals
                                mask = numpy.abs(diff) >= hit_threshold
                                hits_time = times[numpy.nonzero(mask)[0]]

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

                                adc_tcut = adc[time_mask]
                                
                                diff = adc_tcut - pedestals
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
                                if chip not in lines_time:
                                    htime = ax_time.stairs([0], [0, 1], color="#BF3535")
                                    lines_time[chip] = {
                                        "hits": htime
                                    }

                                n_ev, n_ch = adc_tcut.shape
                                x = chip_ch

                                X = numpy.full((n_ev, n_ch + 1), numpy.nan)
                                Y = numpy.full((n_ev, n_ch + 1), numpy.nan)
                                X[:, :n_ch] = x
                                Y[:, :n_ch] = adc_tcut

                                lines[chip]["adc"].set_data(X.ravel(), Y.ravel())

                                # hits per channel
                                edges = numpy.append(x, x[-1] + 1) - 0.5
                                lines_hits[chip]["hits"].set_data(values=hits, edges=edges)

                                ax.set_title(f"{n_ev} events")
                                ax_hits.set_title(f"{n_ev} events, {hit_threshold} hit threshold, {delay} delay")

                                # hits per timestamp
                                edges = numpy.arange(0, 101) - 0.5
                                counts, _ = numpy.histogram(hits_time, bins=edges)
                                lines_time[chip]["hits"].set_data(values=counts, edges=edges)

                            ax.relim()
                            ax.autoscale_view()
                            ax_hits.relim()
                            ax_hits.autoscale_view()
                            ax_time.relim()
                            ax_time.autoscale_view()
                            fig.canvas.draw_idle()
                            fig_hits.canvas.draw_idle()
                            fig_time.canvas.draw_idle()
                plt.pause(interval)
                count += 1
        except KeyboardInterrupt:
            return


def cmd_monitor_pedestals(tgt: dict[str, Any]) -> None:
    """Plot pedestals and noise of the runs taken by the controller"""
    try:
        tgt["alibava"].monitor_pedestals(tgt["interval"])
    except Exception as err:
        print(f"Monitor pedestals interrupted with error: {err}")
    finally:
        print("Monitor pedestals ended")


def cmd_monitor_adc(tgt: dict[str, Any]) -> None:
    """Plot the ADC counts and hits per channel of the runs taken by the controller"""
    delay = readline_float("Delay in latency window", 50.0)
    hit_threshold = readline_float("Hit threshold", 50.0)
    pedestal_data = readline_path("Pedestal data file path")
    ch_min = ch_max = None
    if readline_bool("Chose a channel range?", False):
        ch_min = readline_int("Lower bound for channel range", 70)
        ch_max = readline_int("Upper bound for channel range", 120)
    try:
        tgt["alibava"].monitor_adc(
            delay, pedestal_data, hit_threshold, ch_min, ch_max, tgt["interval"]
        )
    except Exception as err:
        print(f"Monitor ADC interrupted with error: {err}")
    finally:
        print("Monitor ADC ended")


