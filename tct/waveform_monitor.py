"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Live display of the averaged oscilloscope waveforms

The LeCroy satellite publishes its most recent trace per channel as the
WAVEFORM_C<n> metrics. TelemetryConsole can only draw scalar metrics against
wall-clock time, so this listener averages the traces of the current run and
plots them against the sample time from the trigger.
"""

import argparse
import threading
from datetime import datetime
from queue import Empty
from typing import Any

import matplotlib.pyplot as plt
import numpy

from constellation.core.listener import StandaloneListener
from constellation.core.monitoring import Metric

# from .analysis.waveform import get_pedestal, get_maximum, get_tot
from .analysis.waveform import get_pedestal, get_maximum


SCOPE = "LeCroySatellite.Scope"
MAX_CHANNELS = 4
WAVEFORM_METRIC = "WAVEFORM_C"


class WaveformMonitor(StandaloneListener):
    """Listener keeping a running average of the waveforms of the current run"""

    def __init__(self, name: str, group: str, scope: str = SCOPE) -> None:
        super().__init__(name=name, group=group, interface=None)

        self._scope = scope
        self._lock = threading.Lock() # make sure we´re not reading at the same time as writing
        self._sums: dict[int, numpy.ndarray] = {}
        self._counts: dict[int, int] = {}
        self._sampling_period: float | None = None
        self._sample_offset: float = 0.0
        self._num_triggers = 0
        self._dirty = False # indicates when to update the plot
        self._pause = False

        topics = [f"STAT/{WAVEFORM_METRIC}{channel}" for channel in range(1, MAX_CHANNELS + 1)]
        topics += ["STAT/SAMPLING_PERIOD", "STAT/SAMPLE_OFFSET", "STAT/NUM_TRIGGERS"]
        self.set_topics(topics)

    def receive_metric(self, sender: str, metric: Metric, timestamp: datetime, value: Any) -> None:
        if sender != self._scope:
            return
        with self._lock:
            print("METRIC NAME = ", metric.name)
            if metric.name.startswith(WAVEFORM_METRIC):
                channel = int(metric.name[len(WAVEFORM_METRIC) :])
                self._add_waveform(channel, numpy.asarray(value, dtype=float))
            elif metric.name == "SAMPLING_PERIOD":
                self._sampling_period = float(value)
                print("SAMPLING_PERIOD = ", float(value))
            elif metric.name == "SAMPLE_OFFSET":
                self._sample_offset = float(value)
                print("SAMPLE OFFSET = ", float(value))
            elif metric.name == "NUM_TRIGGERS":
                # The counter starts from zero again in a new run
                # Is this a good way to do this? Subscribe to run metric instead?
                # Does something else run before this s.t. we're saving data from last run?
                if int(value) < self._num_triggers:
                    self._reset()
                self._num_triggers = int(value)

    def _add_waveform(self, channel: int, waveform: numpy.ndarray) -> None:
        total = self._sums.get(channel)
        if total is None or total.shape != waveform.shape:
            # First trace, or the scope was reconfigured to another record length
            self._sums[channel] = waveform.copy()
            self._counts[channel] = 1
        else:
            total += waveform
            self._counts[channel] += 1
        self._dirty = True

    def _reset(self) -> None:
        self._sums.clear()
        self._counts.clear()
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

    def averages(self) -> tuple[numpy.ndarray | None, dict[int, numpy.ndarray], dict[int, int]]:
        """Time axis in s and averaged waveform in V per channel, or None if nothing arrived yet"""
        with self._lock:
            self._dirty = False
            # average waveform per channel:
            averages = {channel: total / self._counts[channel] for channel, total in self._sums.items()}
            counts = dict(self._counts)
            if not averages or self._sampling_period is None:
                return None, averages, counts
            num_samples = max(len(avg) for avg in averages.values())
            # Times should not change. I will assume it is constant
            times = self._sample_offset + self._sampling_period * numpy.arange(num_samples)
            return times, averages, counts

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

    def run_plot(self, interval: float = 0.5) -> None:
        """Show the plot and keep it updated until the window is closed"""
        fig, ax = plt.subplots()
        ax.set_xlabel("Time from reference [s]")
        ax.set_ylabel("Amplitude [V]")
        ax.grid(True)
        lines: dict[int, dict[str, Any]] = {}
        fig.canvas.mpl_connect("key_press_event", lambda event: self.reset() if event.key == "r" else None)
        fig.canvas.mpl_connect("key_press_event", 
                               lambda event: self.pause() if (event.key == 'p' and self._pause == False) else 
                               lambda event: self.resume() if (event.key == 'p' and self._pause == True) else 
                               None)

        palette = plt.rcParams["axes.prop_cycle"].by_key()["color"]

        while plt.fignum_exists(fig.number):
            self._process_tasks()
            if self.dirty:
                times, averages, counts = self.averages()
                # Wait for first sample metric
                if times is None or not times.any():
                    continue
                for channel, average in averages.items():
                    # pedestal, maximum, (tot, threshold) = get_pedestal(average), get_maximum(average), get_tot(average, times)
                    pedestal, maximum = get_pedestal(average), get_maximum(average)[0]
                    if channel not in lines:
                        color = palette[channel % len(palette)]
                        (wave,) = ax.plot([], [], color=color, label=f"C{channel}")
                        lines[channel] = {
                            "wave":     wave,
                            "pedestal": ax.axhline(pedestal, ls="--", label=f"Ch {channel} pedestal = {pedestal:.3g}", color=color),
                            "maximum":  ax.axhline(maximum, ls="-.", label=f"Ch {channel} Maximum = {maximum:.3g}", color=color),
                        }
                        #(lines[channel],) = ax.axvline(threshold, label=f"tot_threshold = {threshold}. tot = {tot}", ls='--')
                    #x = times[: len(average)] if times is not None else numpy.arange(len(average))
                    x = times[: len(average)]
                    lines[channel]["wave"].set_data(x, average)
                    lines[channel]["pedestal"].set_ydata([pedestal, pedestal])
                    lines[channel]["pedestal"].set_label(f"Ch {channel} pedestal = {pedestal:.3g}")
                    lines[channel]["maximum"].set_ydata([maximum, maximum])
                    lines[channel]["maximum"].set_label(f"Ch {channel} Maximum = {maximum:.3g}")
                # if times is None and averages:
                #     ax.set_xlabel("Sample")
                ax.legend()
                ax.relim()
                ax.autoscale_view()
                num = ", ".join(f"C{channel}: {count}" for channel, count in sorted(counts.items()))
                ax.set_title(f"{self._scope} averaged waveforms ({num or 'waiting for data'}), 'r' to reset, 'p' to pause/resume")
                fig.canvas.draw_idle()
            plt.pause(interval)


def main(args: Any = None) -> None:
    parser = argparse.ArgumentParser(description="Live display of the averaged oscilloscope waveforms")
    parser.add_argument("-g", "--group", default="tct", help="Constellation group name")
    parser.add_argument("-n", "--name", default="WaveformMonitor", help="Name of this listener")
    parser.add_argument("--scope", default=SCOPE, help="Canonical name of the oscilloscope satellite")
    parser.add_argument("--interval", type=float, default=0.5, help="Plot refresh interval in s")
    opts = parser.parse_args(args)

    monitor = WaveformMonitor(opts.name, opts.group, opts.scope)
    try:
        monitor.run_plot(opts.interval)
    except KeyboardInterrupt:
        pass
    finally:
        monitor.terminate()


if __name__ == "__main__":
    main()
