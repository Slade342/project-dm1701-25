"""Local Tk front end. All USB operations are delegated to qdmr's dmrconf."""
from __future__ import annotations

import os
import json
from pathlib import Path
import queue
import shlex
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

from .backend import Backend, BackendError, create_backend, _USB_LOCK
from .model import Codeplug, frequency_mhz
from .discovery import native_lab_port

ROOT = Path(__file__).resolve().parent.parent
PROFILE_LABELS = {"Stock DM-1701": "stock", "OpenGD77 / OpenDM1701": "opengd77"}
PRODUCT_NAME = os.environ.get("PROJECT_DM1701_NAME", "DM-1701 Studio")
PRODUCT_SHORT = os.environ.get("PROJECT_DM1701_SHORT", "DM-1701")
BUILD_LABEL = os.environ.get("PROJECT_DM1701_BUILD_LABEL", "0.4 EXPERIMENTAL")
# Original dark control-room palette inspired by APX CPS hierarchy.  No
# Motorola artwork or firmware is copied into the project.
BG, PANEL, CARD, INPUT = "#0b111b", "#111b2a", "#19283b", "#142238"
TEXT, MUTED, ACCENT, BORDER = "#eef5fb", "#9db1c5", "#56c7f0", "#2d435c"
ctk.set_appearance_mode("dark")


class _Programmer:
    """Defer process discovery to the worker that invokes an operation."""
    def __init__(self, path, mode):
        self.path, self.mode, self.backend = path, mode, None

    def __getattr__(self, name):
        def operation(*args, **kwargs):
            if self.backend is None:
                self.backend = create_backend(self.path, mode=self.mode)
            return getattr(self.backend, name)(*args, **kwargs)
        return operation


class Studio:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{PRODUCT_NAME} — {BUILD_LABEL}")
        self.root.geometry("1380x870")
        self.root.minsize(1080, 720)
        self.root.configure(bg=BG)
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("TLabelframe", background=BG, bordercolor=BORDER, relief="flat")
        style.configure("TLabelframe.Label", background=BG, foreground=MUTED)
        style.configure("TEntry", fieldbackground=INPUT, foreground=TEXT, bordercolor=BORDER, padding=6, insertcolor=TEXT)
        style.configure("TCombobox", fieldbackground=INPUT, background=INPUT, foreground=TEXT, arrowcolor=ACCENT, padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", INPUT)], foreground=[("readonly", TEXT)], selectbackground=[("readonly", INPUT)], selectforeground=[("readonly", TEXT)])
        style.configure("TCheckbutton", background=BG, foreground=MUTED, indicatorbackground=INPUT)
        style.map("TCheckbutton", background=[("active", BG)], foreground=[("active", TEXT)])
        style.configure("Treeview", rowheight=34, background=PANEL, fieldbackground=PANEL, foreground=TEXT, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=CARD, foreground=TEXT, relief="flat", padding=8, font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#1e5270")], foreground=[("selected", "#ffffff")])
        style.configure("TButton", padding=(12, 7), background=CARD, foreground=TEXT, bordercolor=BORDER)
        style.configure("Primary.TButton", background=ACCENT, foreground="white", bordercolor=ACCENT)
        style.map("Primary.TButton", background=[("active", "#125394"), ("disabled", "#aec6df")], foreground=[("disabled", "white")])
        style.configure("Header.TLabel", font=("Segoe UI", 21, "bold"))
        style.configure("Nav.Treeview", rowheight=36, background="#101c2b", fieldbackground="#101c2b", foreground=TEXT, font=("Segoe UI", 10))
        style.map("Treeview.Heading", background=[("active", INPUT)])
        style.configure("Vertical.TScrollbar", background=INPUT, troughcolor=CARD, borderwidth=0, arrowcolor=MUTED)
        style.configure("Horizontal.TScrollbar", background=INPUT, troughcolor=CARD, borderwidth=0, arrowcolor=MUTED)
        style.configure("Studio.TNotebook", background=BG, borderwidth=0, tabmargins=0, bordercolor=BG, lightcolor=BG, darkcolor=BG)
        style.configure("Treeview", bordercolor=CARD, lightcolor=CARD, darkcolor=CARD)
        style.layout("Studio.TNotebook.Tab", [])
        root.option_add("*TCombobox*Listbox.background", INPUT)
        root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.document = Codeplug.new()
        self.path: Path | None = None
        self.busy = False
        self.result_queue: queue.Queue = queue.Queue()
        self.discovery_queue: queue.Queue = queue.Queue()
        self.discovering = False
        self.discovery_backend = None
        self.operation_widgets: list = []
        self.profile = tk.StringVar(value="Choose installed firmware...")
        self.executable = tk.StringVar()
        self.backup_dir = tk.StringVar(value=str(Path.home() / "Documents" / "DM1701 Backups"))
        self.status = tk.StringVar(value="Local editor ready. Connect your radio when you need to read it.")
        self.search = tk.StringVar()
        self.radio_id = tk.StringVar()
        self.radio_name = tk.StringVar(value="My radio")
        self.confirm_model = tk.BooleanVar(value=False)
        self.auto_detect = tk.BooleanVar(value=True)
        self.detected_status = tk.StringVar(value="Radio: waiting for connection")
        self.backend_mode = tk.StringVar(value="Automatic")
        self.page_title = tk.StringVar(value="Channels")
        self.project_name = tk.StringVar(value="Untitled codeplug")
        self._make_ui()
        self._render()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.bind("<Command-s>", lambda _: self._save())
        self.root.bind("<Control-s>", lambda _: self._save())
        self.root.after(100, self._poll)
        self.root.after(1200, self._discover)

    def _button(self, parent, title, action, **kwargs):
        primary = kwargs.pop("primary", False)
        widget = ttk.Button(parent, text=title, command=action,
                            style="Primary.TButton" if primary else "TButton", **kwargs)
        self.operation_widgets.append(widget)
        return widget

    def _make_ui(self):
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        for label, action in [("New codeplug", self._new), ("Open codeplug…", self._open),
                              ("Save", self._save), ("Save as…", lambda: self._save(True)),
                              ("Load example", self._example), ("Parker County receive template", self._parker_template)]:
            file_menu.add_command(label=label, command=action)
        menu.add_cascade(label="File", menu=file_menu)
        radio_menu = tk.Menu(menu, tearoff=False)
        for label, action in [("Read radio", self._read), ("Write radio", self._write),
                              ("Find radio", self._detect), ("Check programming tool", self._probe)]:
            radio_menu.add_command(label=label, command=action)
        menu.add_cascade(label="Radio", menu=radio_menu)
        tools = tk.Menu(menu, tearoff=False)
        tools.add_command(label="Advanced source view…", command=self._source_view)
        tools.add_command(label="Firmware installation", command=lambda: self.tabs.select(4))
        menu.add_cascade(label="Tools", menu=tools)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="About / running copy", command=self._about)
        menu.add_cascade(label="Help", menu=help_menu)
        self.root.configure(menu=menu)
        shell = ttk.Frame(self.root)
        shell.pack(fill="both", expand=True)
        title = tk.Frame(shell, bg="#10263c", height=62)
        title.pack(fill="x")
        title.pack_propagate(False)
        tk.Label(title, text="PROJECT DM1701-25  /  DM-1701", bg="#10263c", fg="white", font=("Segoe UI", 18, "bold")).pack(side="left", padx=22)
        tk.Label(title, text="P25  ·  DMR  ·  FM  /  Customer Programming Software", bg="#10263c", fg="#b9d9ea", font=("Segoe UI", 10)).pack(side="left", padx=10)
        tk.Label(title, text=BUILD_LABEL, bg="#10263c", fg="white", font=("Segoe UI", 10, "bold")).pack(side="right", padx=22)
        toolbar = ttk.Frame(shell, padding=(16, 9))
        toolbar.pack(fill="x")
        for text, action, primary in [("New", self._new, False), ("Open", self._open, False),
                                       ("Save", self._save, False), ("Read radio", self._read, True),
                                       ("Write radio", self._write, False), ("Check", self._verify, False)]:
            self._button(toolbar, text, action, primary=primary).pack(side="left", padx=(0, 6))
        ttk.Label(toolbar, textvariable=self.detected_status, style="Muted.TLabel").pack(side="right", padx=12)
        ttk.Separator(shell).pack(fill="x")
        workspace = ttk.Panedwindow(shell, orient="horizontal")
        workspace.pack(fill="both", expand=True, padx=12, pady=12)
        rail = ttk.Frame(workspace, width=235)
        workspace.add(rail, weight=0)
        ttk.Label(rail, text="CODEPLUG EXPLORER", font=("Segoe UI", 9, "bold"), foreground=MUTED).pack(anchor="w", padx=10, pady=(6, 10))
        self.navigation = ttk.Treeview(rail, show="tree", selectmode="browse", style="Nav.Treeview")
        self.navigation.pack(fill="both", expand=True)
        self.navigation.insert("", "end", iid="project", text="Project DM1701-25 codeplug", open=True)
        self.navigation.insert("project", "end", iid="identity", text="Radio identity")
        self.navigation.insert("project", "end", iid="channels", text="Channels")
        self.navigation.insert("project", "end", iid="zones", text="Zones")
        self.navigation.insert("project", "end", iid="scans", text="Scan lists")
        self.navigation.insert("project", "end", iid="contacts", text="Talkgroups / contacts")
        self.navigation.insert("project", "end", iid="settings", text="General settings")
        self.navigation.insert("", "end", iid="device", text="Connected radio", open=True)
        self.navigation.insert("device", "end", iid="connection", text="Read, write & backups")
        self.navigation.insert("device", "end", iid="p25", text="P25 receiver")
        self.navigation.insert("device", "end", iid="firmware", text="Firmware installation")
        self.navigation.bind("<<TreeviewSelect>>", self._navigate)
        ttk.Label(rail, text="DM-1701 / RT84\nProject DM1701-25 receiver\nLocal files stay on this computer", style="Muted.TLabel", justify="left").pack(anchor="w", padx=10, pady=12)
        content = ttk.Frame(workspace, padding=(14, 0, 0, 0))
        workspace.add(content, weight=1)
        page_heading = ttk.Frame(content)
        page_heading.pack(fill="x", pady=(4, 12))
        ttk.Label(page_heading, textvariable=self.page_title, style="Header.TLabel").pack(side="left")
        ttk.Label(page_heading, textvariable=self.project_name, style="Muted.TLabel").pack(side="right", pady=10)
        self.tabs = ttk.Notebook(content, style="Studio.TNotebook", height=480)
        self.tabs.pack(fill="both", expand=True)
        self.channels_page = ttk.Frame(self.tabs, padding=12)
        self.yaml_page = ttk.Frame(self.tabs, padding=12)
        self.radio_page = ttk.Frame(self.tabs, padding=16)
        self.p25_page = ttk.Frame(self.tabs, padding=16)
        self.firmware_page = ttk.Frame(self.tabs, padding=16)
        self.tabs.add(self.channels_page, text="  Channels  ")
        self.tabs.add(self.yaml_page, text="  All settings  ")
        self.tabs.add(self.radio_page, text="  Radio & backups  ")
        self.tabs.add(self.p25_page, text="  P25 lab  ")
        self.tabs.add(self.firmware_page, text="  Firmware  ")
        self._channels_ui()
        self._yaml_ui()
        self._radio_ui()
        self._p25_ui()
        self._firmware_ui()
        self.tabs.bind("<<NotebookTabChanged>>", self._tab_changed)
        self.navigation.selection_set("channels")
        ttk.Separator(shell).pack(fill="x")
        ttk.Label(shell, textvariable=self.status, style="Muted.TLabel", anchor="w", padding=(16, 9), wraplength=1320).pack(fill="x")

    def _navigate(self, _event=None):
        selected = self.navigation.selection()
        if not selected:
            return
        key = selected[0]
        target = {"channels": (0, None), "identity": (1, 0), "settings": (1, 1),
                  "zones": (1, 2), "scans": (1, 3), "contacts": (1, 4),
                  "connection": (2, None), "p25": (3, None), "firmware": (4, None)}.get(key)
        if target:
            self.tabs.select(target[0])
            if target[1] is not None:
                self.settings_tabs.select(target[1])
            self.page_title.set(self.navigation.item(key, "text"))

    def _about(self):
        messagebox.showinfo(f"About {PRODUCT_NAME}", f"{PRODUCT_NAME} {BUILD_LABEL}\n\nRunning from:\n{ROOT}\n\nPython:\n{sys.executable}\n\nThis is an original CPS for the DM-1701. P25 RF reception remains experimental and requires hardware validation.", parent=self.root)

    def _channels_ui(self):
        top = ttk.Frame(self.channels_page)
        top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, text="Add a channel, choose its mode, then set the receive frequency.", style="Muted.TLabel").pack(side="left")
        self.channel_count = tk.StringVar(value="0 CHANNELS")
        ttk.Label(top, textvariable=self.channel_count, foreground=ACCENT, font=("Segoe UI", 10, "bold")).pack(side="right")
        bar = ttk.Frame(self.channels_page)
        bar.pack(fill="x", pady=(0, 8))
        self._button(bar, "Add FM", self._add_channel, primary=True).pack(side="left", padx=(0, 5))
        self._button(bar, "Add DMR", lambda: self._add_mode_channel("DMR")).pack(side="left", padx=(0, 5))
        self._button(bar, "Add P25", self._add_p25_channel).pack(side="left", padx=(0, 5))
        self._button(bar, "Edit", self._edit_channel).pack(side="left", padx=(0, 5))
        self._button(bar, "Remove", self._remove_channel).pack(side="left", padx=(0, 7))
        ttk.Entry(bar, textvariable=self.search, width=20).pack(side="right")
        ttk.Label(bar, text="Search  ", style="Muted.TLabel").pack(side="right")
        self.search.trace_add("write", lambda *_: self._refresh_table())
        columns = ("name", "mode", "rx", "tx", "ro", "contact")
        split = ttk.Frame(self.channels_page)
        split.pack(fill="both", expand=True, pady=(10, 0))
        inspector = ttk.LabelFrame(self.channels_page, text="Selected channel", padding=14)
        inspector.pack(side="bottom", fill="x", pady=(12, 0))
        self.selected_name = tk.StringVar(value="Select a channel")
        self.selected_frequency = tk.StringVar(value="---.-----")
        self.selected_description = tk.StringVar(value="Choose one from your list.")
        self.selected_details = tk.StringVar()
        summary = ttk.Frame(inspector)
        summary.pack(side="left", fill="x", expand=True)
        ttk.Label(summary, textvariable=self.selected_name, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(summary, textvariable=self.selected_description, foreground=ACCENT).pack(anchor="w", pady=(4, 0))
        ttk.Label(summary, textvariable=self.selected_details, style="Muted.TLabel", justify="left", wraplength=700).pack(anchor="w", pady=(6, 0))
        self._button(inspector, "Edit channel", self._edit_channel).pack(side="right", anchor="n")
        frame = ttk.Frame(split)
        frame.pack(fill="both", expand=True)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        self.table = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse", height=7)
        for col, label, width in zip(columns, ["Channel name", "Mode", "Receive MHz", "Transmit MHz", "Receive only", "Access / talkgroup"],
                                      [180, 70, 130, 130, 110, 220]):
            self.table.heading(col, text=label)
            self.table.column(col, width=width, minwidth=40, stretch=col in ("name", "contact"))
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.table.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.table.bind("<Double-1>", lambda _: self._edit_channel())
        self.table.bind("<<TreeviewSelect>>", lambda _: self._inspect_channel())
        ttk.Label(self.channels_page, text="FM and DMR use Read / Write radio. P25 channels are sent to the experimental receiver; choose No filter for an unqualified clear-voice scan.",
                  style="Muted.TLabel", wraplength=1000).pack(anchor="w", pady=(8, 0))

    def _inspect_channel(self):
        selected = self.table.selection()
        row = next((r for r in self.document.channels() if selected and r.id == selected[0]), None)
        if row is None:
            self.selected_name.set("Select a channel")
            self.selected_frequency.set("---.-----")
            self.selected_description.set("Choose one from your list.")
            self.selected_details.set("")
            return
        self.selected_name.set(row.name)
        self.selected_frequency.set(row.rx_frequency.replace(" MHz", ""))
        self.selected_description.set(f"{row.mode}   /   {'LISTEN ONLY' if row.rx_only else 'RX + TX'}")
        details = f"Transmit: {row.tx_frequency}\n\n"
        contact_label = row.contact
        for item in self.document.data.get("contacts", []):
            value = item.get("dmr", {}) if isinstance(item, dict) else {}
            if isinstance(value, dict) and value.get("id") == row.contact:
                contact_label = f"{value.get('name', '')} ({value.get('number', '')})"
        if row.mode == "DMR":
            details += f"Color code: {row.color_code}\nTime slot: {row.time_slot}\n\nTalkgroup: {contact_label}"
        elif row.mode == "P25":
            nac = "ANY" if row.nac == 0xFFFF else f"{row.nac:X}"
            details += f"P25 NAC: {nac}\nTalkgroup: {'ANY' if row.talkgroup == 0 else row.talkgroup}\nScan: {row.scan_mode}\nAudio: {'Yes' if row.audio else 'No'}"
        else:
            details += "Analog voice\n\nEdit tones and bandwidth\nin channel settings."
        self.selected_details.set(details)

    def _yaml_ui(self):
        # Keep one canonical source buffer for the existing semantic YAML
        # round-trip path. Ordinary programming uses the forms below.
        self.editor = ScrolledText(self.yaml_page, undo=True, wrap="none")
        self.settings_tabs = ttk.Notebook(self.yaml_page)
        self.settings_tabs.pack(fill="both", expand=True)
        pages = [ttk.Frame(self.settings_tabs, padding=18) for _ in range(5)]
        for page, title in zip(pages, ["Radio identity", "General", "Zones", "Scan lists", "Talkgroups"]):
            self.settings_tabs.add(page, text=title)
        identity = pages[0]
        ttk.Label(identity, text="Your radio identity", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 18))
        for row, (title, variable) in enumerate([("Name / callsign", self.radio_name), ("Assigned DMR radio ID", self.radio_id)], 1):
            ttk.Label(identity, text=title).grid(row=row, column=0, sticky="w", padx=(0, 24), pady=8)
            ttk.Entry(identity, textvariable=variable, width=28).grid(row=row, column=1, sticky="w", pady=8)
        self._button(identity, "Apply identity", self._identity, primary=True).grid(row=3, column=1, sticky="w", pady=16)
        ttk.Label(identity, text="Your DMR ID identifies you on DMR networks. It is separate from a P25 talkgroup or NAC.", style="Muted.TLabel", wraplength=650).grid(row=4, column=0, columnspan=2, sticky="w")
        self.general_fields = {key: tk.StringVar() for key in ("introLine1", "introLine2", "power", "squelch")}
        general = pages[1]
        ttk.Label(general, text="Everyday radio settings", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 18))
        for row, (key, label) in enumerate([("introLine1", "Startup message — line 1"), ("introLine2", "Startup message — line 2"), ("power", "Default transmit power"), ("squelch", "Analog squelch")], 1):
            ttk.Label(general, text=label).grid(row=row, column=0, sticky="w", padx=(0, 24), pady=8)
            if key in ("power", "squelch"):
                choices = ["Min", "Low", "Mid", "High", "Max"] if key == "power" else [str(x) for x in range(11)]
                control = ttk.Combobox(general, textvariable=self.general_fields[key], values=choices, state="readonly", width=26)
            else:
                control = ttk.Entry(general, textvariable=self.general_fields[key], width=28)
            control.grid(row=row, column=1, sticky="w", pady=8)
        self._button(general, "Apply general settings", self._apply_general, primary=True).grid(row=5, column=1, sticky="w", pady=16)
        self.group_tables = {}
        for page, key, title in [(pages[2], "zones", "zone"), (pages[3], "scanLists", "scan list")]:
            bar = ttk.Frame(page)
            bar.pack(fill="x", pady=(0, 14))
            for label, action in [(f"Add {title}", lambda k=key: self._edit_group(k)), ("Edit", lambda k=key: self._edit_selected_group(k)), ("Remove", lambda k=key: self._remove_group(k))]:
                self._button(bar, label, action).pack(side="left", padx=(0, 6))
            table = ttk.Treeview(page, columns=("name", "members"), show="headings")
            table.heading("name", text=title.capitalize() + " name")
            table.heading("members", text="Channels")
            table.column("name", width=240)
            table.column("members", width=480)
            table.pack(fill="both", expand=True)
            table.bind("<Double-1>", lambda _, k=key: self._edit_selected_group(k))
            self.group_tables[key] = table
            ttk.Label(page, text="Choose channels by name. Existing imported settings are kept when you rename or change the channel selection.", style="Muted.TLabel", wraplength=800).pack(anchor="w", pady=12)
        contact_page = pages[4]
        bar = ttk.Frame(contact_page)
        bar.pack(fill="x", pady=(0, 14))
        self._button(bar, "Add talkgroup", self._add_contact, primary=True).pack(side="left", padx=(0, 6))
        self._button(bar, "Edit talkgroup", self._edit_contact).pack(side="left")
        self.contacts_table = ttk.Treeview(contact_page, columns=("name", "number", "type"), show="headings")
        for key, title in [("name", "Name"), ("number", "Talkgroup / radio ID"), ("type", "Call type")]:
            self.contacts_table.heading(key, text=title)
        self.contacts_table.pack(fill="both", expand=True)
        ttk.Label(contact_page, text="These contacts are for DMR. P25 talkgroup and NAC are set on each P25 channel.", style="Muted.TLabel").pack(anchor="w", pady=12)
        self._button(self.yaml_page, "Advanced source view…", self._source_view).pack(anchor="e", pady=(12, 0))

    def _apply_general(self):
        try:
            self._sync()
            values = {key: var.get().strip() for key, var in self.general_fields.items()}
            if len(values["introLine1"]) > 16 or len(values["introLine2"]) > 16:
                raise ValueError("Startup messages can contain up to 16 characters per line.")
            if values["power"] not in ("Min", "Low", "Mid", "High", "Max"):
                raise ValueError("Choose a transmit power.")
            values["squelch"] = int(values["squelch"])
            if not 0 <= values["squelch"] <= 10:
                raise ValueError("Squelch must be from 0 to 10.")
            self.document.data.setdefault("settings", {}).update(values)
            self._render()
            self.status.set("General settings updated. Save the file or write the radio to keep them.")
        except Exception as exc:
            self._error(exc)

    def _refresh_settings(self):
        settings = self.document.data.get("settings", {})
        if isinstance(settings, dict):
            for key, variable in self.general_fields.items():
                variable.set(str(settings.get(key, {"power": "Low", "squelch": 3}.get(key, ""))))
        names = {row.id: row.name for row in self.document.channels()}
        for key, table in self.group_tables.items():
            table.delete(*table.get_children())
            for entry in self.document.data.get(key, []):
                if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
                    continue
                members = entry.get("A" if key == "zones" else "channels", [])
                table.insert("", "end", iid=entry["id"], values=(entry.get("name", ""), ", ".join(names.get(member, str(member)) for member in members)))
        self.contacts_table.delete(*self.contacts_table.get_children())
        for entry in self.document.data.get("contacts", []):
            value = entry.get("dmr", {}) if isinstance(entry, dict) else {}
            if isinstance(value, dict) and isinstance(value.get("id"), str):
                kind = "Group call" if value.get("type") == "GroupCall" else "Private call" if value.get("type") == "PrivateCall" else str(value.get("type", ""))
                self.contacts_table.insert("", "end", iid=value["id"], values=(value.get("name", ""), value.get("number", ""), kind))

    def _edit_selected_group(self, key):
        selected = self.group_tables[key].selection()
        if selected:
            self._edit_group(key, selected[0])

    def _edit_group(self, key, ident=None):
        self._sync()
        entry = next((x for x in self.document.data.get(key, []) if isinstance(x, dict) and x.get("id") == ident), {})
        dialog = tk.Toplevel(self.root)
        dialog.title("Zone" if key == "zones" else "Scan list")
        dialog.configure(bg=BG)
        dialog.transient(self.root)
        dialog.grab_set()
        body = ttk.Frame(dialog, padding=20)
        body.pack(fill="both", expand=True)
        name = tk.StringVar(value=entry.get("name", "New zone" if key == "zones" else "New scan list"))
        ttk.Label(body, text="Name").pack(anchor="w")
        ttk.Entry(body, textvariable=name, width=48).pack(fill="x", pady=(5, 16))
        ttk.Label(body, text="Channels — hold Ctrl to select more than one").pack(anchor="w")
        choices = tk.Listbox(body, selectmode="extended", exportselection=False, height=16, width=56, bg=PANEL, fg=TEXT, selectbackground="#dceafa", selectforeground=TEXT, relief="solid", borderwidth=1)
        choices.pack(fill="both", expand=True, pady=6)
        channels = self.document.channels()
        members = entry.get("A" if key == "zones" else "channels", [])
        for index, row in enumerate(channels):
            choices.insert("end", f"{row.name}   ·   {row.mode}   ·   {row.rx_frequency}")
            if row.id in members:
                choices.selection_set(index)
        def apply():
            try:
                label = name.get().strip()
                if not label or len(label) > 16:
                    raise ValueError("Use a name from 1 to 16 characters.")
                self._sync()
                entries = self.document.data.setdefault(key, [])
                target = next((x for x in entries if isinstance(x, dict) and x.get("id") == ident), None)
                if target is None:
                    prefix = "zone" if key == "zones" else "scan"
                    used = {x.get("id") for x in entries if isinstance(x, dict)}
                    number = 1
                    while f"{prefix}{number}" in used:
                        number += 1
                    target = {"id": f"{prefix}{number}"}
                    if key == "zones":
                        target["B"] = []
                    entries.append(target)
                target["name"] = label
                target["A" if key == "zones" else "channels"] = [channels[int(index)].id for index in choices.curselection()]
                self._render()
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Channel selection", str(exc), parent=dialog)
        bar = ttk.Frame(body)
        bar.pack(fill="x", pady=(14, 0))
        ttk.Button(bar, text="Cancel", command=dialog.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(bar, text="Apply", command=apply, style="Primary.TButton").pack(side="right")

    def _remove_group(self, key):
        selected = self.group_tables[key].selection()
        if not selected:
            return
        ident = selected[0]
        if key == "scanLists":
            referenced = [row.name for row in self.document.channels() if any(isinstance(raw, dict) and isinstance(raw.get(kind), dict) and raw[kind].get("id") == row.id and raw[kind].get("scanList") == ident for raw in self.document.data.get("channels", []) for kind in ("fm", "dmr", "digital", "p25"))]
            if referenced:
                self._error(ValueError("This scan list is assigned to: " + ", ".join(referenced) + ". Remove those assignments in Advanced source view first."))
                return
        if messagebox.askokcancel("Remove entry", "Remove the selected entry from this codeplug?", parent=self.root):
            self.document.data[key] = [x for x in self.document.data.get(key, []) if not isinstance(x, dict) or x.get("id") != ident]
            self._render()

    def _edit_contact(self):
        selected = self.contacts_table.selection()
        if not selected:
            return
        ident = selected[0]
        value = next((x["dmr"] for x in self.document.data.get("contacts", []) if isinstance(x, dict) and isinstance(x.get("dmr"), dict) and x["dmr"].get("id") == ident), None)
        if value is None:
            return
        number = simpledialog.askinteger("Edit DMR contact", "Talkgroup / radio ID:", initialvalue=value.get("number"), minvalue=1, maxvalue=16777215, parent=self.root)
        if number is None:
            return
        name = simpledialog.askstring("Edit DMR contact", "Contact name:", initialvalue=value.get("name", ""), parent=self.root)
        if name:
            self.document.upsert_contact(number, name, contact_id=ident, type=value.get("type", "GroupCall"))
            self._render()

    def _source_view(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Advanced source view — imported settings")
        dialog.geometry("900x650")
        body = ttk.Frame(dialog, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="For imported or uncommon settings. Ordinary channels, zones, scan lists and identity use the forms in the explorer.", wraplength=820).pack(anchor="w", pady=(0, 10))
        source = ScrolledText(body, wrap="none", undo=True, font=("Consolas", 11))
        source.pack(fill="both", expand=True)
        source.insert("1.0", self.editor.get("1.0", "end-1c"))
        def apply():
            try:
                candidate = Codeplug.loads(source.get("1.0", "end-1c"))
                self.document = candidate
                self._render()
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Source settings", str(exc), parent=dialog)
        self._button(body, "Apply source changes", apply, primary=True).pack(anchor="e", pady=(12, 0))

    def _radio_ui(self):
        page = self.radio_page
        ttk.Label(page, text="Program the connected radio", font=("Helvetica", 17, "bold")).pack(anchor="w")
        ttk.Label(page, text="Stock / OpenGD77: read and write your FM/DMR codeplug. Studio voice firmware: read its receiver status or send the selected P25 receive channel using the native USB connection.",
                  wraplength=1000).pack(anchor="w", pady=(6, 14))
        profile_row = ttk.Frame(page)
        profile_row.pack(fill="x", pady=5)
        ttk.Label(profile_row, text="Installed firmware", width=22).pack(side="left")
        self.profile_picker = ttk.Combobox(profile_row, textvariable=self.profile, state="readonly", values=list(PROFILE_LABELS), width=29)
        self.profile_picker.pack(side="left", padx=6)
        ttk.Label(profile_row, text="Programmer").pack(side="left", padx=(16, 6))
        ttk.Combobox(profile_row, textvariable=self.backend_mode, state="readonly", values=["Automatic", "Native dmrconf", "WSL qdmr"], width=18).pack(side="left")
        row = ttk.Frame(page)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Programming tool path", width=22).pack(side="left")
        ttk.Entry(row, textvariable=self.executable).pack(side="left", fill="x", expand=True, padx=6)
        self._button(row, "Browse...", self._choose_executable).pack(side="left")
        ttk.Label(page, text="Leave blank for automatic native dmrconf, then WSL qdmr on Windows; choose a file only for a known native install.").pack(anchor="w", padx=(165, 0))
        row = ttk.Frame(page)
        row.pack(fill="x", pady=(12, 4))
        ttk.Label(row, text="Codeplug backup folder", width=22).pack(side="left")
        ttk.Entry(row, textvariable=self.backup_dir).pack(side="left", fill="x", expand=True, padx=6)
        self._button(row, "Choose...", self._choose_backups).pack(side="left")
        ttk.Checkbutton(page, text="I have checked that the physical radio is a Baofeng DM-1701 / Retevis RT84.",
                        variable=self.confirm_model).pack(anchor="w", pady=(12, 4))
        ttk.Label(page, text="Select the firmware actually running on the radio. The Studio P25 receiver is detected separately over USB.",
                  wraplength=1000).pack(anchor="w", pady=(0, 12))
        bar = ttk.Frame(page)
        bar.pack(fill="x", pady=6)
        for title, action in [("Check programmer", self._probe), ("Find radio", self._detect),
                              ("Read radio & back up", self._read), ("Check settings", self._verify),
                              ("Export radio file...", self._encode), ("Write to radio...", self._write)]:
            self._button(bar, title, action).pack(side="left", padx=(0, 6))
        ttk.Label(page, text="Every write first reads a binary codeplug and YAML backup. These are NOT full firmware/calibration backups.",
                  foreground="#e9ba76", wraplength=1000).pack(anchor="w", pady=(5, 10))
        self.log = ScrolledText(page, height=12, wrap="word", font=("Menlo", 11), state="disabled",
                               bg=PANEL, fg=TEXT, insertbackground=ACCENT, relief="flat", borderwidth=0, padx=14, pady=14)
        self.log.pack(fill="both", expand=True)
        self._button(page, "Open firmware setup guide", lambda: self._open_document("FIRMWARE.md")).pack(anchor="w", pady=(10, 0))
        self._button(page, "Save operation log...", self._save_log).pack(anchor="w", pady=(8, 0))

    def _p25_ui(self):
        page = self.p25_page
        ttk.Label(page, text="Experimental P25 receiver", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(page, text="The new voice image links P25 frame recovery, speech decoding and radio speaker output. RF reception is unverified. Conventional Phase 1 C4FM, clear voice, receive only; control channels do not carry speech.", wraplength=900, justify="left").pack(anchor="w", pady=(10, 18))
        row = ttk.Frame(page)
        row.pack(anchor="w", pady=5)
        self._button(row, "Install P25 voice firmware", self._install_voice, primary=True).pack(side="left", padx=(0, 8))
        self._button(row, "Read P25 receiver", self._read_p25).pack(side="left")
        tune = ttk.LabelFrame(page, text="Tune the radio", padding=18)
        tune.pack(fill="x", pady=16)
        self.p25_frequency = tk.StringVar(value="443.25000")
        self.p25_nac = tk.StringVar(value="any")
        self.p25_scan_mode = tk.StringVar(value="No filter")
        for label, variable, width in [("Receive MHz", self.p25_frequency, 18), ("NAC (hex or any)", self.p25_nac, 12)]:
            ttk.Label(tune, text=label).pack(side="left", padx=(0, 6))
            ttk.Entry(tune, textvariable=variable, width=width).pack(side="left", padx=(0, 18))
        ttk.Label(tune, text="Admission").pack(side="left", padx=(0, 6))
        ttk.Combobox(tune, textvariable=self.p25_scan_mode,
                     values=["NAC + talkgroup", "NAC only", "No filter"],
                     state="readonly", width=18).pack(side="left", padx=(0, 12))
        self._button(tune, "Start receiving", self._tune_p25, primary=True).pack(side="left", padx=6)
        self._button(tune, "Stop P25", self._stop_p25).pack(side="left", padx=6)
        self._button(page, "Send selected P25 channel", self._send_p25_channel).pack(anchor="w", pady=6)
        ttk.Label(page, text="No filter means NAC=ANY and talkgroup=ANY. The base radio zone scan is requested when available; only clear conventional Phase 1 voice is decoded. Save your CPS file to retain the channel list. Hold # on an FM channel to toggle experimental P25.", wraplength=900, style="Muted.TLabel").pack(anchor="w", pady=10)
        self.p25_status = tk.StringVar(value="Receiver status will appear here after connecting the Studio voice firmware.")
        ttk.Label(page, textvariable=self.p25_status, wraplength=900, justify="left", font=("Consolas", 11)).pack(anchor="w", pady=12)
        self._button(page, "Open firmware instructions", lambda: self._open_document("firmware-voice/README.md")).pack(anchor="w", pady=6)

    def _firmware_ui(self):
        page = self.firmware_page
        ctk.CTkLabel(page, text="Firmware", font=("Helvetica", 28, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(page, text="The software that runs inside your radio.", text_color=MUTED,
                     font=("Helvetica", 12)).pack(anchor="w", pady=(0, 24))
        card = ctk.CTkFrame(page, fg_color=CARD, corner_radius=16)
        card.pack(fill="x")
        ctk.CTkLabel(card, text="DM-1701 / experimental P25 voice receiver", text_color=TEXT,
                     font=("Helvetica", 19, "bold")).pack(anchor="w", padx=24, pady=(24, 10))
        ctk.CTkLabel(card, text="COMPLETE APPLICATION IMAGE / RF RECEPTION UNVERIFIED", text_color="#815b13",
                     fg_color=INPUT, corner_radius=8, padx=12, height=30,
                     font=("Helvetica", 10, "bold")).pack(anchor="w", padx=24, pady=(0, 14))
        ctk.CTkLabel(card, text="Includes the P25 frame decoder, fixed-point IMBE speech decoder, automatic\n"
                     "C6000 mapping search, speaker stream, and new professional radio home screen.\n\n"
                     "P25 is receive-only. FM/DMR remain available in the base firmware.\n"
                     "The installer selects the matching image and verifies its hash.\n"
                     "It replaces the current application; keep your backup and restore files.", justify="left", text_color=MUTED,
                     font=("Helvetica", 12)).pack(anchor="w", padx=24, pady=(0, 20))
        self._button(card, "Install P25 voice firmware...", self._install_voice, primary=True).pack(anchor="w", padx=24, pady=(0, 24))
        row = ttk.Frame(page)
        row.pack(anchor="w", pady=20)
        self._button(row, "Firmware & recovery guide", lambda: self._open_document("FIRMWARE.md")).pack(side="left", padx=(0, 10))
        self._button(row, "Read development status", lambda: self._open_document("P25-RESEARCH.md")).pack(side="left")
        self._button(page, "Voice firmware instructions", lambda: self._open_document("firmware-voice/README.md")).pack(anchor="w", pady=10)
        ttk.Checkbutton(page, text="Detect my radio automatically", variable=self.auto_detect).pack(anchor="w", pady=10)

    def _install_voice(self):
        image = ROOT / "firmware-voice/PROJECT-DM1701-25-P25-EXPERIMENTAL.bin"
        if not image.is_file():
            image = ROOT / "firmware-voice/DM1701-P25-VOICE-EXPERIMENTAL.bin"
        if not image.is_file():
            self._error(ValueError("The voice firmware image is missing from this copy. Install the complete 0.3 package."))
            return
        self.auto_detect.set(False)
        python = Path(sys.executable)
        if python.name.casefold() == "pythonw.exe":
            python = python.with_name("python.exe")
        if sys.platform == "win32":
            def install():
                with _USB_LOCK:
                    # Launch the product's bundled installer directly.  The
                    # Project DM1701-25 package intentionally does not ship the old
                    # Studio-era collection of command runners.
                    process = subprocess.Popen([str(python), str(ROOT / "firmware-voice/install.py")], cwd=ROOT,
                                               creationflags=subprocess.CREATE_NEW_CONSOLE)
                    code = process.wait()
                if code:
                    raise RuntimeError(f"Voice installer stopped with code {code}; read the messages in its console.")
                return "Voice installer completed. Reconnect the radio in normal mode, then read its P25 receiver status."
            self._work("Install experimental P25 voice firmware", install)
        elif sys.platform == "darwin":
            # The firmware installer is intentionally interactive (it asks
            # for the explicit INSTALL P25 confirmation).  Open it in a
            # visible Terminal window from the standalone macOS app.
            command = " ".join((shlex.quote(str(python)), shlex.quote(str(ROOT / "firmware-voice/install.py"))))
            script = f"tell application \"Terminal\" to do script {json.dumps(command)}"
            subprocess.Popen(["/usr/bin/osascript", "-e", script])
        else:
            messagebox.showinfo("Voice firmware installer", f"Run in a terminal:\n{python} {ROOT / 'firmware-voice/install.py'}", parent=self.root)

    def _voice_action(self, arguments, title):
        python = Path(sys.executable)
        if python.name.casefold() == "pythonw.exe":
            python = python.with_name("python.exe")
        def run():
            with _USB_LOCK:
                result = subprocess.run([str(python), str(ROOT / "firmware-voice/radio.py"), *arguments],
                    cwd=ROOT, capture_output=True, text=True, timeout=15,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if result.returncode:
                raise BackendError(result.stderr.strip() or result.stdout.strip())
            return result.stdout
        def show(result):
            data = json.loads(result)
            if data.get("request_accepted"):
                self.p25_status.set(f"Receive profile sent: {data['requested_rx_hz'] / 1e6:.5f} MHz, NAC {data['requested_nac']}.\nClick Read P25 receiver for the radio's current state.")
            else:
                self.p25_status.set("\n".join(f"{key.replace('_', ' ').title()}: {value}" for key, value in data.items()))
            self.tabs.select(3)
            self.page_title.set("P25 receiver")
        self._work(title, run, show)

    def _read_p25(self):
        self._voice_action(["--status"], "Read active P25 receiver")

    def _tune_p25(self):
        scan = self.p25_scan_mode.get().strip() or "No filter"
        self._voice_action(["--frequency", self.p25_frequency.get().strip(), "--nac", self.p25_nac.get().strip(),
                            "--scan-mode", scan, "--enable", "yes"], "Send P25 receive profile")

    def _stop_p25(self):
        self._voice_action(["--enable", "no"], "Stop P25 receiver")

    def _send_p25_channel(self):
        try:
            self._sync()
            channel = self._selected()
            if channel is None or channel.mode != "P25":
                raise ValueError("Select a P25 channel on Channels first.")
            self.p25_frequency.set(str(frequency_mhz(channel.rx_frequency)))
            self.p25_nac.set("any" if channel.nac == 0xFFFF else f"{channel.nac:03X}")
            self.p25_scan_mode.set(channel.scan_mode)
            self._tune_p25()
        except Exception as exc:
            self._error(exc)

    def _install_lab(self):
        if not messagebox.askokcancel("Experimental firmware installation",
            "This installs the DM-1701 capture-lab image. It replaces the current firmware and provides no P25 voice yet.\n\n"
            "Make a full flash/calibration backup and read the capture-lab guide first. The installer will open in a separate window and check the image/model. Continue?", parent=self.root):
            return
        if sys.platform == "win32":
            python = Path(sys.executable)
            if python.name.casefold() == "pythonw.exe":
                python = python.with_name("python.exe")
            self.auto_detect.set(False)
            self.detected_status.set("Firmware installer active. Automatic detection paused.")
            def install():
                with _USB_LOCK:
                    process = subprocess.Popen([str(python), str(ROOT / "firmware-lab/install.py")], cwd=ROOT,
                                                creationflags=subprocess.CREATE_NEW_CONSOLE)
                    code = process.wait()
                if code:
                    raise RuntimeError(f"The firmware installer stopped with code {code}. Review its console output before retrying.")
                return "Installer completed. Automatic detection remains paused; enable it when the radio is running normally."
            self._work("Install capture-lab firmware", install)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", "Terminal", str(ROOT / "Install-Capture-Lab.command")])
        else:
            messagebox.showinfo("Installer", f"Run in a terminal:\n{sys.executable} {ROOT / 'firmware-lab/install.py'}", parent=self.root)

    def _capture_lab(self):
        if not messagebox.askokcancel("Receive-data capture",
            "The capture-lab image must already be installed. Select an FM channel at the test frequency and turn scanning and receiver battery saving off.\n\n"
            "This records 10 seconds of raw modem RAM, blocks transmitting until the radio is restarted, and does not decode P25 voice. Continue?", parent=self.root):
            return
        name = filedialog.asksaveasfilename(defaultextension=".jsonl", filetypes=[("Radio test data", "*.jsonl")])
        if not name:
            return
        def run():
            python = Path(sys.executable)
            if python.name.casefold() == "pythonw.exe":
                python = python.with_name("python.exe")
            with _USB_LOCK:
                result = subprocess.run([str(python), str(ROOT / "firmware-lab/capture.py"), "--seconds", "10", "--output", name,
                    "--acknowledge-experimental"], capture_output=True, text=True, timeout=45,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            diagnostics = Path(name).with_suffix(".diagnostics.txt")
            diagnostics.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
            if result.returncode not in (0, 1) or "Traceback" in result.stderr:
                raise RuntimeError(f"{result.stderr or result.stdout or 'Capture failed.'}\nDiagnostics saved: {diagnostics}")
            return f"{result.stdout}\nSaved test results: {name}\nDiagnostics: {diagnostics}"
        self._work("Capture raw receive data", run, lambda result: messagebox.showinfo("Test saved", str(result), parent=self.root))

    def _speech_test(self, known):
        arguments=['--known'] if known else []
        if not known:
            source=filedialog.askopenfilename(title="Select demodulated packed P25 bits",filetypes=[("P25 bits","*.p25bits *.bin"),("All files","*")])
            if not source:
                return
            arguments=['--input',source]
        python=Path(sys.executable)
        if python.name.casefold()=='pythonw.exe':
            python=python.with_name('python.exe')
        def run():
            result=subprocess.run([str(python),str(ROOT/'firmware-p25/voice/speech_test.py'),*arguments,'--play'],
                capture_output=True,text=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            if result.returncode:
                raise RuntimeError(result.stderr or result.stdout)
            return result.stdout
        self._work('Desktop P25 speech test',run,lambda result: messagebox.showinfo('PC speech test',str(result),parent=self.root))

    def _open_document(self, relative):
        path = ROOT / relative
        if not path.exists():
            messagebox.showinfo("Documentation", f"See {relative} in the downloaded source bundle.", parent=self.root)
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif os.name == "nt":
            os.startfile(path)
        else:
            try:
                subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except FileNotFoundError:
                messagebox.showinfo("Location", str(path), parent=self.root)

    def _set_editor(self, text):
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", text)
        self.editor.edit_modified(False)

    def _render(self):
        self._set_editor(self.document.dumps())
        ids = self.document.data.get("radioIDs", [])
        candidates = [entry["dmr"] for entry in ids if isinstance(entry, dict) and isinstance(entry.get("dmr"), dict)] if isinstance(ids, list) else []
        settings = self.document.data.get("settings", {})
        default_id = settings.get("defaultID") if isinstance(settings, dict) else None
        if candidates:
            item = next((entry for entry in candidates if entry.get("id") == default_id), candidates[0])
            self.radio_id.set(str(item.get("number", "")))
            self.radio_name.set(str(item.get("name", "My radio")))
        else:
            self.radio_id.set("")
        self._refresh_table()
        self.root.title(f"{PRODUCT_NAME} - {self.path.name if self.path else 'Untitled'}")

    def _refresh_table(self):
        if not hasattr(self, "table"):
            return
        self.table.delete(*self.table.get_children())
        query = self.search.get().casefold()
        contacts = {}
        for item in self.document.data.get("contacts", []) if isinstance(self.document.data.get("contacts", []), list) else []:
            value = item.get("dmr", {}) if isinstance(item, dict) else {}
            if isinstance(value, dict) and isinstance(value.get("id"), str):
                contacts[value["id"]] = f"{value.get('name', '')} ({value.get('number', '')})"
        try:
            rows = self.document.channels()
            self.channel_count.set(f"{len(rows)} CHANNELS")
            for row in rows:
                if query and query not in f"{row.name} {row.mode} {row.rx_frequency} {row.contact}".casefold():
                    continue
                access = (f"CC {row.color_code} / {row.time_slot} / {contacts.get(row.contact, row.contact)}" if row.mode == "DMR"
                          else f"NAC {row.nac:03X} / TG {row.talkgroup}" if row.mode == "P25" else row.bandwidth)
                self.table.insert("", "end", iid=row.id, values=(row.name, row.mode, row.rx_frequency,
                                  row.tx_frequency, "Yes" if row.rx_only else "No", access))
            self._inspect_channel()
        except Exception as exc:
            self.status.set(f"Channel view: {exc}. Review All radio settings.")

    def _sync(self):
        candidate = Codeplug.loads(self.editor.get("1.0", "end-1c"))
        self.document = candidate
        return candidate

    def _tab_changed(self, _event=None):
        if self.tabs.select():
            selected = self.tabs.index(self.tabs.select())
            self.page_title.set(["Channels", "Radio settings", "Read, write & backups", "P25 receiver", "Firmware installation"][selected])
        if self.busy:
            return
        try:
            self._sync()
            self._refresh_table()
        except Exception as exc:
            self.status.set(f"YAML needs attention: {exc}")

    def _apply_yaml(self):
        try:
            self._sync()
            errors = self.document.validate()
            self._render()
            if errors:
                messagebox.showwarning("Codeplug checks", "\n".join(errors), parent=self.root)
                self.status.set(f"{len(errors)} issue(s) need attention before programming.")
            else:
                self.status.set("Local codeplug checks passed.")
        except Exception as exc:
            self._error(exc)

    def _can_replace(self):
        if self.busy:
            return False
        current = self.editor.get("1.0", "end-1c").strip()
        if current == Codeplug.new().dumps().strip() and self.path is None:
            return True
        return messagebox.askokcancel("Replace current document?", "Open another document? Save current edits first if needed.", parent=self.root)

    def _new(self):
        if self._can_replace():
            self.document, self.path = Codeplug.new(), None
            self._render()

    def _open(self):
        if not self._can_replace():
            return
        name = filedialog.askopenfilename(filetypes=[("qdmr YAML", "*.yaml *.yml"), ("All files", "*")])
        if name:
            self._load_path(Path(name))

    def _load_path(self, path, detach=False):
        try:
            document = Codeplug.load(path)
            self.document, self.path = document, None if detach else Path(path)
            self._render()
            self.status.set(f"Opened {path}")
        except Exception as exc:
            self._error(exc)

    def _example(self):
        if self._can_replace():
            self._load_path(ROOT / "examples" / "demo.yaml")
            self.path = None
            self.status.set("Receive-only example loaded. Save a copy and enter your own DMR ID.")
            self._render()

    def _parker_template(self):
        if self._can_replace():
            self.document, self.path = Codeplug.parker_county(), None
            self._render()
            self.status.set("Parker County receive-only P25 template loaded. Save a copy before editing.")

    def _save(self, save_as=False):
        if self.busy:
            return False
        try:
            self._sync()
            path = self.path
            if path is None or save_as:
                name = filedialog.asksaveasfilename(defaultextension=".yaml", filetypes=[("qdmr YAML", "*.yaml")])
                if not name:
                    return False
                path = Path(name)
            self.document.save(path)
            self.path = path
            self.editor.edit_modified(False)
            self.root.title(f"{PRODUCT_NAME} - {path.name}")
            self.status.set(f"Saved {path}")
            return True
        except Exception as exc:
            self._error(exc)
            return False

    def _identity(self):
        try:
            self._sync()
            self.document.set_radio_id(int(self.radio_id.get()), self.radio_name.get().strip())
            self._render()
            self.status.set("Radio identity updated in the document.")
        except Exception as exc:
            self._error(exc)

    def _selected(self):
        selected = self.table.selection()
        if not selected:
            self.status.set("Select a channel first.")
            return None
        return next((r for r in self.document.channels() if r.id == selected[0]), None)

    def _add_channel(self):
        try:
            self._sync()
            ChannelDialog(self)
        except Exception as exc:
            self._error(exc)

    def _add_p25_channel(self):
        try:
            self._sync()
            ChannelDialog(self, preset="P25")
        except Exception as exc:
            self._error(exc)

    def _edit_channel(self):
        if self.busy:
            return
        try:
            self._sync()
            row = self._selected()
            if row:
                ChannelDialog(self, row)
        except Exception as exc:
            self._error(exc)

    def _remove_channel(self):
        try:
            self._sync()
            row = self._selected()
            if row and messagebox.askokcancel("Remove channel", f"Remove {row.name}? Referenced channels must first be removed from their zones and scan lists in Full codeplug.", parent=self.root):
                self.document.remove_channel(row.id)
                self._render()
        except Exception as exc:
            self._error(exc)

    def _add_contact(self):
        try:
            self._sync()
            number = simpledialog.askinteger("DMR contact", "Talkgroup number (1-16777215):", minvalue=1,
                                            maxvalue=16777215, parent=self.root)
            if number is None:
                return
            name = simpledialog.askstring("DMR contact", "Contact name:", initialvalue=f"TG {number}", parent=self.root)
            if name:
                self.document.upsert_contact(number, name)
                self._render()
        except Exception as exc:
            self._error(exc)

    def _choose_executable(self):
        path = filedialog.askopenfilename(title="Choose dmrconf executable")
        if path:
            self.executable.set(path)

    def _choose_backups(self):
        path = filedialog.askdirectory(title="Codeplug backup folder")
        if path:
            self.backup_dir.set(path)

    def _backend(self):
        mode = {"Automatic": "auto", "Native dmrconf": "native", "WSL qdmr": "wsl"}[self.backend_mode.get()]
        return _Programmer(self.executable.get().strip() or None, mode)

    def _discover(self):
        """Read-only background discovery; never reads/writes a codeplug."""
        if self.auto_detect.get() and not self.busy and not self.discovering:
            configured = self.executable.get().strip() or None
            mode = {"Automatic": "auto", "Native dmrconf": "native", "WSL qdmr": "wsl"}[self.backend_mode.get()]
            self.discovering = True
            def task():
                try:
                    native = native_lab_port()
                    if native:
                        self.discovery_queue.put((True, (None, f"Studio / RadioFoundry USB ({native})")))
                    else:
                        key = (configured, mode)
                        if not self.discovery_backend or self.discovery_backend[0] != key:
                            self.discovery_backend = (key, create_backend(configured, timeout=8, mode=mode))
                        self.discovery_queue.put((True, self.discovery_backend[1].identify()))
                except Exception as exc:
                    self.discovery_queue.put((False, str(exc)))
            threading.Thread(target=task, daemon=True).start()
        self.root.after(4000, self._discover)

    def _get_profile(self, usb=False):
        if self.profile.get() not in PROFILE_LABELS:
            raise ValueError("Choose the firmware actually installed on your radio in the top-right menu.")
        if usb and not self.confirm_model.get():
            raise ValueError("Confirm the physical radio model in Radio & backups before USB access.")
        return PROFILE_LABELS[self.profile.get()]

    def _log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", str(text).rstrip() + "\n\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _save_log(self):
        name = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Operation log", "*.txt")])
        if name:
            try:
                Path(name).write_text(self.log.get("1.0", "end-1c"), encoding="utf-8")
                self.status.set(f"Operation log saved: {name}")
            except OSError as exc:
                self._error(exc)

    def _work(self, title, operation, on_success=None):
        if self.busy:
            return
        self.busy = True
        for widget in self.operation_widgets:
            widget.configure(state="disabled")
        self.editor.configure(state="disabled")
        self.profile_picker.configure(state="disabled")
        self.status.set(f"{title}...")
        self._log(title)

        def task():
            try:
                result = operation()
                self.result_queue.put((True, result, on_success, title))
            except Exception as exc:
                self.result_queue.put((False, exc, None, title))
        threading.Thread(target=task, daemon=True).start()

    def _poll(self):
        try:
            found, result = self.discovery_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            self.discovering = False
            if found:
                profile, name = result
                self.detected_status.set(f"Radio connected: {name}")
                if profile is not None and self.profile.get() not in PROFILE_LABELS:
                    self.profile.set(next(label for label, key in PROFILE_LABELS.items() if key == profile))
            else:
                self.detected_status.set("Radio: not detected - check power, USB cable and programming-tool setup")
        try:
            ok, result, callback, title = self.result_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            for widget in self.operation_widgets:
                widget.configure(state="normal")
            self.editor.configure(state="normal")
            self.profile_picker.configure(state="readonly")
            if ok:
                self._log(getattr(result, "log", str(result)))
                self.status.set(f"{title} completed.")
                if callback:
                    try:
                        callback(result)
                    except Exception as exc:
                        self._error(exc)
            else:
                self._log(f"FAILED: {result}")
                self._error(result)
        self.root.after(100, self._poll)

    def _probe(self):
        try:
            backend = self._backend()
            self._work("Check dmrconf", backend.probe)
        except Exception as exc:
            self._error(exc)

    def _detect(self):
        try:
            if native_lab_port():
                self._read_p25()
                return
            profile, backend = self._get_profile(usb=True), self._backend()
            self._work("Detect radio", lambda: backend.detect(profile))
        except Exception as exc:
            self._error(exc)

    def _read(self):
        try:
            if native_lab_port():
                self._read_p25()
                return
            if not self._can_replace():
                return
            profile, backend = self._get_profile(usb=True), self._backend()
            folder = Path(self.backup_dir.get()).expanduser()
            self._work("Read and back up codeplug", lambda: backend.read(folder, profile),
                       lambda result: self._load_path(result.yaml_path, detach=True))
        except Exception as exc:
            self._error(exc)

    def _validated_snapshot(self):
        import tempfile
        self._sync()
        errors = self.document.validate()
        if errors:
            raise ValueError("Fix these codeplug issues first:\n" + "\n".join(errors))
        # A private temporary folder gives the worker a stable document even if the UI changes.
        folder = tempfile.TemporaryDirectory(prefix="dm1701-")
        path = Path(folder.name) / "codeplug.yaml"
        self.document.save(path)
        return folder, path

    def _verify(self):
        try:
            if any(row.mode == "P25" for row in self.document.channels()):
                self._sync()
                issues = self.document.validate()
                if issues:
                    raise ValueError("\n".join(issues))
                self.status.set("Local channel checks passed. Send a P25 receive channel from the P25 receiver page.")
                return
            profile, backend = self._get_profile(), self._backend()
            folder, path = self._validated_snapshot()
            def task():
                try:
                    return backend.verify(path, profile)
                finally:
                    folder.cleanup()
            self._work("Verify with dmrconf", task)
        except Exception as exc:
            self._error(exc)

    def _encode(self):
        try:
            profile, backend = self._get_profile(), self._backend()
            name = filedialog.asksaveasfilename(defaultextension=".dfu", filetypes=[("qdmr binary codeplug", "*.dfu")])
            if not name:
                return
            folder, path = self._validated_snapshot()
            def task():
                try:
                    return backend.encode(path, Path(name), profile)
                finally:
                    folder.cleanup()
            self._work("Encode binary codeplug", task)
        except Exception as exc:
            self._error(exc)

    def _write(self):
        try:
            if native_lab_port():
                self._send_p25_channel()
                return
            profile, backend = self._get_profile(usb=True), self._backend()
            folder, path = self._validated_snapshot()
            backup_dir = Path(self.backup_dir.get()).expanduser()
            if not messagebox.askokcancel("Back up and write codeplug?",
                f"Write DMR/FM settings to the connected {self.profile.get()} radio?\n\n"
                f"First, dmrconf must successfully save binary and YAML codeplug backups in:\n{backup_dir}\n\n"
                "Keep the same radio connected throughout. This changes its programming; it does not install firmware.", parent=self.root):
                folder.cleanup()
                return
            def task():
                try:
                    return backend.write(path, backup_dir, profile)
                finally:
                    folder.cleanup()
            self._work("Back up and write codeplug", task,
                       lambda result: self._log(f"Backup retained at {result.backup.yaml_path.parent}"))
        except Exception as exc:
            self._error(exc)

    def _error(self, error):
        self.status.set(str(error).splitlines()[0])
        messagebox.showerror(PRODUCT_NAME, str(error), parent=self.root)

    def _close(self):
        if self.busy:
            messagebox.showinfo("Operation running", "Wait for the current operation to finish before closing.", parent=self.root)
            return
        if messagebox.askokcancel(f"Close {PRODUCT_NAME}", "Close the app? Save current edits first if needed.", parent=self.root):
            self.root.destroy()


class ChannelDialog:
    """Edit common channel fields while preserving unsupported imported settings."""

    @staticmethod
    def _tone_display(value):
        if value is None:
            return ""
        if isinstance(value, dict) and set(value) == {"ctcss"}:
            return str(value["ctcss"]).removesuffix(" Hz").strip()
        return "[preserve existing tone]"

    @staticmethod
    def _ctcss(text):
        """Convert an explicitly changed form value to qdmr's tone mapping."""
        from decimal import Decimal, InvalidOperation
        text = text.strip()
        if not text:
            return None
        try:
            value = Decimal(text.removesuffix(" Hz").strip())
        except InvalidOperation as exc:
            raise ValueError("FM tone must be a CTCSS frequency in Hz, or blank to disable.") from exc
        if not value.is_finite() or not Decimal("67") <= value <= Decimal("254.1"):
            raise ValueError("CTCSS frequency must be between 67 and 254.1 Hz.")
        return {"ctcss": f"{value:f} Hz"}

    def __init__(self, studio, channel=None, preset=None):
        self.studio, self.channel = studio, channel
        if channel and channel.mode not in ("FM", "DMR", "P25"):
            raise ValueError("This channel mode cannot be edited by the channel form.")
        self.original = {}
        if channel:
            for raw in studio.document.data.get("channels", []):
                for kind in ("fm", "dmr", "digital", "p25"):
                    value = raw.get(kind, {}) if isinstance(raw, dict) else {}
                    if isinstance(value, dict) and value.get("id") == channel.id:
                        self.original = value
                        break
        self.window = tk.Toplevel(studio.root)
        self.window.configure(bg=BG)
        self.window.title("Edit channel" if channel else "Add channel")
        self.window.transient(studio.root)
        self.window.grab_set()
        self.fields = {}
        body = ttk.Frame(self.window, padding=18)
        body.pack(fill="both", expand=True)
        defaults = {"name": "New channel", "mode": preset or "FM", "rx_frequency": "145.50000", "tx_frequency": "145.50000",
                    "power": "Low", "color_code": "1", "time_slot": "TS1", "contact": "tg9", "bandwidth": "Narrow",
                    "rx_tone": "", "tx_tone": "", "nac": "293", "talkgroup": "1", "audio": "1", "promiscuous": "0",
                    "scan_mode": "NAC + talkgroup"}
        if channel:
            for key in defaults:
                if key not in ("rx_tone", "tx_tone", "power", "bandwidth") and hasattr(channel, key) and getattr(channel, key) is not None:
                    defaults[key] = str(getattr(channel, key))
            for form_key, yaml_key in (("rx_tone", "rxTone"), ("tx_tone", "txTone")):
                defaults[form_key] = self._tone_display(self.original.get(yaml_key))
            for key in ("bandwidth", "power"):
                current = self.original.get(key)
                defaults[key] = current if isinstance(current, str) else "[preserve inherited setting]"
            for key in ("nac", "talkgroup", "audio", "promiscuous", "scan_mode"):
                if key in self.original:
                    defaults[key] = str(self.original[key])
            if isinstance(self.original.get("nac"), int):
                defaults["nac"] = "ANY" if self.original["nac"] == 0xFFFF else f"{self.original['nac']:03X}"
        self.initial = dict(defaults)
        contact_ids = []
        self.contact_choices = {}
        for item in studio.document.data.get("contacts", []):
            value = item.get("dmr", item) if isinstance(item, dict) else {}
            if isinstance(value, dict) and "id" in value:
                label = f"{value.get('name', 'Contact')} ({value.get('number', '')})"
                if label in self.contact_choices:
                    label += f" [{value['id']}]"
                self.contact_choices[label] = value["id"]
                contact_ids.append(label)
                if defaults["contact"] == value["id"]:
                    defaults["contact"] = label
        if defaults["mode"] == "P25":
            defaults["mode"] = "P25 (experimental)"
        defaults["audio"] = "Yes" if str(defaults["audio"]).casefold() in ("1", "true", "yes") else "No"
        defaults["promiscuous"] = "Yes" if str(defaults["promiscuous"]).casefold() in ("1", "true", "yes") else "No"
        choices = {"mode": ["FM", "DMR", "P25 (experimental)"], "power": ["Min", "Low", "Mid", "High", "Max"], "time_slot": ["TS1", "TS2"],
                   "bandwidth": ["Narrow", "Wide"], "contact": contact_ids, "audio": ["Yes", "No"],
                   "promiscuous": ["Yes", "No"], "scan_mode": ["NAC + talkgroup", "NAC only", "No filter"]}
        # Imported !default values and radio-specific enums must survive an unrelated edit.
        for key, values in choices.items():
            if defaults[key] not in values:
                values.append(defaults[key])
        labels = [("name", "Name (up to 16 characters)"), ("mode", "Mode"), ("rx_frequency", "Receive MHz"),
                  ("tx_frequency", "Transmit MHz"), ("power", "Power"), ("bandwidth", "FM bandwidth"),
                  ("rx_tone", "FM RX CTCSS Hz (blank = off)"), ("tx_tone", "FM TX CTCSS Hz (blank = off)"),
                  ("color_code", "DMR color code (0-15)"), ("time_slot", "DMR time slot"), ("contact", "Talkgroup / contact"),
                  ("nac", "P25 NAC (hex or ANY)"), ("talkgroup", "P25 talkgroup (0 = any)"), ("scan_mode", "P25 scan admission"),
                  ("audio", "P25 speaker audio"), ("promiscuous", "Legacy promiscuous flag")]
        self.field_rows = {}
        for index, (key, label) in enumerate(labels):
            label_widget = ttk.Label(body, text=label)
            label_widget.grid(row=index, column=0, sticky="w", padx=(0, 15), pady=5)
            var = tk.StringVar(value=defaults[key])
            self.fields[key] = var
            if key in choices:
                widget = ttk.Combobox(body, textvariable=var, values=choices[key], state="readonly", width=24)
            else:
                widget = ttk.Entry(body, textvariable=var, width=27)
            widget.grid(row=index, column=1, sticky="ew", pady=5)
            self.field_rows[key] = (label_widget, widget)
        self.fields["mode"].trace_add("write", lambda *_: self._mode_changed())
        self.rx_only = tk.BooleanVar(value=channel.rx_only if channel else True)
        self.rx_only_control = ttk.Checkbutton(body, text="Receive only (disable transmit)", variable=self.rx_only)
        self.rx_only_control.grid(row=len(labels), columnspan=2, sticky="w", pady=10)
        ttk.Label(body, text="P25 uses Send selected P25 channel in P25 receiver. The experimental voice image receives clear Phase 1 C4FM; its RF path is unverified. Talkgroup/audio options are retained in the project; this image currently receives all clear talkgroups.",
                  wraplength=440).grid(row=len(labels)+1, columnspan=2, sticky="w", pady=5)
        bar = ttk.Frame(body)
        bar.grid(row=len(labels)+2, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(bar, text="Cancel", command=self.window.destroy).pack(side="left", padx=6)
        ttk.Button(bar, text="Apply channel", command=self._apply).pack(side="left")
        self._mode_changed()

    def _mode_changed(self):
        mode = self.fields["mode"].get()
        if mode == "P25 (experimental)":
            mode = "P25"
        groups = {
            "FM": {"bandwidth", "rx_tone", "tx_tone"},
            "DMR": {"color_code", "time_slot", "contact"},
            "P25": {"nac", "talkgroup", "scan_mode", "audio", "promiscuous"},
        }
        visible = groups.get(mode, set()) | {"name", "mode", "rx_frequency"}
        if mode != "P25":
            visible |= {"tx_frequency", "power"}
        if mode == "P25":
            self.rx_only.set(True)
        self.rx_only_control.configure(state="disabled" if mode == "P25" else "normal")
        for key, (label, widget) in self.field_rows.items():
            if key in visible:
                label.grid(); widget.grid()
            else:
                label.grid_remove(); widget.grid_remove()

    def _apply(self):
        try:
            fields = {key: var.get().strip() for key, var in self.fields.items()}
            if fields["mode"] == "P25 (experimental)":
                fields["mode"] = "P25"
            fields["audio"] = fields["audio"] == "Yes"
            fields["promiscuous"] = fields["promiscuous"] == "Yes"
            fields["contact"] = self.contact_choices.get(fields["contact"], fields["contact"])
            fields["rx_only"] = self.rx_only.get()
            if fields["mode"] == "P25" and fields["scan_mode"] == "No filter":
                fields["nac"] = "ANY"
                fields["talkgroup"] = "0"
            if not 1 <= len(fields["name"]) <= 16:
                raise ValueError("Channel name must contain 1-16 characters.")
            for key in ("power", "bandwidth"):
                if self.channel and fields[key] == self.initial[key]:
                    fields.pop(key)
            for form_key in ("rx_tone", "tx_tone"):
                if self.channel and fields[form_key] == self.initial[form_key]:
                    fields.pop(form_key)
                elif fields["mode"] == "FM":
                    fields[form_key] = self._ctcss(fields[form_key])
                else:
                    fields.pop(form_key)
            # Keep the live document intact when a form fails validation.
            candidate = Codeplug(self.studio.document.data)
            before = set(candidate.validate())
            ident = candidate.upsert_channel(fields, self.channel.id if self.channel else None)
            issues = [error for error in candidate.validate()
                      if (error not in before or error.startswith(f"Channel {ident}:"))
                      and "Set your assigned DMR radio ID" not in error]
            if issues:
                raise ValueError("\n".join(issues))
            self.studio.document = candidate
            self.studio._render()
            self.window.destroy()
        except Exception as exc:
            messagebox.showerror("Channel settings", str(exc), parent=self.window)


def main():
    root = tk.Tk()
    Studio(root)
    root.mainloop()


if __name__ == "__main__":
    main()
