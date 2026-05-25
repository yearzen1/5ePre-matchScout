import struct
import json
import sys
import base64
import datetime
import urllib.request
import urllib.parse
import threading
import time

import os
import ctypes
import websocket as ws_lib

if sys.stdout:
    sys.stdout.reconfigure(encoding='utf-8')

API_SEARCH = "https://arena.5eplay.com/api/search/player/1/16"
API_ID_TRANSFER = "https://gate.5eplay.com/userinterface/http/v1/userinterface/idTransfer"
API_PLAYER_HOME = "https://gate.5eplay.com/crane/http/api/data/player/home"
API_USER_HEADER = "https://gate.5eplay.com/userinterface/pt/v1/userinterface/header"

ID_TRANSFER_HEADERS = {
    "accept": "*/*",
    "content-type": "application/json",
    "x-ca-key": "5eplay",
    "x-ca-signature": "pm/c+nYSScWXLOYG7WCczBallQAPFsQ+mu3szgvr7xg=",
    "x-ca-signature-headers": "Accept-Language,Authorization",
    "x-ca-signature-method": "HmacSHA256",
    "Accept-Language": "zh-cn",
    "authorization": "",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

MSG_CODES = {39583794: "GAME_CTX"}
STATUS_MAP = {"0": "正常", "-2": "非法", "-4": "作弊", "-5": "关联", "-6": "违规", "-7": "恶意", "-8": "风险"}


def ts():
    return datetime.datetime.now().strftime("%H:%M:%S")


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def http_post(url, headers, body):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def get_nickname(uuid: str) -> str:
    data = http_get(f"{API_USER_HEADER}/{uuid}")
    ud = data.get("data", {}).get("header", {}).get("user_data", {})
    return ud.get("nickname") or ud.get("username") or "?"


def get_uuid_from_nickname(nickname: str) -> str | None:
    players = http_get(f"{API_SEARCH}?keywords={urllib.parse.quote(nickname)}")
    if players.get("success"):
        lst = players.get("data", {}).get("user", {}).get("list", [])
        for p in lst:
            if p.get("username") == nickname:
                domain = p.get("domain", "")
                if domain:
                    resp = http_post(API_ID_TRANSFER, ID_TRANSFER_HEADERS, {"trans": {"domain": domain}})
                    return resp.get("data", {}).get("uuid")
    return None


def get_season_stats(uuid: str) -> dict:
    data = http_get(f"{API_PLAYER_HOME}?uuid={uuid}")
    return data.get("data", {})


def scout_player(nickname: str, uuid: str | None = None) -> dict:
    result = {"nickname": nickname, "uuid": uuid, "seasons": {}, "account": {}}
    if not uuid:
        return result
    home = get_season_stats(uuid)
    result["seasons"] = home.get("season_data", {})
    user_data = http_get(f"{API_USER_HEADER}/{uuid}")
    ud = user_data.get("data", {}).get("header", {}).get("user_data", {})
    result["account"] = {
        "status": ud.get("account_status", "?"),
        "credit_score": ud.get("credit_score", "?"),
        "reg_date": ud.get("reg_date", "?"),
    }
    return result


def decode_comet_frame(data: bytes) -> tuple:
    if len(data) < 12:
        return None, {}, 0
    magic, total_len, seq, msg_code = struct.unpack("!IHHI", data[:12])
    body = {}
    if len(data) > 12:
        try:
            body = json.loads(data[12:].decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {"_raw": data[12:].hex()}
    return msg_code, body, seq


def format_player_short(stats: dict) -> str:
    nickname = stats.get("nickname", "?")
    seasons = stats.get("seasons", {})
    account = stats.get("account", {})
    if not seasons:
        return f"{nickname}: 未找到赛季数据"
    now = list(seasons.values())[-1]
    name = now.get("name", "?")
    elo = now.get("elo", 0)
    rating = now.get("rating", 0)
    adr = now.get("adr", 0)
    rws = now.get("rws", 0)
    match_total = now.get("match_total", 0)
    win_total = now.get("win_match_total", 0)
    per_win = now.get("per_win_match", 0)
    per_hs = now.get("per_headshot", 0)
    impact = now.get("impact", 0)
    level_id = now.get("level_id", 0)
    acct_status = STATUS_MAP.get(account.get("status", "?"), account.get("status", "?"))
    return (f"{nickname} [{name}] Lv{level_id} | ELO:{elo} Rtg:{rating} ADR:{adr} RWS:{rws} | "
            f"场次:{match_total} 胜:{win_total}({per_win*100:.0f}%) 爆头:{per_hs*100:.0f}% Impact:{impact} | "
            f"账号:{acct_status} 信誉:{account.get('credit_score','?')}")


def extract_player_data(nickname: str, uuid: str, team: str, is_me: bool, stats: dict) -> dict:
    seasons = stats.get("seasons", {})
    account = stats.get("account", {})
    now = list(seasons.values())[-1] if seasons else {}
    return {
        "nickname": nickname,
        "uuid": uuid,
        "team": team,
        "is_me": is_me,
        "level": now.get("level_id", 0),
        "season_name": now.get("name", "?"),
        "elo": now.get("elo", 0),
        "rating": now.get("rating", 0),
        "adr": now.get("adr", 0),
        "rws": now.get("rws", 0),
        "match_total": now.get("match_total", 0),
        "win_total": now.get("win_match_total", 0),
        "win_rate": now.get("per_win_match", 0),
        "headshot_rate": now.get("per_headshot", 0),
        "impact": now.get("impact", 0),
        "account_status": account.get("status", "?"),
        "account_status_label": STATUS_MAP.get(account.get("status", "?"), account.get("status", "?")),
        "credit_score": account.get("credit_score", "?"),
        "reg_date": account.get("reg_date", "?"),
    }


class Scout:
    def __init__(self, on_log=None, on_match_found=None, on_stopped=None, client_path=None, my_nickname=None, steam_path=None):
        self.on_log = on_log or (lambda msg: None)
        self.on_match_found = on_match_found or (lambda players: None)
        self.on_stopped = on_stopped or (lambda: None)
        self.client_path = client_path if client_path else None
        self.steam_path = steam_path if steam_path else None
        self.my_uuid = None
        self.my_nickname = my_nickname
        self.running = False
        self.seen_games = set()
        self._ws = None
        self._seen_codes = set()

    def _log(self, msg):
        self.on_log(f"[{ts()}] {msg}")

    def _get_cdp_page(self):
        resp = urllib.request.urlopen("http://localhost:9222/json", timeout=5)
        pages = json.loads(resp.read().decode())
        for p in pages:
            url = p.get("url", "")
            if "view-arena" in url or "5eplay" in url:
                return p["webSocketDebuggerUrl"]
        return pages[0]["webSocketDebuggerUrl"] if pages else None

    def _on_cdp_message(self, ws, message: str):
        try:
            msg = json.loads(message)
        except json.JSONDecodeError:
            return
        if "method" not in msg:
            return
        params = msg.get("params", {})
        if msg["method"] == "Network.webSocketFrameReceived":
            response = params.get("response", {})
            payload_data = response.get("payloadData", "")
            opcode = response.get("opcode", 0)
            if opcode == 2:
                try:
                    raw = base64.b64decode(payload_data)
                except Exception:
                    raw = payload_data.encode("latin-1")
                msg_code, body, seq = decode_comet_frame(raw)
                if msg_code is None or msg_code == 0:
                    return
                if msg_code == 39583794 or msg_code == 42205234:
                    self._handle_game_ctx(body)
                # elif msg_code not in self._seen_codes:
                #     self._seen_codes.add(msg_code)
                #     self._log(f"[探索] 未知消息 code={msg_code} keys={list(body.keys())[:20]} size={len(str(body))}")

    def _on_cdp_open(self, ws):
        self._log("已连接 5E 客户端，等待匹配...")
        ws.send(json.dumps({"id": 1, "method": "Network.enable"}))

    def _on_cdp_error(self, ws, error):
        self._log(f"CDP 错误: {error}")

    def _on_cdp_close(self, ws, code, msg):
        self._log("CDP 断开")
        if self.running:
            self._log("3秒后重连...")
            time.sleep(3)
            if self.running:
                self._start_ws()

    def _handle_game_ctx(self, body: dict):
        game_ctx = body.get("game_ctx", {})
        gmi = game_ctx.get("gmi", {})
        game_id = game_ctx.get("id", "?")
        status = game_ctx.get("status", -1)

        if status < 1 or game_id in self.seen_games:
            return
        self.seen_games.add(game_id)
        self._log(f"比赛已匹配! ID: {game_id}")
        self._log("开始获取玩家数据...")

        all_players = []
        for team_name in ("t1", "t2"):
            team = gmi.get(team_name, {})
            for room in team.get("rooms", []):
                for member in room.get("members", []):
                    all_players.append((team_name, member))

        self._log(f"共 {len(all_players)} 名玩家")
        player_list = []
        for team_name, uid in all_players:
            try:
                nickname = get_nickname(uid)
                is_me = bool(self.my_uuid) and uid == self.my_uuid
                if is_me:
                    self._log(f"  [{team_name}] {uid[:8]}... -> {nickname} (我)")
                else:
                    self._log(f"  [{team_name}] {uid[:8]}... -> {nickname}")
                stats = scout_player(nickname, uid)
                player_data = extract_player_data(nickname, uid, team_name, is_me, stats)
                player_list.append(player_data)
                self._log(format_player_short(stats))
                time.sleep(0.5)
            except Exception as e:
                self._log(f"  [{team_name}] {uid[:8]}... 获取失败: {e}")
                player_list.append({
                    "nickname": "?", "uuid": uid, "team": team_name, "is_me": False,
                    "level": 0, "season_name": "?", "elo": 0, "rating": 0, "adr": 0,
                    "rws": 0, "match_total": 0, "win_total": 0, "win_rate": 0,
                    "headshot_rate": 0, "impact": 0, "account_status": "?",
                    "account_status_label": "获取失败", "credit_score": "?", "reg_date": "?",
                })

        self._log("侦察完成!")
        if self.on_match_found:
            self.on_match_found(player_list)

    def _ensure_steam_running(self):
        if not self.steam_path:
            self._log("Steam 路径未配置，跳过自动启动 Steam")
            return
        self._log("正在启动 Steam...")
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", self.steam_path, "", None, 1
        )
        if ret <= 32:
            self._log(f"Steam 启动失败，错误码: {ret}")
            return
        self._log("等待 5 秒确保 Steam 就绪...")
        time.sleep(5)

    def _start_ws(self):
        if not self.running:
            return
        for _ in range(3):
            if not self.running:
                return
            try:
                url = self._get_cdp_page()
                if url:
                    break
            except Exception:
                time.sleep(1)
        else:
            if not self.running:
                return
            if not self.client_path and not self.steam_path:
                self._log("5E 客户端路径和 Steam 路径均未配置，请在设置中填写")
                self.running = False
                self.on_stopped()
                return
            if not self.client_path:
                self._log("未配置 5E 客户端路径，请在设置中填写")
                self.running = False
                self.on_stopped()
                return
            if not self.steam_path:
                self._log("未配置 Steam 路径，请在设置中填写（若 Steam 已在运行可忽略）")
            else:
                self._ensure_steam_running()
            self._log("请手动关闭已运行的 5E 客户端，程序将自动启动调试模式...")
            if not self.running:
                return
            self._log("启动 5E 客户端（调试模式）...")
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", self.client_path,
                "--remote-debugging-port=9222 --remote-allow-origins=*", None, 1
            )
            if ret <= 32:
                self._log(f"启动失败，错误码: {ret}")
                self.running = False
                self.on_stopped()
                return
            for _ in range(30):
                if not self.running:
                    return
                try:
                    url = self._get_cdp_page()
                    if url:
                        break
                except Exception:
                    time.sleep(2)
            else:
                if not self.running:
                    return
                self._log("无法连接到 5E 客户端")
                self.running = False
                self.on_stopped()
                return

        if not self.running:
            return
        self._log("5E 侦察器启动")
        ws = ws_lib.WebSocketApp(
            url,
            on_message=self._on_cdp_message,
            on_open=self._on_cdp_open,
            on_error=self._on_cdp_error,
            on_close=self._on_cdp_close,
        )
        self._ws = ws
        ws.run_forever()

    def start(self):
        self.running = True
        if self.my_nickname and not self.my_uuid:
            self._log(f"正在解析昵称 '{self.my_nickname}' ...")
            try:
                uuid = get_uuid_from_nickname(self.my_nickname)
                if uuid:
                    self.my_uuid = uuid
                    self._log(f"识别到自己的 UUID: {uuid}")
                else:
                    self._log('未能解析自己的 UUID，将不标记"我"')
            except Exception as e:
                self._log(f"解析昵称失败: {e}")
        elif self.my_uuid:
            self._log(f"我的 UUID: {self.my_uuid}")
        self._start_ws()

    def stop(self):
        self.running = False
        ws = self._ws
        self._ws = None
        if ws:
            threading.Thread(target=ws.close, args=(1000, "", 1), daemon=True).start()

    def is_running(self):
        return self.running


def main():
    scout = Scout(on_log=lambda msg: print(msg, flush=True))
    try:
        scout.start()
    except KeyboardInterrupt:
        print("\n退出", flush=True)


if __name__ == "__main__":
    main()
