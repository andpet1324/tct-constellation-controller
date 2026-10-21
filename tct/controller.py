"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Controller for the TCT setup, taking one run per scan point
"""

import pathlib
import threading
import time
from datetime import datetime
from typing import Any

from constellation.core.controller import ScriptableController
from constellation.core.controller_configuration import load_config
from constellation.core.listener import MonitoringListener
from constellation.core.monitoring import schedule_metric
from constellation.core.monitoring import Metric
from constellation.core.protocol.cscp1 import SatelliteState


class TCTController(ScriptableController, MonitoringListener):
    """Controller which ends a run once enough triggers have been collected.
    The number of triggers is taken from the TRIG metric of the Alibava satellite, or NUM_TRIGGERS from LeCroySatellite.
    """

    def __init__(self, *args: Any, daq: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._daq = daq
        self._data_dir = None
        self._triggers_lock = threading.Lock()
        self._num_triggers = 0
        self._run_id = None

        # Subscribe to the trigger counter of the 
        if daq.upper() == "ALIBAVA":
            print("Using STAT/TRIG metric!")
            self.set_topics(["STAT/TRIG"])
        elif daq.upper() == "LECROY":
            self.set_topics(["STAT/NUM_TRIGGERS"])

    def receive_metric(self, sender: str, metric: Metric, timestamp: datetime, value: Any) -> None:
        if (metric.name == "TRIG" or metric.name == "NUM_TRIGGERS") and (sender.split(".", 1)[0]).upper() == self._daq.upper():
            with self._triggers_lock:
                self._num_triggers = int(value)

    def set_data_dir(self, config_path: str, writer: str) -> None:
        cfg = load_config(config_path)
        self._data_dir = str(cfg.get_satellite_configuration(writer).get_path("output_directory"))
    
    @property
    def num_triggers(self) -> int:
        with self._triggers_lock:
            return self._num_triggers

    def reset_triggers(self) -> None:
        with self._triggers_lock:
            self._num_triggers = 0

    def bring_up(self, config_path: pathlib.Path, satellites: list[str]) -> None:
        """Initialize and launch the constellation from a configuration file"""
        cfg = load_config(config_path)
        self.await_satellites(satellites)
        self.constellation.initialize(cfg)
        self.await_state(SatelliteState.INIT)
        self.constellation.launch()
        self.await_state(SatelliteState.ORBIT, timeout = 360) # Can take a long time to bias

    def take_run(self, run_identifier: str, triggers: int, timeout: int = 360) -> int:
        """Take a single run until triggers have been collected.
        """
        timeout = timeout + 0.01 * triggers # Add some time if we have a lot of triggers
        self.reset_triggers()

        self.constellation.start(run_identifier)
        self.await_state(SatelliteState.RUN)

        deadline = time.monotonic() + timeout
        try:
            while self.num_triggers < triggers:
                self.log.info(f"Trigger {self.num_triggers} / {triggers}")
                if time.monotonic() > deadline:
                    raise TimeoutError(
                        f"Run {run_identifier} collected {self.num_triggers}/{triggers} triggers in {timeout}s"
                    )
                time.sleep(0.1)
        finally:
            self.constellation.stop()
            self.await_state(SatelliteState.ORBIT)
        
        self._run_id = run_identifier
        collected = self.num_triggers
        self.log.status(f"Run {run_identifier} finished with {collected} triggers")
        return collected

    def reentry(self) -> None:
        # land satellites
        self.constellation.land()
        self.await_state(SatelliteState.INIT, timeout = 360)
        
        super().reentry()

    @schedule_metric("", 1, [SatelliteState.ORBIT])
    def RUN_IDENTIFIER(self) -> str | None:
        return self._run_id

    @schedule_metric("", 10, [SatelliteState.ORBIT])
    def DATA_DIRECTORY(self) -> str | None:
        return self._data_dir
