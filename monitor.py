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
from .alibava.alibava_monitor import AlibavaMonitor
from .lecroy.monitor_lecroy import LeCroyMonitor


def main(args: Any = None) -> None:
    parser = argparse.ArgumentParser(description="Live display of the Alibava or LeCroy data")
    parser.add_argument("-g", "--group", default="tct", help="Constellation group name")
    parser.add_argument("-n", "--name", default="tct", help="Monitor name")
    parser.add_argument("-daq", "--daq", required=True, help="Type and Name of the DAQ Satellite. For example Alibava.DAQ or LeCroy.Scope")
    parser.add_argument("--interval", type=float, default=0.5, help="Plot refresh interval in s")
    opts = parser.parse_args(args)

    daq_id = opts.daq
    if opts.daq.split(".")[0].upper() == "ALIBAVA":
        monitor = AlibavaMonitor(opts.name, opts.group, daq_id)
    elif opts.daq.split(".")[0].upper() == "LECROY":
        monitor = LeCroyMonitor(opts.name, opts.group, daq_id)
    else:
        raise(ValueError, "DAQ does not match Alibava or LeCroy!")

    root = Menu("Monitor")
    root.load_subs({opts.daq.split(".")[0].upper(): monitor_menu()[opts.daq.split(".")[0].upper()]})
    try:
        root.steer({opts.daq.split(".")[0].lower(): monitor, "interval": opts.interval})
    finally:
        monitor.terminate()


if __name__ == "__main__":
    main()
