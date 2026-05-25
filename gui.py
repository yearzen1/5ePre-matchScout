import json
import os
import sys
import threading
import customtkinter as ctk
from scout import Scout, STATUS_MAP

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(_BASE_DIR, "scout_config.json")
DEFAULT_CONFIG = {
    "client_path": "",
    "cdp_port": 9222,
    "my_nickname": "",
    "steam_path": "",
}

STATUS_COLORS = {
    "0": "#1a4a1a",
    "-2": "#3a1a3a",
    "-4": "#4a1a1a",
    "-5": "#3a3a1a",
    "-6": "#4a1a1a",
    "-7": "#4a1a1a",
    "-8": "#3a3a1a",
}


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("5E 赛前侦察器")
        self.geometry("950x800")
        self.minsize(800, 600)

        icon_path = os.path.join(_BASE_DIR, "app.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        self.config = self._load_config()
        self.player_data = []

        self._setup_ui()
        self._set_status("运行中", "#66DD66")
        self._auto_start()

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return {**DEFAULT_CONFIG, **json.load(f)}
            except Exception:
                pass
        return DEFAULT_CONFIG.copy()

    def _save_config(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        self._build_title_bar()
        self._build_table_area()
        self._build_log_area()

    def _build_title_bar(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            frame, text="5E 赛前侦察器",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=(12, 0), pady=8, sticky="w")

        right_frame = ctk.CTkFrame(frame, fg_color="transparent")
        right_frame.grid(row=0, column=1, padx=(0, 12), sticky="e")

        ctk.CTkButton(
            right_frame, text="设置", command=self._open_settings,
            width=60, height=26, font=ctk.CTkFont(size=12),
        ).pack(side="right", padx=(6, 0))

        self.status_dot = ctk.CTkLabel(
            right_frame, text="●", font=ctk.CTkFont(size=16), text_color="gray"
        )
        self.status_dot.pack(side="right", padx=(0, 4))

        self.status_label = ctk.CTkLabel(
            right_frame, text="", font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(side="right")

    def _build_table_area(self):
        self.table_frame = ctk.CTkFrame(self)
        self.table_frame.grid(row=1, column=0, padx=10, pady=(8, 0), sticky="nsew")
        self.table_frame.grid_columnconfigure(0, weight=1)
        self.table_frame.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=(4, 0))

        cols = [
            ("队伍", 50, "center"),
            ("玩家", 130, "w"),
            ("Lv", 30, "center"),
            ("ELO", 55, "center"),
            ("Rt", 45, "center"),
            ("ADR", 50, "center"),
            ("RWS", 45, "center"),
            ("场次", 50, "center"),
            ("胜率", 50, "center"),
            ("爆头", 50, "center"),
            ("Imp", 45, "center"),
            ("状态", 70, "center"),
        ]

        for i, (text, width, anchor) in enumerate(cols):
            header_frame.grid_columnconfigure(i, minsize=width, weight=0)
            ctk.CTkLabel(
                header_frame, text=text, width=width,
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor=anchor,
            ).grid(row=0, column=i, padx=1, pady=2)

        self._col_spec = cols
        self.table_canvas = ctk.CTkScrollableFrame(self.table_frame)
        self.table_canvas.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 4))

        self.empty_label = ctk.CTkLabel(
            self.table_canvas, text="等待比赛匹配...",
            font=ctk.CTkFont(size=14), text_color="gray",
        )
        self.empty_label.pack(expand=True, fill="both", pady=60)

    def _build_log_area(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=2, column=0, padx=10, pady=(8, 10), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            frame, text="日志", font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(4, 0))

        self.log_text = ctk.CTkTextbox(frame, height=160, wrap="word", state="disabled")
        self.log_text.grid(row=1, column=0, sticky="ew", padx=6, pady=(2, 6))

    def _auto_start(self):
        scout = Scout(
            on_log=self._on_log,
            on_match_found=self._on_match_found,
            client_path=self.config.get("client_path") or None,
            my_nickname=self.config.get("my_nickname") or None,
            steam_path=self.config.get("steam_path") or None,
        )
        threading.Thread(target=scout.start, daemon=True).start()

    def _on_log(self, msg):
        self.after(0, lambda: self._append_log(msg))

    def _on_match_found(self, players):
        self.after(0, lambda: self._update_table(players))

    _MAX_LOG_LINES = 1000

    def _append_log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > self._MAX_LOG_LINES:
            self.log_text.delete("1.0", f"{lines - self._MAX_LOG_LINES}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _update_table(self, players):
        self.player_data = players
        self._clear_table()
        for player in players:
            self._add_player_row(player)

    def _clear_table(self):
        for w in self.table_canvas.winfo_children():
            w.destroy()

    def _add_player_row(self, player):
        status = player.get("account_status", "?")
        bg = STATUS_COLORS.get(status, "#252525")

        row = ctk.CTkFrame(self.table_canvas, fg_color=bg, corner_radius=4)
        row.pack(fill="x", padx=1, pady=1)

        team_text = player["team"].upper()
        if player["is_me"]:
            team_text = "★我"

        row_data = [
            team_text,
            player["nickname"],
            str(player["level"]),
            str(player["elo"]),
            f"{player['rating']:.2f}",
            str(player["adr"]),
            str(player["rws"]),
            str(player["match_total"]),
            f"{player['win_rate'] * 100:.0f}%",
            f"{player['headshot_rate'] * 100:.0f}%",
            f"{player['impact']:.1f}",
            player["account_status_label"],
        ]

        for i, (val, (_, width, anchor)) in enumerate(zip(row_data, self._col_spec)):
            text_color = None
            if i == len(row_data) - 1:
                if player["account_status"] == "0":
                    text_color = "#66DD66"
                elif player["account_status"] in ("-4", "-6", "-7"):
                    text_color = "#FF6666"
                elif player["account_status"] in ("-5", "-8"):
                    text_color = "#DDDD66"
                elif player["account_status"] == "-2":
                    text_color = "#CC66CC"
            if i == 0 and player["is_me"]:
                text_color = "#66DDFF"

            ctk.CTkLabel(
                row, text=val, width=width, anchor=anchor,
                text_color=text_color,
            ).grid(row=0, column=i, padx=1, pady=2)

    def _set_status(self, text, color):
        self.status_label.configure(text=text)
        self.status_dot.configure(text_color=color)

    def _open_settings(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("设置")
        dialog.geometry("480x340")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="5E 客户端路径",
            font=ctk.CTkFont(size=13),
            anchor="w",
        ).pack(padx=20, pady=(16, 2), fill="x")

        path_var = ctk.StringVar(value=self.config.get("client_path", ""))
        ctk.CTkEntry(dialog, textvariable=path_var, width=400).pack(padx=20, pady=(0, 2))

        ctk.CTkLabel(
            dialog, text="我的 5E 昵称（用于在表格中标记自己，留空则不标记）",
            font=ctk.CTkFont(size=13),
            anchor="w",
        ).pack(padx=20, pady=(10, 2), fill="x")

        nick_var = ctk.StringVar(value=self.config.get("my_nickname", ""))
        ctk.CTkEntry(dialog, textvariable=nick_var, width=400, placeholder_text="例如: MyPlayerName").pack(padx=20, pady=(0, 2))

        ctk.CTkLabel(
            dialog, text="Steam 路径（留空则仅警告不启动 Steam）",
            font=ctk.CTkFont(size=13),
            anchor="w",
        ).pack(padx=20, pady=(10, 2), fill="x")

        steam_var = ctk.StringVar(value=self.config.get("steam_path", ""))
        ctk.CTkEntry(dialog, textvariable=steam_var, width=400).pack(padx=20, pady=(0, 2))

        ctk.CTkLabel(
            dialog, text="⚠ 修改设置后需重启程序生效",
            font=ctk.CTkFont(size=11), text_color="gray",
        ).pack(padx=20, pady=(2, 0), anchor="w")

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=14)

        def save():
            self.config["client_path"] = path_var.get()
            self.config["my_nickname"] = nick_var.get().strip()
            self.config["steam_path"] = steam_var.get()
            self._save_config()
            dialog.destroy()

        ctk.CTkButton(btn_frame, text="保存", command=save, width=90).pack(side="left", padx=6)


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    app = App()
    app.mainloop()
