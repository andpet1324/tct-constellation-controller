
import readline
import os
import glob
import pathlib

readline.parse_and_bind("tab: complete")
readline.set_completer_delims(" \t\n")

def readline_int(prompt: str, default: int | None = None) -> int:
    while True:
        if default is not None:
            response = input(prompt + " [" + str(default) + "]: > ").strip()
        else:
            response = input(prompt + ": > ").strip()
        if response == "" and default is not None:
            return default
        try:
            value = int(response, 0)
            return value
        except ValueError as err:
            print(f"{response} is not a valid integer! Failed with {err}.")
            continue

def readline_float(prompt: str, default: float | None = None) -> float:
    while True:
        if default is not None:
            response = input(prompt + " [" + str(default) + "]: > ").strip()
        else:
            response = input(prompt + ": > ").strip()
        if response == "" and default is not None:
            return default
        try:
            value = float(response)
            return value
        except ValueError as err:
            print(f"{response} is not a valid float! Failed with {err}.")
            continue


def readline_bool(prompt: str, default = False) -> bool:
    while True:
        response = input(prompt + " [Y/N]: > ").strip()
        if response == "":
            return default
        try:
            val = str(response).upper()
            if val in {"Y", "YES", "TRUE", "1"}:
                return True
            elif val in {"N", "NO", "FALSE", "0"}:
                return False
        except ValueError as err:
            print(f"{response} is not a valid answer! Failed with {err}.")
            continue

def complete_dir(text: str, state: int) -> str | None:
    pattern = os.path.expanduser(text) + "*"
    matches = sorted(m + "/" for m in glob.glob(pattern) if os.path.isdir(m))
    if state < len(matches):
        return matches[state]
    return None

def readline_dir(prompt: str, default = None) -> pathlib.Path | None:
    while True:
        readline.set_completer(complete_dir)
        response = input(prompt + " [" + str(default) + "]: > ").strip()
        if response == "":
            return default
        path = pathlib.Path(response).expanduser() # expands to home directory
        if path.is_dir():
            return path
        else:
            print("directory does not exist!")
            answer = readline_bool("create directory?")
            if answer == True:
                try:
                    path.mkdir(parents=True)
                    return path
                except Exception as err:
                    print(f"Exception when creating dir with {err}")
            return None