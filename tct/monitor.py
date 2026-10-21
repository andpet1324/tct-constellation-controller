"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Live display of the ADC counts from Alibava per channel.

"""

import argparse
import threading
from datetime import datetime
from queue import Empty
from typing import Any
import pathlib

import matplotlib.pyplot as plt
import numpy

from constellation.core.listener import StandaloneListener
from constellation.core.monitoring import Metric

from .analysis.h5 import Run

DAQ = "Alibava.DAQ"
MAX_CHANNELS = 128 * 2


class Monitor(StandaloneListener):
    """Listener keeping a running average of the waveforms of the current run"""

    def __init__(self, name: str, group: str, daq: str = DAQ) -> None:
        super().__init__(name=name, group=group, interface=None)

        self.run_id = None
        self.data_dir = None
        self._daq = daq
        self._lock = threading.Lock() # make sure we´re not reading at the same time as writing
        self._dirty = False # indicates when to update the plot
        self._pause = False

        topics = ["STAT/RUN_IDENTIFIER", "STAT/DATA_DIRECTORY", "STAT/TRIG"]
        self.set_topics(topics)

    def receive_metric(self, sender: str, metric: Metric, timestamp: datetime, value: Any) -> None:
        if sender != self._daq:
            return
        with self._lock:
            print("METRIC NAME = ", metric.name)
            if metric.name.startswith("RUN_IDENTIFIER"):
                self._run_id = str(metric.name)
            elif metric.name.startswith("DATA_DIRECTORY"):
                self._data_dir = pathlib.Path(metric[1])

    def _reset(self) -> None:
        self._run_id = None
        self._data_dir = None
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

    def run_plots(self, interval: float = 0.5) -> None:
        """Show the plot or plots and keep it updated until the window is closed"""
      
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
                    with Run.from_run_id(self.run_id, self.data_dir, clear=False) as run:
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


def main(args: Any = None) -> None:
    parser = argparse.ArgumentParser(description="Live display of Alibava metrics")
    parser.add_argument("-g", "--group", default="tct", help="Constellation group name")
    parser.add_argument("-n", "--name", default="mMonitor", help="Name of this listener")
    parser.add_argument("--interval", type=float, default=0.5, help="Plot refresh interval in s")
    opts = parser.parse_args(args)

    monitor = Monitor(opts.name, opts.group)
    try:
        monitor.run_plots(opts.interval)
    except KeyboardInterrupt:
        pass
    finally:
        monitor.terminate()


if __name__ == "__main__":
    main()
