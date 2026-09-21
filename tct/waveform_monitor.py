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

SCOPE = "LeCroySatellite.Scope"
MAX_CHANNELS = 4
WAVEFORM_METRIC = "WAVEFORM_C"


class WaveformMonitor(StandaloneListener):
    """Listener keeping a running average of the waveforms of the current run"""

    def __init__(self, name: str, group: str, scope: str = SCOPE) -> None:
        super().__init__(name=name, group=group, interface=None)

        self._scope = scope
        self._lock = threading.Lock()
        self._sums: dict[int, numpy.ndarray] = {}
        self._counts: dict[int, int] = {}
        self._sampling_period: float | None = None
        self._sample_offset: float = 0.0
        self._num_triggers = 0
        self._dirty = False

        # Subscriptions have to match the metric names exactly, so subscribe
        # to every channel the scope could have
        topics = [f"STAT/{WAVEFORM_METRIC}{channel}" for channel in range(1, MAX_CHANNELS + 1)]
        topics += ["STAT/SAMPLING_PERIOD", "STAT/SAMPLE_OFFSET", "STAT/NUM_TRIGGERS"]
        self.set_topics(topics)

    def receive_metric(self, sender: str, metric: Metric, timestamp: datetime, value: Any) -> None:
        if sender != self._scope:
            return
        with self._lock:
            if metric.name.startswith(WAVEFORM_METRIC):
                channel = int(metric.name[len(WAVEFORM_METRIC) :])
                self._add_waveform(channel, numpy.asarray(value, dtype=float))
            elif metric.name == "SAMPLING_PERIOD":
                self._sampling_period = float(value)
            elif metric.name == "SAMPLE_OFFSET":
                self._sample_offset = float(value)
            elif metric.name == "NUM_TRIGGERS":
                # The counter starts from zero again in a new run
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

    def averages(self) -> tuple[numpy.ndarray | None, dict[int, numpy.ndarray], dict[int, int]]:
        """Time axis in s and averaged waveform in V per channel, or None if nothing arrived yet"""
        with self._lock:
            self._dirty = False
            averages = {channel: total / self._counts[channel] for channel, total in self._sums.items()}
            counts = dict(self._counts)
            if not averages or self._sampling_period is None:
                return None, averages, counts
            num_samples = max(len(avg) for avg in averages.values())
            times = self._sample_offset + self._sampling_period * numpy.arange(num_samples)
            return times, averages, counts

    @property
    def dirty(self) -> bool:
        return self._dirty

    def _process_tasks(self) -> None:
        """Run the queued CHIRP callbacks, normally done by run_listener()"""
        while True:
            try:
                callback, args = self.task_queue.get(block=False)
            except Empty:
                return
            try:
                callback(*args)
            except Exception as e:
                self.log.exception("Caught exception handling task '%s': %s", callback, repr(e))

    def run_plot(self, interval: float = 0.5) -> None:
        """Show the plot and keep it updated until the window is closed"""
        fig, ax = plt.subplots()
        ax.set_xlabel("Time from trigger [s]")
        ax.set_ylabel("Amplitude [V]")
        ax.grid(True)
        lines: dict[int, Any] = {}
        fig.canvas.mpl_connect("key_press_event", lambda event: self.reset() if event.key == "r" else None)

        while plt.fignum_exists(fig.number):
            self._process_tasks()
            if self.dirty:
                times, averages, counts = self.averages()
                for channel, average in averages.items():
                    if channel not in lines:
                        (lines[channel],) = ax.plot([], [], label=f"C{channel}")
                        ax.legend()
                    x = times[: len(average)] if times is not None else numpy.arange(len(average))
                    lines[channel].set_data(x, average)
                if times is None and averages:
                    ax.set_xlabel("Sample")
                ax.relim()
                ax.autoscale_view()
                num = ", ".join(f"C{channel}: {count}" for channel, count in sorted(counts.items()))
                ax.set_title(f"{self._scope} averaged waveforms ({num or 'waiting for data'}), 'r' resets")
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
