from collections.abc import Callable
import argparse
import readline
import time
readline.parse_and_bind("tab: complete")

from constellation.core.controller_configuration import load_config

from .controller import TCTController
from .scans.common import add_common_arguments, bring_up
from .menu_layout import MENU
from .menu_meta import SATELLITES

class Menu:
    def __init__(self, 
        name: str = "", 
        parent: "Menu | None" = None
    ) -> None:
            self._name = name
            self._parent = parent

            self._submenus = {}

            self._lines = {
                "EXIT": ("Exit menu", None),
                "HELP": ("Print list of commands", self.print_help),
                "PWD": ("Print current directory", self.path_print)
            }

    def _complete(self, text, state):
        matches = [w for w in self._lines.keys() if w.startswith(text.upper())]
        if state < len(matches):
            return matches[state]
        return None

    def line(self, cmd: str, descr: str, func: Callable) -> "Menu":
        self._lines[cmd.upper()] = (descr, func)
        return self

    def print_help(self, tgt: dict[str, any]) -> None:
        for name, (descr, _) in self._lines.items():
            print(f"{name:<12} {descr}")

    def path(self) -> str:
        if self._parent is None:
                return "/ROOT/"
        else:
            name = self._parent.path()
            return name + self._name + "/"

    def path_print(self, tgt: dict[str, any]) -> None:
        print(self.path())

    def steer(self, tgt: dict[str, any]) -> None:
        while True:
            readline.set_completer(self._complete)
            try:
                cmd = input(self.path() + " > ").strip().upper()
            except KeyboardInterrupt:
                print("Exiting menu")
                exit(0)
            if not cmd:
                continue
            if cmd == "EXIT":
                return
            elif cmd in self._lines:
                _, func = self._lines[cmd]
                try:
                    func(tgt)
                except Exception as err:
                    print(f"function {func} failed with {err}")
            else:
                print("Command not in list of commands. Type HELP for list of commands.")

    def submenu(self, cmd, descr):
        sub = Menu(cmd.upper(), parent=self)
        self.line(cmd, f"{descr} →", sub.steer)
        return sub

    def load_subs(self, layout: dict[str, any]):
        for top_cmd, (top_descr, top_func) in layout.items():
            if isinstance(top_func, dict):
                sub = self.submenu(top_cmd, top_descr)
                for cmd, (descr, func) in top_func.items():
                    sub.line(cmd, descr, func)
            else:
                self.line(top_cmd, top_descr, top_func)

def find_sat(satellites: dict, name: str) -> tuple[str, any] | tuple[None, None]:
    try:
        for k, v in satellites.items():
            if name in k:
                return k, v
        return (None, None)
    except RuntimeError as err:
        print(f"Finding satellites failed with {err}")
        return (None, None)

def main(args: list[str] | None = None):
    parser = argparse.ArgumentParser(description="TCT Menu")
    parser.add_argument("-daq", required=True, type=str, help="Provide the type of DAQ used. Options: Alibava.DAQ, LeCroySatellite.Scope")
    add_common_arguments(parser)
    opts = parser.parse_args(args)
    daq_name = opts.daq

    ctrl = TCTController(opts.group, daq=daq_name)
    satellite_names = []
    while True:
        satellites = ctrl.constellation.satellites
        _, daq = find_sat(satellites, daq_name)
        hv_name, hv = find_sat(satellites, "Keithley")
        writer_name, writer = find_sat(satellites, "H5DataWriter")
        stage_name, stage = find_sat(satellites, "Standa")
        satellite_names = [daq_name, hv_name, writer_name, stage_name]
        if all(name is not None for name in satellite_names):
            break

    if not opts.no_launch:
        bring_up(ctrl, opts.config, satellite_names)

    root = Menu("Menu")
    root.load_subs(MENU)
    tgt = {"ctrl": ctrl, "cfg": opts.config, "hv": hv, "writer": writer, "stage": stage, "daq": daq}
    root.steer(tgt)

if __name__ == "__main__":
    main()