"""
SPDX-FileCopyrightText: 2026 A. Pettersson, DESY
SPDX-License-Identifier: EUPL-1.2

Entry point of the live monitors, listening to the runs taken by the controller.
The monitor base class lives in monitor_base.py.
"""

import argparse
import time
from typing import Any

from .menu_layout import monitor_menu
from .controller import TCTController
from .menu import Menu, find_sat
from .alibava.monitor_alibava import AlibavaMonitor
from .lecroy.monitor_lecroy import LeCroyMonitor


def main(args: Any = None) -> None:
    parser = argparse.ArgumentParser(description="Live display of the Alibava or LeCroy data")
    parser.add_argument("-g", "--group", default="tct", help="Constellation group name")
    parser.add_argument("-n", "--name", default="tct", help="Monitor name")
    parser.add_argument("-daq", "--daq", required=True, choices=["Alibava", "LeCroy"], help="Type of DAQ to monitor")
    parser.add_argument("--interval", type=float, default=0.5, help="Plot refresh interval in s")
    opts = parser.parse_args(args)

    ctrl = TCTController(opts.group)
    daq_id = None
    while daq_id is None:
        time.sleep(1) # Wait for satellites to connect
        daq_id, _ = find_sat(ctrl.constellation.satellites, opts.daq)

    if opts.daq.upper() == "ALIBAVA":
        monitor = AlibavaMonitor(opts.name, opts.group, daq_id)
    elif opts.daq.upper() == "LECROY":
        monitor = LeCroyMonitor(opts.name, opts.group, daq_id)
    else:
        raise(ValueError, "DAQ does not match Alibava or LeCroy!")

    root = Menu("Monitor")
    root.load_subs({opts.daq.upper(): monitor_menu()[opts.daq.upper()]})
    try:
        root.steer({opts.daq.lower(): monitor, "interval": opts.interval})
    finally:
        monitor.terminate()
        ctrl.terminate()


if __name__ == "__main__":
    main()
