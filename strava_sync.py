#!/usr/bin/env python3
"""
strava_sync.py — a small terminal UI that turns a Samsung Health export into
Strava-ready files by driving the two converters (samsung_to_gpx.py and
samsung_to_tcx.py) that live next to it.

Usage:
  python3 strava_sync.py /path/to/export            (folder OR .zip)
  python3 strava_sync.py                             (it will ask for the path)

It figures out where the workout data is (unzipping if you hand it a .zip),
then shows a menu:
  - Convert everything  (GPX for GPS workouts, TCX for the rest — no duplicates)
  - GPX only
  - TCX only
  - Change the "only since" date filter
Output goes to a 'strava_upload' folder that it prints for you; upload those
files free at https://www.strava.com/upload/select
"""

import glob
import os
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import samsung_export as sx  # noqa: E402

GPX = os.path.join(HERE, "samsung_to_gpx.py")
TCX = os.path.join(HERE, "samsung_to_tcx.py")
UPLOAD_URL = "https://www.strava.com/upload/select"

# --- pretty terminal helpers ------------------------------------------------
if os.name == "nt":
    os.system("")  # enable ANSI escapes on Windows terminals
C = {
    "b": "\033[1m", "dim": "\033[2m", "r": "\033[0m",
    "cyan": "\033[36m", "green": "\033[32m", "yellow": "\033[33m", "red": "\033[31m",
}


def color(s, *names):
    return "".join(C[n] for n in names) + s + C["r"]


def rule(char="─", width=58):
    print(color(char * width, "dim"))


def banner():
    print()
    print(color("  Samsung Health  →  Strava", "b", "cyan"))
    print(color("  turn your watch workouts into upload-ready files", "dim"))
    rule()


# --- locating the export ----------------------------------------------------
def resolve_export(path):
    """Accept a folder or a .zip; return the folder that holds the exercise CSV."""
    path = os.path.abspath(os.path.expanduser(path.strip().strip('"').strip("'")))
    if not os.path.exists(path):
        sys.exit(color("That path doesn't exist: " + path, "red"))

    if zipfile.is_zipfile(path):
        dest = os.path.join(tempfile.gettempdir(), "samsung_export_" + str(os.getpid()))
        os.makedirs(dest, exist_ok=True)
        print(color("Unzipping export...", "dim"))
        with zipfile.ZipFile(path) as z:
            z.extractall(dest)
        path = dest

    root = find_root(path)
    if not root:
        sys.exit(color(
            "Couldn't find Samsung workout data under:\n  " + path +
            "\nExpected a 'com.samsung.health.exercise.*.csv' (or "
            "'com.samsung.shealth.exercise.*.csv') file somewhere inside.", "red"))
    return root


def find_root(path):
    return sx.find_root(path)


# --- running the converters -------------------------------------------------
def run(script, export_root, out_dir, extra=None):
    cmd = [sys.executable, script, export_root, "--out", out_dir] + (extra or [])
    print(color("→ " + os.path.basename(script), "yellow"))
    try:
        subprocess.run(cmd, check=False)
    except FileNotFoundError:
        print(color("Missing script: " + script, "red"))


def count(folder, ext):
    return len(glob.glob(os.path.join(folder, "*." + ext))) if os.path.isdir(folder) else 0


def do_convert(export_root, out_base, mode, since):
    tcx_dir = os.path.join(out_base, "tcx")
    gpx_dir = os.path.join(out_base, "gpx")
    since_args = ["--since", since] if since else []

    rule()
    if mode in ("all", "gpx"):
        run(GPX, export_root, gpx_dir, since_args)
    if mode in ("all", "tcx"):
        # in "all" mode, skip GPS workouts here so they aren't duplicated by GPX
        extra = list(since_args) + (["--skip-gps"] if mode == "all" else [])
        run(TCX, export_root, tcx_dir, extra)
    rule()

    g, t = count(gpx_dir, "gpx"), count(tcx_dir, "tcx")
    print(color("Done.", "b", "green"), "GPX:", color(str(g), "b"), " TCX:", color(str(t), "b"))
    print("Files are in:", color(out_base, "cyan"))
    if g:
        print("  • GPX (with maps):", gpx_dir)
    if t:
        print("  • TCX (heart rate / distance):", tcx_dir)
    print("\nUpload them free at:", color(UPLOAD_URL, "b", "cyan"))
    print(color("(drag files in, ~50–100 at a time)", "dim"))


# --- menu -------------------------------------------------------------------
MENU = """
{b}What do you want to do?{r}
  {c}1{r}  Convert everything   {d}(GPX for GPS workouts, TCX for the rest){r}
  {c}2{r}  GPX only             {d}(workouts that have a GPS map){r}
  {c}3{r}  TCX only             {d}(heart-rate / distance, no map){r}
  {c}4{r}  Set date filter      {d}(only workouts on/after a date){r}
  {c}q{r}  Quit
"""


def main():
    banner()
    arg = sys.argv[1] if len(sys.argv) > 1 else input("Path to your export (folder or .zip): ")
    arg_abs = os.path.abspath(os.path.expanduser(arg.strip().strip('"').strip("'")))
    export_root = resolve_export(arg)
    # put output next to the file/folder the user gave us (not the temp copy)
    anchor = os.path.dirname(arg_abs) if os.path.isfile(arg_abs) else arg_abs
    out_base = os.path.join(anchor, "strava_upload")
    print("Export found:", color(export_root, "green"))

    since = None
    while True:
        extra = "   " + color("filter: since " + since, "yellow") if since else ""
        print(MENU.format(b=C["b"], r=C["r"], c=C["cyan"], d=C["dim"]) + extra)
        choice = input(color("Choose: ", "b")).strip().lower()

        if choice in ("q", "quit", "exit"):
            print("Bye.")
            return
        if choice == "1":
            do_convert(export_root, out_base, "all", since)
        elif choice == "2":
            do_convert(export_root, out_base, "gpx", since)
        elif choice == "3":
            do_convert(export_root, out_base, "tcx", since)
        elif choice == "4":
            v = input("Only workouts on/after (YYYY-MM-DD, blank to clear): ").strip()
            since = v or None
            print(color("Filter set." if since else "Filter cleared.", "green"))
        else:
            print(color("Didn't catch that — pick 1, 2, 3, 4, or q.", "red"))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye.")
