"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Live display of the ADC counts from Alibava per channel.

"""

import argparse
import threading
import pathlib
import numpy
from datetime import datetime
from queue import Empty
from typing import Any

import matplotlib.pyplot as plt

from constellation.core.listener import StandaloneListener
from constellation.core.monitoring import Metric
from constellation.core.protocol.cscp1 import SatelliteState

from .analysis.h5 import Run
from .menu import Menu
from .prompts import readline_int, readline_float, readline_path, readline_bool

DELAY_INTERVAL = 8

class Monitor(StandaloneListener):
    """Listener keeping a running average of the waveforms of the current run"""

    def __init__(self, name: str, group: str, daq: str) -> None:
        super().__init__(name=name, group=group, interface=None)

        self._run_id = None
        self._data_dir = None
        self._daq = daq
        self._lock = threading.Lock() # make sure we´re not reading at the same time as writing
        self._dirty = False # indicates when to update the plot
        self._pause = False

        topics = ["STAT/RUN_IDENTIFIER", "STAT/DATA_DIRECTORY", "STAT/TRIG"]
        self.set_topics(topics)

    def receive_metric(self, sender: str, metric: Metric, timestamp: datetime, value: Any) -> None:
        with self._lock:
            if metric.name.startswith("RUN_IDENTIFIER"):
                new_run_id = str(value)
                if self._data_dir is not None and new_run_id != self._run_id:
                    self._dirty = True
                self._run_id = new_run_id
            elif metric.name.startswith("DATA_DIRECTORY"):
                self._data_dir = str(value)

    def _reset(self) -> None:
        self._run_id = None
        self._dirty = True

    def reset(self) -> None:
        with self._lock:
            self._reset()

    def pause(self) -> None:
        self._pause = True
        if self._pause == True:
            self.pause()

    def resume(self) -> None:
        self._pause = False
        return

    @property
    def dirty(self) -> bool:
        return self._dirty

    def _process_tasks(self) -> None:
        """Run the queued CHIRP callbacks without blocking"""
        while True:
            try:
                callback, args = self.task_queue.get(block=False)
            except Empty:
                return
            try:
                callback(*args)
            except Exception as err:
                self.log.exception("Caught exception handling task '%s': %s", callback, repr(err))

    def finish_run(self) -> None:
        """Make sure the run has finished before opening the data file"""
        with self._lock:
            self._dirty = False

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

        lines: dict[int, dict[str, any]] = {}
        count = 0
        try:
            while plt.fignum_exists(fig.number):
                self._process_tasks()
                if self.dirty:
                    self.log.info("Recieved data")
                    with self._lock:
                        self._dirty = False
                        with Run.from_run_id(self._run_id, self._data_dir, clear=False) as run:
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
        """Take data in RADSOURCE mode for an amount of triggers
        """

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
                self._process_tasks()
                if self.dirty:
                    self.log.info("Recieved data")
                    with self._lock:
                        self._dirty = False
                        with Run.from_run_id(self._run_id, self._data_dir) as run:
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
                            fig.canvas.draw_idle()
                            fig_hits.canvas.draw_idle()
                plt.pause(interval)
                count += 1
        except KeyboardInterrupt:
            return


def cmd_monitor_pedestals(tgt: dict[str, Any]) -> None:
    """Plot pedestals and noise of the runs taken by the controller"""
    try:
        tgt["monitor"].monitor_pedestals(tgt["interval"])
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
        tgt["monitor"].monitor_adc(
            delay, pedestal_data, hit_threshold, ch_min, ch_max, tgt["interval"]
        )
    except Exception as err:
        print(f"Monitor ADC interrupted with error: {err}")
    finally:
        print("Monitor ADC ended")


MENU = {
    "PEDESTALS": ("Monitor pedestals and noise of the Alibava", cmd_monitor_pedestals),
    "ADC": ("Monitor ADC counts and hits per channel of the Alibava", cmd_monitor_adc),
}


def main(args: Any = None) -> None:
    parser = argparse.ArgumentParser(description="Live display of Alibava metrics")
    parser.add_argument("-g", "--group", default="tct", help="Constellation group name")
    parser.add_argument("-n", "--name", default="tct", help="Monitor name")
    parser.add_argument("-daq", "--daq", required=True, type=str, help="Provide the type of DAQ used. Options: Alibava, LeCroy")
    parser.add_argument("--interval", type=float, default=0.5, help="Plot refresh interval in s")
    opts = parser.parse_args(args)

    root = Menu("Monitor")
    root.load_subs(MENU)

    monitor = Monitor(opts.name, opts.group, opts.daq)
    try:
        root.steer({"monitor": monitor, "interval": opts.interval})
    finally:
        monitor.terminate()


if __name__ == "__main__":
    main()
