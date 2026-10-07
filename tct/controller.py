"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Controller for the TCT setup, taking one run per scan point
"""

import threading
import time
from datetime import datetime
from typing import Any

from constellation.core.controller import ScriptableController
from constellation.core.listener import MonitoringListener
from constellation.core.monitoring import Metric
from constellation.core.protocol.cscp1 import SatelliteState


class TCTController(ScriptableController, MonitoringListener):
    """Controller which ends a run once enough triggers have been collected.

    The number of triggers is taken from the NUM_TRIGGERS metric of the
    oscilloscope satellite, so that every scan point holds the same number of
    waveforms instead of the same amount of time. Points where the trigger rate
    is low then take longer rather than ending up with fewer events.
    """

    def __init__(self, *args: Any, scope: str = "LeCroySatellite.Scope", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._scope = scope
        self._triggers_lock = threading.Lock()
        self._num_triggers = 0

        # Subscribe to the trigger counter of the oscilloscope
        self.set_topics(["STAT/NUM_TRIGGERS"])

    def receive_metric(self, sender: str, metric: Metric, timestamp: datetime, value: Any) -> None:
        if metric.name == "NUM_TRIGGERS" and sender == self._scope:
            with self._triggers_lock:
                self._num_triggers = int(value)

    @property
    def num_triggers(self) -> int:
        with self._triggers_lock:
            return self._num_triggers

    def reset_triggers(self) -> None:
        with self._triggers_lock:
            self._num_triggers = 0

    def take_run(self, run_identifier: str, triggers: int, timeout: float = 300.0) -> int:
        """Take a single run until triggers have been collected.
        """
        self.reset_triggers()

        self.constellation.start(run_identifier)
        self.await_state(SatelliteState.RUN)

        deadline = time.monotonic() + timeout
        try:
            while self.num_triggers < triggers:
                if time.monotonic() > deadline:
                    raise TimeoutError(
                        f"Run {run_identifier} collected {self.num_triggers}/{triggers} triggers in {timeout}s"
                    )
                time.sleep(0.1)
        finally:
            self.constellation.stop()
            self.await_state(SatelliteState.ORBIT)

        collected = self.num_triggers
        self.log.status(f"Run {run_identifier} finished with {collected} triggers")
        return collected

    def reentry(self) -> None:
        # land satellites
        self.constellation.land()
        self.await_state(SatelliteState.INIT)
        
        super().reentry()
