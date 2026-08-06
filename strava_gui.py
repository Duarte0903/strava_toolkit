#!/usr/bin/env python3
"""
strava_gui.py — desktop app to pick which Samsung Health workouts to export
for Strava, and to inspect any single workout (stats, heart-rate & pace charts,
GPS route).

Run it:
    python3 strava_gui.py
    python3 strava_gui.py /path/to/export_or_zip     (optional: preload)

Open your Samsung Health export (folder or .zip), click a workout to inspect it,
tick the ones you want, choose a format, and click Export. Upload the resulting
files free at https://www.strava.com/upload/select

Uses only Python's standard library (tkinter) — nothing to install.
"""

import math
import os
import sys
import webbrowser
from datetime import datetime, timezone

try:
    import tkinter as tk
    from tkinter import ttk, font as tkfont, filedialog, messagebox
except Exception:
    sys.exit(
        "This app needs Tk (tkinter), which ships with most Python installs.\n"
        "On macOS: install Python from python.org. On Linux: 'sudo apt install python3-tk'."
    )

import workout_core as wc
import export_log

UPLOAD_URL = "https://www.strava.com/upload/select"
CHECK, UNCHECK = "☑", "☐"

# ---- palette ------------------------------------------------------------- #
BG      = "#F4F5F7"   # window background
CARD    = "#FFFFFF"   # panels / list background
TEXT    = "#1A1D21"   # primary text
MUTED   = "#6B7280"   # secondary text
FAINT   = "#9AA1AC"   # tertiary / hints
BORDER  = "#E3E5E9"   # hairlines
ZEBRA   = "#F6F7F9"   # odd list rows
ACCENT  = "#FC5200"   # Strava orange
ACCENT_D = "#DA4600"  # accent, pressed
HR_LINE  = "#FC5200"
HR_FILL  = "#FFE1D2"
PACE_LINE = "#2F6FED"
PACE_FILL = "#DCE7FF"
ROUTE_LINE = "#FC5200"
START_DOT = "#0E9F6E"
END_DOT   = "#E0245E"


# =========================================================================== #
# Canvas charting — tiny polyline / route renderers (stdlib only)
# =========================================================================== #
def _projected(points, w, h, pad, invert):
    """Map (x, y) data points into pixel coords inside a padded box.

    invert=False -> larger y is higher on screen; invert=True flips it (used for
    pace, where a smaller number means faster and should read as 'up').
    Returns (pixel_coords, ymin, ymax).
    """
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    xr = (xmax - xmin) or 1.0
    yr = (ymax - ymin) or 1.0
    coords = []
    for x, y in points:
        px = pad + (x - xmin) / xr * (w - 2 * pad)
        ny = (y - ymin) / yr
        py = (pad + ny * (h - 2 * pad)) if invert else ((h - pad) - ny * (h - 2 * pad))
        coords.append((px, py))
    return coords, ymin, ymax


def render_series(canvas, points, line, fill, invert, fmtv, fonts):
    """Draw a filled sparkline for [(x, y), ...] into canvas, with min/max labels.

    Shows a muted placeholder when there's nothing to plot.
    """
    canvas.delete("all")
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    if w <= 1 or h <= 1:
        return
    pad = 12
    if len(points) < 2:
        canvas.create_text(w / 2, h / 2, text="No data for this workout",
                           fill=FAINT, font=fonts["small"])
        return

    coords, ymin, ymax = _projected(points, w, h, pad, invert)

    # soft area fill under the curve
    poly = coords + [(coords[-1][0], h - pad), (coords[0][0], h - pad)]
    canvas.create_polygon(poly, fill=fill, outline="")
    # baseline + curve
    canvas.create_line(pad, h - pad, w - pad, h - pad, fill=BORDER)
    flat = [c for xy in coords for c in xy]
    canvas.create_line(flat, fill=line, width=2, smooth=True, capstyle="round")

    # min/max value labels (top value / bottom value)
    top_v = ymin if invert else ymax
    bot_v = ymax if invert else ymin
    canvas.create_text(pad, pad, text=fmtv(top_v), anchor="nw",
                       fill=MUTED, font=fonts["small"])
    canvas.create_text(pad, h - pad - 2, text=fmtv(bot_v), anchor="sw",
                       fill=MUTED, font=fonts["small"])


def render_route(canvas, route, fonts):
    """Draw a GPS route trace, aspect-corrected, with start/end markers."""
    canvas.delete("all")
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    if w <= 1 or h <= 1:
        return
    pad = 14
    if len(route) < 2:
        canvas.create_text(w / 2, h / 2, text="No GPS — indoor / treadmill workout",
                           fill=FAINT, font=fonts["small"])
        return

    lats = [p[0] for p in route]
    lons = [p[1] for p in route]
    mean_lat = sum(lats) / len(lats)
    kx = math.cos(math.radians(mean_lat))          # shrink longitude to match

    xs = [lon * kx for lon in lons]
    ys = lats
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    xr = (xmax - xmin) or 1e-9
    yr = (ymax - ymin) or 1e-9

    # uniform scale so the shape isn't distorted, then centre it
    scale = min((w - 2 * pad) / xr, (h - 2 * pad) / yr)
    ox = (w - xr * scale) / 2
    oy = (h - yr * scale) / 2

    coords = []
    for x, y in zip(xs, ys):
        px = ox + (x - xmin) * scale
        py = (h - oy) - (y - ymin) * scale          # north = up
        coords.append((px, py))

    flat = [c for xy in coords for c in xy]
    canvas.create_line(flat, fill=ROUTE_LINE, width=2, smooth=True,
                       joinstyle="round", capstyle="round")

    def dot(cx, cy, color):
        r = 4
        canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline=CARD)
    dot(*coords[0], START_DOT)
    dot(*coords[-1], END_DOT)


# =========================================================================== #
# Detail panel — the "inspect one workout" pane
# =========================================================================== #
class DetailPanel(tk.Frame):
    def __init__(self, parent, fonts):
        super().__init__(parent, bg=BG)
        self.fonts = fonts
        self._detail = None

        # a card with a hairline border
        self.card = tk.Frame(self, bg=CARD, highlightthickness=1,
                             highlightbackground=BORDER, highlightcolor=BORDER)
        self.card.pack(fill="both", expand=True, padx=(6, 0))

        # empty-state (shown when nothing is focused)
        self.empty = tk.Label(self.card, text="Select a workout to inspect",
                              bg=CARD, fg=FAINT, font=fonts["h2"])

        # content (shown when a workout is focused)
        self.content = tk.Frame(self.card, bg=CARD)

        pad = 16
        self.header = tk.Label(self.content, bg=CARD, fg=TEXT, font=fonts["h1"],
                               anchor="w")
        self.header.pack(fill="x", padx=pad, pady=(pad, 2))
        self.subhead = tk.Label(self.content, bg=CARD, fg=MUTED, font=fonts["small"],
                                anchor="w")
        self.subhead.pack(fill="x", padx=pad, pady=(0, 10))

        self.tiles = tk.Frame(self.content, bg=CARD)
        self.tiles.pack(fill="x", padx=pad - 4)

        charts = tk.Frame(self.content, bg=CARD)
        charts.pack(fill="both", expand=True, padx=pad, pady=(12, pad))

        self.hr_canvas = self._chart_section(charts, "Heart rate")
        self.pace_canvas = self._chart_section(charts, "Pace")
        self.route_canvas = self._chart_section(charts, "Route")

        self.hr_canvas.bind("<Configure>", lambda e: self._draw_hr())
        self.pace_canvas.bind("<Configure>", lambda e: self._draw_pace())
        self.route_canvas.bind("<Configure>", lambda e: self._draw_route())

        self.show_empty()

    def _chart_section(self, parent, title):
        wrap = tk.Frame(parent, bg=CARD)
        wrap.pack(fill="both", expand=True, pady=(0, 10))
        tk.Label(wrap, text=title.upper(), bg=CARD, fg=FAINT,
                 font=self.fonts["label"], anchor="w").pack(fill="x", pady=(0, 3))
        cv = tk.Canvas(wrap, bg=CARD, highlightthickness=0, height=110)
        cv.pack(fill="both", expand=True)
        return cv

    # ---- state ---------------------------------------------------------- #
    def show_empty(self, msg="Select a workout to inspect"):
        self._detail = None
        self.content.pack_forget()
        self.empty.config(text=msg)
        self.empty.pack(fill="both", expand=True)

    def show(self, detail):
        self._detail = detail
        self.empty.pack_forget()
        self.content.pack(fill="both", expand=True)

        self.header.config(text="{} · {}".format(detail["sport"], detail["date"]))
        gps = "GPS route" if detail["has_gps"] else "No GPS"
        self.subhead.config(text=gps)
        self._build_tiles(detail)
        self._draw_hr()
        self._draw_pace()
        self._draw_route()

    # ---- tiles ---------------------------------------------------------- #
    def _build_tiles(self, d):
        for w in self.tiles.winfo_children():
            w.destroy()

        stats = []
        if d["distance_m"]:
            stats.append(("Distance", wc.fmt_distance(d["distance_m"])))
        stats.append(("Duration", wc.fmt_duration(d["duration_s"])))
        if d["avg_pace_s_per_km"]:
            stats.append(("Avg pace", wc.fmt_pace(d["avg_pace_s_per_km"])))
        if d["avg_hr"] is not None:
            stats.append(("Avg HR", "{:.0f} bpm".format(d["avg_hr"])))
        if d["max_hr"] is not None:
            stats.append(("Max HR", "{:.0f} bpm".format(d["max_hr"])))
        if d["calories"] is not None:
            stats.append(("Calories", "{:.0f}".format(d["calories"])))

        cols = 3
        for c in range(cols):
            self.tiles.grid_columnconfigure(c, weight=1, uniform="tile")
        for i, (name, val) in enumerate(stats):
            tile = tk.Frame(self.tiles, bg=CARD)
            tile.grid(row=i // cols, column=i % cols, sticky="ew", padx=4, pady=4)
            tk.Label(tile, text=val, bg=CARD, fg=TEXT,
                     font=self.fonts["value"], anchor="w").pack(fill="x")
            tk.Label(tile, text=name.upper(), bg=CARD, fg=FAINT,
                     font=self.fonts["label"], anchor="w").pack(fill="x")

    # ---- chart draws (also fire on resize) ------------------------------ #
    def _draw_hr(self):
        if not self._detail:
            return
        render_series(self.hr_canvas, self._detail["hr_series"], HR_LINE, HR_FILL,
                      invert=False, fmtv=lambda v: "{:.0f} bpm".format(v),
                      fonts=self.fonts)

    def _draw_pace(self):
        if not self._detail:
            return
        render_series(self.pace_canvas, self._detail["pace_series"], PACE_LINE,
                      PACE_FILL, invert=True, fmtv=wc.fmt_pace, fonts=self.fonts)

    def _draw_route(self):
        if not self._detail:
            return
        render_route(self.route_canvas, self._detail["route"], self.fonts)


# =========================================================================== #
# Main application
# =========================================================================== #
class App:
    def __init__(self, root, preload=None):
        self.root = root
        self.export_root = None
        self.ex_dir = None
        self.items = []              # all workouts
        self.view = []               # currently filtered workouts
        self.selected = set()        # ticked workout ids (for export)
        self.focused = None          # workout id shown in the detail panel
        self.exported = export_log.load_log()   # {id: "YYYY-MM-DD"}
        self.out_dir = tk.StringVar(value="")
        self.fmt = tk.StringVar(value="auto")
        self.hide_exported = tk.BooleanVar(value=False)

        root.title("Samsung Health → Strava exporter")
        root.geometry("1120x680")
        root.minsize(940, 560)
        root.configure(bg=BG)

        self._init_fonts()
        self._init_style()

        self._build_top()
        self._build_body()
        self._build_bottom()

        if preload:
            self.root.after(100, lambda: self._open_path(preload))

    # ---- theming -------------------------------------------------------- #
    def _init_fonts(self):
        fam = tkfont.nametofont("TkDefaultFont").actual("family")
        self.fonts = {
            "h1":    tkfont.Font(family=fam, size=16, weight="bold"),
            "h2":    tkfont.Font(family=fam, size=13),
            "value": tkfont.Font(family=fam, size=15, weight="bold"),
            "label": tkfont.Font(family=fam, size=8, weight="bold"),
            "small": tkfont.Font(family=fam, size=9),
            "body":  tkfont.Font(family=fam, size=10),
        }

    def _init_style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure(".", background=BG, foreground=TEXT, font=self.fonts["body"])
        st.configure("TFrame", background=BG)
        st.configure("TLabel", background=BG, foreground=TEXT)
        st.configure("Muted.TLabel", foreground=MUTED)
        st.configure("Hint.TLabel", foreground=FAINT)

        # Treeview (the workout list)
        st.configure("Treeview", background=CARD, fieldbackground=CARD,
                     foreground=TEXT, rowheight=30, borderwidth=0)
        st.configure("Treeview.Heading", background=BG, foreground=MUTED,
                     font=self.fonts["label"], relief="flat", borderwidth=0,
                     padding=(6, 6))
        st.map("Treeview.Heading", background=[("active", BG)])
        st.map("Treeview",
               background=[("selected", ACCENT)],
               foreground=[("selected", "#FFFFFF")])

        # Buttons
        st.configure("TButton", background=CARD, foreground=TEXT, borderwidth=1,
                     relief="flat", padding=(10, 5))
        st.map("TButton", background=[("active", ZEBRA)])
        st.configure("Accent.TButton", background=ACCENT, foreground="#FFFFFF",
                     borderwidth=0, padding=(14, 6), font=self.fonts["body"])
        st.map("Accent.TButton",
               background=[("active", ACCENT_D), ("disabled", "#F0B9A0")])

        # Inputs
        st.configure("TCombobox", fieldbackground=CARD, background=CARD)
        st.configure("TEntry", fieldbackground=CARD)
        st.configure("TRadiobutton", background=BG)
        st.map("TRadiobutton", background=[("active", BG)])
        st.configure("TCheckbutton", background=BG)
        st.map("TCheckbutton", background=[("active", BG)])

        # Progress bar
        st.configure("Horizontal.TProgressbar", troughcolor=BORDER,
                     background=ACCENT, borderwidth=0)

    # ---- layout --------------------------------------------------------- #
    def _build_top(self):
        f = ttk.Frame(self.root, padding=(14, 12, 14, 6))
        f.pack(fill="x")
        ttk.Label(f, text="Samsung Health → Strava", font=self.fonts["h1"]).pack(side="left")
        ttk.Button(f, text="Open export…", style="Accent.TButton",
                   command=self.open_dialog).pack(side="right")
        self.path_lbl = ttk.Label(f, text="No export loaded", style="Hint.TLabel")
        self.path_lbl.pack(side="right", padx=12)

    def _build_body(self):
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=14, pady=4)

        left = ttk.Frame(paned)
        self._build_filters(left)
        self._build_table(left)
        paned.add(left, weight=3)

        self.detail = DetailPanel(paned, self.fonts)
        paned.add(self.detail, weight=2)

    def _build_filters(self, parent):
        f = ttk.Frame(parent, padding=(0, 0, 0, 6))
        f.pack(fill="x")
        ttk.Label(f, text="Type:").pack(side="left")
        self.type_cb = ttk.Combobox(f, width=10, state="readonly", values=["All"])
        self.type_cb.set("All")
        self.type_cb.pack(side="left", padx=(2, 12))
        self.type_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_view())

        ttk.Label(f, text="Since:").pack(side="left")
        self.since_var = tk.StringVar()
        e = ttk.Entry(f, width=12, textvariable=self.since_var)
        e.pack(side="left", padx=(2, 2))
        e.bind("<Return>", lambda ev: self.refresh_view())
        ttk.Label(f, text="(YYYY-MM-DD)", style="Hint.TLabel").pack(side="left", padx=(0, 12))

        ttk.Label(f, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        se = ttk.Entry(f, width=14, textvariable=self.search_var)
        se.pack(side="left", padx=(2, 12))
        se.bind("<KeyRelease>", lambda ev: self.refresh_view())

        ttk.Checkbutton(f, text="Hide exported", variable=self.hide_exported,
                        command=self.refresh_view).pack(side="left", padx=(0, 12))

        ttk.Button(f, text="Select shown", command=self.select_shown).pack(side="left")
        ttk.Button(f, text="Clear", command=self.clear_selection).pack(side="left", padx=4)

    def _build_table(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill="both", expand=True)
        cols = ("sel", "date", "type", "dur", "dist", "hr", "gps")
        self.tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="none")
        heads = {
            "sel": ("", 34), "date": ("Date", 150), "type": ("Type", 80),
            "dur": ("Duration", 90), "dist": ("Distance", 100),
            "hr": ("Avg HR", 70), "gps": ("GPS", 50),
        }
        for c, (txt, w) in heads.items():
            self.tree.heading(c, text=txt)
            anchor = "center" if c in ("sel", "gps", "hr") else "w"
            self.tree.column(c, width=w, anchor=anchor, stretch=(c == "date"))
        self.tree.tag_configure("odd", background=ZEBRA)
        self.tree.tag_configure("even", background=CARD)
        vsb = ttk.Scrollbar(f, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Button-1>", self.on_click)
        self.tree.bind("<space>", self.on_space)

    def _build_bottom(self):
        f = ttk.Frame(self.root, padding=(14, 8))
        f.pack(fill="x")
        ttk.Label(f, text="Format:").pack(side="left")
        for txt, val in [("Auto (map if GPS)", "auto"), ("TCX", "tcx"), ("GPX", "gpx")]:
            ttk.Radiobutton(f, text=txt, value=val, variable=self.fmt).pack(side="left", padx=2)

        ttk.Button(f, text="Output…", command=self.pick_out).pack(side="left", padx=(12, 2))
        self.out_lbl = ttk.Label(f, textvariable=self.out_dir, style="Muted.TLabel", width=28)
        self.out_lbl.pack(side="left")

        self.export_btn = ttk.Button(f, text="Export selected", style="Accent.TButton",
                                     command=self.export)
        self.export_btn.pack(side="right")
        self.count_lbl = ttk.Label(f, text="0 selected", style="Muted.TLabel")
        self.count_lbl.pack(side="right", padx=10)

        pf = ttk.Frame(self.root, padding=(14, 0))
        pf.pack(fill="x")
        self.progress = ttk.Progressbar(pf, mode="determinate")
        self.progress.pack(fill="x")
        self.status = ttk.Label(self.root, text="", padding=(14, 4), style="Muted.TLabel")
        self.status.pack(fill="x")

    # ---- loading -------------------------------------------------------- #
    def open_dialog(self):
        choice = messagebox.askquestion(
            "Open export",
            "Is your export a single .zip file?\n\nYes = pick the .zip\nNo = pick the unzipped folder",
        )
        if choice == "yes":
            p = filedialog.askopenfilename(title="Select export .zip",
                                           filetypes=[("Zip files", "*.zip"), ("All files", "*.*")])
        else:
            p = filedialog.askdirectory(title="Select unzipped export folder")
        if p:
            self._open_path(p)

    def _open_path(self, p):
        self.status.config(text="Loading…")
        self.root.update_idletasks()
        try:
            root, note = wc.resolve_export(p)
            self.ex_dir, self.items = wc.load_workouts(root)
        except Exception as e:
            messagebox.showerror("Couldn't open export", str(e))
            self.status.config(text="")
            return
        self.export_root = root
        self.selected.clear()
        self.focused = None
        self.detail.show_empty()
        anchor = os.path.dirname(os.path.abspath(p)) if os.path.isfile(p) else os.path.abspath(p)
        self.out_dir.set(os.path.join(anchor, "strava_upload"))
        self.path_lbl.config(text="{} — {} workouts".format(os.path.basename(p) or root, len(self.items)))
        self.type_cb.config(values=["All"] + wc.sport_labels(self.items))
        self.type_cb.set("All")
        self.status.config(text=(note + "  " if note else "") + "Loaded {} workouts.".format(len(self.items)))
        self.refresh_view()

    # ---- filtering / view ----------------------------------------------- #
    def refresh_view(self):
        typ = self.type_cb.get()
        since_ms = None
        s = self.since_var.get().strip()
        if s:
            try:
                since_ms = int(datetime.strptime(s, "%Y-%m-%d")
                               .replace(tzinfo=timezone.utc).timestamp() * 1000)
            except ValueError:
                pass
        q = self.search_var.get().strip().lower()
        hide_exp = self.hide_exported.get()

        self.view = []
        for it in self.items:
            if typ != "All" and it["label"] != typ:
                continue
            if hide_exp and it["id"] in self.exported:
                continue
            if since_ms and (it["start"] or 0) < since_ms:
                continue
            if q:
                hay = (wc.fmt_date(it["start"], it.get("tz_offset_ms", 0)) + " " + it["label"]).lower()
                if q not in hay:
                    continue
            self.view.append(it)

        self.tree.delete(*self.tree.get_children())
        for i, it in enumerate(self.view):
            box = CHECK if it["id"] in self.selected else UNCHECK
            self.tree.insert("", "end", iid=it["id"],
                             tags=("odd" if i % 2 else "even",),
                             values=(
                                 box, wc.fmt_date(it["start"], it.get("tz_offset_ms", 0)), it["label"],
                                 wc.fmt_duration(it["duration_s"]), wc.fmt_distance(it["distance_m"]),
                                 "" if it["avg_hr"] is None else "{:.0f}".format(it["avg_hr"]),
                                 "✓" if it["has_gps"] else "",
                             ))
        self.update_count()

    # ---- selection & inspection ----------------------------------------- #
    def on_click(self, event):
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        col = self.tree.identify_column(event.x)
        if col == "#1":                 # the checkbox column -> toggle only
            self.toggle(iid)
        else:                            # any other column -> inspect
            self.focus_workout(iid)

    def on_space(self, event):
        for iid in self.tree.selection() or []:
            self.toggle(iid)

    def focus_workout(self, iid):
        self.focused = iid
        by_id = {it["id"]: it for it in self.items}
        it = by_id.get(iid)
        if not it:
            return
        try:
            detail = wc.load_detail(self.ex_dir, it)
        except Exception:
            self.detail.show_empty("Couldn't read this workout's data")
            return
        self.detail.show(detail)

    def toggle(self, iid):
        if iid in self.selected:
            self.selected.discard(iid)
            box = UNCHECK
        else:
            self.selected.add(iid)
            box = CHECK
        self.tree.set(iid, "sel", box)
        self.update_count()

    def select_shown(self):
        for it in self.view:
            self.selected.add(it["id"])
            self.tree.set(it["id"], "sel", CHECK)
        self.update_count()

    def clear_selection(self):
        self.selected.clear()
        for iid in self.tree.get_children():
            self.tree.set(iid, "sel", UNCHECK)
        self.update_count()

    def update_count(self):
        self.count_lbl.config(text="{} selected".format(len(self.selected)))

    # ---- output / export ------------------------------------------------ #
    def pick_out(self):
        d = filedialog.askdirectory(title="Choose output folder")
        if d:
            self.out_dir.set(d)

    def export(self):
        if not self.selected:
            messagebox.showinfo("Nothing selected", "Tick some workouts first.")
            return
        out = self.out_dir.get().strip()
        if not out:
            self.pick_out()
            out = self.out_dir.get().strip()
            if not out:
                return

        by_id = {it["id"]: it for it in self.items}
        chosen = [by_id[i] for i in self.selected if i in by_id]
        fmt = self.fmt.get()

        self.export_btn.config(state="disabled")
        self.progress.config(maximum=len(chosen), value=0)
        made = skipped = 0
        made_ids = []
        for i, it in enumerate(chosen, 1):
            try:
                path, kind = wc.export_workout(self.ex_dir, it, out, fmt)
                if path:
                    made += 1
                    made_ids.append(it["id"])
                else:
                    skipped += 1
            except Exception:
                skipped += 1
            self.progress.config(value=i)
            self.status.config(text="Exporting… {}/{}".format(i, len(chosen)))
            self.root.update_idletasks()

        self.export_btn.config(state="normal")
        warn = ""
        if made_ids:
            # remember what we exported; keep the session correct even if the
            # write to disk fails.
            for wid in made_ids:
                self.exported.setdefault(wid, "")
            try:
                self.exported = export_log.mark_exported(made_ids)
            except Exception as e:
                warn = "  (couldn't save export log: {})".format(e)
            self.refresh_view()
        self.status.config(text="Exported {} files ({} skipped) to {}{}".format(
            made, skipped, out, warn))
        if made and messagebox.askyesno(
            "Done",
            "Exported {} files to:\n{}\n\nOpen Strava's upload page now?".format(made, out),
        ):
            webbrowser.open(UPLOAD_URL)


def main():
    preload = sys.argv[1] if len(sys.argv) > 1 else None
    root = tk.Tk()
    App(root, preload)
    root.mainloop()


if __name__ == "__main__":
    main()
