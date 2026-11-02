"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Base class of the live monitors, listening to the runs taken by the controller.
"""

import threading
from datetime import datetime
from queue import Empty
from typing import Any

from constellation.core.listener import StandaloneListener
from constellation.core.monitoring import Metric


class Monitor(StandaloneListener):
    """Listener keeping track of the current run of the controller"""
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

