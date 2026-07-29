#!/usr/bin/env python3
"""
BDGWIN BOT - Dual Bet Auto Prediction Engine
Works with bdgwin79.com - Same backend as JAI Club
Features:
- WinGo 30sec/1min/3min/5min/10min
- 5 Number Prediction (higher accuracy)
- Martingale Auto Bet
- Trend Statistics API
- Clean UI with Profit/Loss in Rs
"""

from __future__ import annotations

import base64
from collections import Counter
import getpass
import hashlib
import io
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from PIL import Image, ImageFilter, ImageOps
except ImportError:
    print("Install: pip install requests urllib3 pillow")
    raise

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  STYLES
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

def col(text: str, tone: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{tone}{text}{Style.RESET}"

def rule(char: str = "=", length: int = 60) -> str:
    return char * length

def fmt_money(value: Any) -> str:
    try:
        return f"Rs {float(value):,.2f}"
    except:
        return str(value)

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  GAME CONSTANTS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
GAME_CODES = {
    "1": "WinGo_30S",
    "2": "WinGo_1M",
    "3": "WinGo_3M",
    "4": "WinGo_5M",
    "5": "WinGo_10M"
}

GREEN_NUMS = {1, 3, 5, 7, 9}
RED_NUMS = {0, 2, 4, 6, 8}
VIOLET_NUMS = {0, 5}

def number_size(n: int) -> str:
    return "Big" if n >= 5 else "Small"

def number_color(n: int) -> str:
    if n in VIOLET_NUMS:
        return "Violet"
    return "Green" if n in GREEN_NUMS else "Red"

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  BDGWIN ACCOUNT CHECKER
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class BDGWinAccountChecker:
    def __init__(self, username: str, password: str):
        self.username = username.strip()
        self.password = password.strip()
        self.base_url = "https://bdgwin79.com"
        self.api_base_url = "https://api.bdg88zf.com"
        self.lottery_api_base_url = "https://h5.ar-lottery01.com"
        self.lottery_draw_base_url = "https://draw.ar-lottery06.com"
        self.client = requests.Session()
        self.timeout = 25
        self.verify_ssl = False
        self.jwt_token: str | None = None
        self.ar_token: str | None = None
        self.auth_token_candidates: list[str] = []
        self.user_info: dict[str, Any] = {}
        self.status = "unknown"
        self.message = ""

    def update_headers(self) -> None:
        self.client.headers.update({
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Mobile Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "X-Requested-With": "XMLHttpRequest",
        })

    def generate_signature(self, params_dict: dict[str, Any]) -> str:
        language = params_dict.get("language", 0)
        random_val = params_dict.get("random", "")
        param_str = f'{{"language":{language},"random":"{random_val}"}}'
        return hashlib.md5(param_str.encode()).hexdigest().upper()

    def generate_login_signature(self, params: dict[str, Any]) -> str:
        sig_fields = ["username", "captchaId", "pwd", "phonetype", "logintype", "deviceId", "language", "random"]
        filtered_params = {k: params[k] for k in sig_fields if k in params}
        parts = []
        for key in sorted(filtered_params.keys()):
            value = filtered_params[key]
            if isinstance(value, int):
                parts.append(f'"{key}":{value}')
            else:
                parts.append(f'"{key}":"{value}"')
        return hashlib.md5(("{" + ",".join(parts) + "}").encode()).hexdigest().upper()

    def generate_ar_signature_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        signed_payload = dict(payload)
        signed_payload["random"] = random.randint(100000000000, 999999999999)
        sign_params = {}
        for key in sorted(signed_payload.keys()):
            value = signed_payload[key]
            if key in {"signature"} or value is None or value == "":
                continue
            if isinstance(value, (dict, list)):
                continue
            sign_params[key] = 0 if value == 0 else value
        sign_str = json.dumps(sign_params, separators=(",", ":"), sort_keys=True)
        signed_payload["signature"] = hashlib.md5(sign_str.encode()).hexdigest().upper()
        signed_payload["timestamp"] = int(time.time())
        return signed_payload

    def parse_json_response(self, response: requests.Response, api_name: str) -> dict[str, Any]:
        body = response.text.strip()
        if not body:
            raise RuntimeError(f"{api_name} empty response")
        try:
            return response.json()
        except ValueError:
            raise RuntimeError(f"{api_name} non-JSON response")

    def post_api(self, endpoint: str, payload: dict[str, Any]) -> requests.Response:
        try:
            return self.client.post(
                f"{self.api_base_url}{endpoint}",
                json=payload, timeout=self.timeout, verify=self.verify_ssl,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"API connection failed: {exc}")

    def base64_to_image(self, b64_str: str) -> Image.Image | None:
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        try:
            img_data = base64.b64decode(b64_str)
            return Image.open(io.BytesIO(img_data)).convert("RGBA")
        except Exception:
            return None

    def extract_slider_piece(self, slider: Image.Image):
        alpha = slider.getchannel("A")
        bbox = alpha.point(lambda px: 255 if px > 15 else 0).getbbox()
        if bbox is None:
            return None, None
        piece = slider.crop(bbox)
        piece_mask = alpha.crop(bbox).point(lambda px: 255 if px > 15 else 0)
        return piece, piece_mask

    def build_edge_map(self, image: Image.Image) -> Image.Image:
        gray = ImageOps.grayscale(image)
        gray = gray.filter(ImageFilter.GaussianBlur(radius=1))
        edges = gray.filter(ImageFilter.FIND_EDGES)
        return ImageOps.autocontrast(edges)

    def solve_captcha_image(self, bg_b64: str, slider_b64: str) -> float | None:
        bg = self.base64_to_image(bg_b64)
        slider = self.base64_to_image(slider_b64)
        if bg is None or slider is None:
            return None
        slider_piece, slider_mask = self.extract_slider_piece(slider)
        if slider_piece is None or slider_mask is None:
            return None
        bg_edges = self.build_edge_map(bg)
        slider_edges = self.build_edge_map(slider_piece)
        if bg_edges.width <= 0 or slider_edges.width <= 0:
            return 0
        best_score = float("inf")
        best_x = 0
        max_x = bg_edges.width - slider_edges.width
        for offset_x in range(0, max_x + 1):
            bg_crop = bg_edges.crop((offset_x, 0, offset_x + slider_edges.width, slider_edges.height))
            score = sum(
                abs(bg_crop.load()[x, y] - slider_edges.load()[x, y])
                for y in range(0, slider_edges.height, 2)
                for x in range(0, slider_edges.width, 2)
                if slider_mask.load()[x, y] > 0
            )
            if score < best_score:
                best_score = score
                best_x = offset_x
        return best_x * (340.0 / bg_edges.width)

    def generate_track(self, target_x: float) -> list[dict[str, int]]:
        tracks = []
        current_t = 100
        tracks.append({"x": 10, "y": -2, "t": current_t})
        for index in range(40):
            progress = index / 40
            factor = 1 - (1 - progress) * (1 - progress)
            new_x = int(10 + (target_x - 10) * factor + random.randint(-1, 1))
            current_t += 20 + random.randint(-5, 5)
            tracks.append({"x": new_x, "y": random.randint(-2, 2), "t": current_t})
        for _ in range(5):
            current_t += 30
            tracks.append({"x": int(target_x), "y": random.randint(-1, 1), "t": current_t})
        return tracks

    def get_captcha(self) -> dict[str, Any] | None:
        for retry in range(5):
            random_val = f"{int(time.time())}{random.randint(100000, 999999)}"
            signature = self.generate_signature({"language": 0, "random": random_val})
            payload = {"signature": signature, "language": 0, "random": random_val, "timestamp": int(time.time())}
            try:
                self.update_headers()
                response = self.post_api("/api/webapi/Captcha", payload)
                if response.status_code == 200:
                    data = self.parse_json_response(response, "Captcha")
                    if data.get("code") == 0:
                        return data.get("data") or {}
                time.sleep(2)
            except Exception:
                time.sleep(2)
        return None

    def perform_login(self) -> bool:
        for attempt in range(5):
            if attempt > 0:
                time.sleep(random.uniform(3, 6))
            captcha_data = self.get_captcha()
            if not captcha_data:
                continue
            target_x = self.solve_captcha_image(captcha_data.get("backgroundImage", ""), captcha_data.get("sliderImage", ""))
            if target_x is None:
                continue
            time.sleep(random.uniform(1.0, 2.5))
            random_val = hashlib.md5(f"{time.time()}{random.randint(100000, 999999)}".encode()).hexdigest()
            device_id = hashlib.md5(f"device_{time.time()}_{random.random()}".encode()).hexdigest()
            username_to_use = f"91{self.username}" if len(self.username) == 10 and self.username.isdigit() else self.username
            
            login_params = {
                "username": username_to_use,
                "captchaId": captcha_data["captchaId"],
                "pwd": self.password,
                "phonetype": 1,
                "logintype": "mobile",
                "deviceId": device_id,
                "language": 0,
                "random": random_val,
            }
            payload = {
                **login_params,
                "track": {
                    "backgroundImageWidth": 340,
                    "backgroundImageHeight": 212,
                    "sliderImageWidth": 68,
                    "sliderImageHeight": 212,
                    "startTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.414Z"),
                    "endTime": (datetime.now(timezone.utc) + timedelta(seconds=2)).strftime("%Y-%m-%dT%H:%M:%S.880Z"),
                    "tracks": self.generate_track(target_x),
                },
                "packId": "",
                "signature": self.generate_login_signature(login_params),
                "timestamp": int(time.time()),
            }
            try:
                self.update_headers()
                response = self.post_api("/api/webapi/Login", payload)
                if response.status_code != 200:
                    continue
                data = self.parse_json_response(response, "Login")
                if data.get("code") == 0:
                    login_data = data.get("data", {})
                    self.jwt_token = login_data.get("token")
                    if not self.jwt_token:
                        continue
                    self.status = "active"
                    self.message = "Login successful"
                    return True
                self.message = data.get("msg") or "Login failed"
                return False
            except Exception as exc:
                self.message = f"Login error: {exc}"
                continue
        return False

    def fetch_user_info(self) -> dict[str, Any]:
        if not self.jwt_token:
            return {}
        self.update_headers()
        self.client.headers["Authorization"] = f"Bearer {self.jwt_token}"
        random_val = hashlib.md5(f"{time.time()}{random.randint(100000, 999999)}".encode()).hexdigest()
        payload = {"signature": self.generate_signature({"language": 0, "random": random_val}), "language": 0, "random": random_val, "timestamp": int(time.time())}
        try:
            response = self.post_api("/api/webapi/GetUserInfo", payload)
            if response.status_code == 200:
                data = self.parse_json_response(response, "GetUserInfo")
                if data.get("code") == 0:
                    self.user_info = data["data"]
        except Exception:
            pass
        return self.user_info

    def fetch_ar_token(self, game_code="WinGo_30S"):
        time.sleep(2)  # Rate limit protection
        payload = {
            "gameCode": game_code,
            "vendorCode": "ARLottery",
            "returnUrl": self.base_url,
            "deviceType": 1,
        }
        signed_payload = self.generate_ar_signature_payload(payload)
        self.update_headers()
        if self.jwt_token:
            self.client.headers["Authorization"] = f"Bearer {self.jwt_token}"
        try:
            response = self.post_api("/api/webapi/GetGameUrl", signed_payload)
            data = self.parse_json_response(response, "GetGameUrl")
            if data.get("code") == 0:
                launch_url = data.get("data", {}).get("url") if isinstance(data.get("data"), dict) else data.get("data")
                if launch_url:
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(launch_url or "")
                    query = parse_qs(parsed.query)
                    token = (query.get("Token") or query.get("token") or [""])[0]
                    if token:
                        self.ar_token = token
                        return {"token": token, "url": launch_url}
            else:
                print(f"[!] GetGameUrl: {data.get('msg')}")
        except Exception as e:
            print(f"[!] GetGameUrl error: {e}")
        raise RuntimeError("Could not fetch AR token")

    def place_wingo_bet(self, issue_number, amount, bet_multiple, bet_content, game_code="WinGo_30S"):
        payload = {
            "gameCode": game_code,
            "issueNumber": issue_number,
            "amount": amount,
            "betMultiple": bet_multiple,
            "betContent": bet_content,
            "language": "en",
        }
        signed_payload = self.generate_ar_signature_payload(payload)
        self.update_headers()
        # Use AR token for lottery API
        token_to_use = self.ar_token or self.jwt_token
        if token_to_use:
            token = token_to_use.strip()
            self.client.headers["Authorization"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"
        response = self.client.post(
            f"{self.lottery_api_base_url}/api/Lottery/WinGoBet",
            json=signed_payload, timeout=self.timeout, verify=self.verify_ssl,
        )
        data = self.parse_json_response(response, "WinGoBet")
        if response.status_code != 200 or data.get("code") != 0:
            raise RuntimeError(data.get("msg") or "WinGoBet failed")
        return data

    def close(self):
        self.client.close()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  PREDICTION ENGINE
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def predict_bs(pattern):
    if len(pattern) < 2:
        return "BIG", "DEFAULT"
    b = pattern.count("B")
    s = pattern.count("S")
    if b >= 5: return "SMALL", "5X REVERSAL"
    if s >= 5: return "BIG", "5X REVERSAL"
    if b >= 4: return "SMALL", "4X REVERSAL"
    if s >= 4: return "BIG", "4X REVERSAL"
    if pattern[-3:] == ["B", "B", "B"]: return "BIG", "3X TREND"
    if pattern[-3:] == ["S", "S", "S"]: return "SMALL", "3X TREND"
    if pattern[-2:] == ["B", "B"]: return "BIG", "2X TREND"
    if pattern[-2:] == ["S", "S"]: return "SMALL", "2X TREND"
    if b > s: return "BIG", "COUNT"
    elif s > b: return "SMALL", "COUNT"
    else: return "BIG", "TIE"

def predict_color(pattern):
    if len(pattern) < 2:
        return "RED", "DEFAULT"
    r = pattern.count("R")
    g = pattern.count("G")
    if r >= 5: return "GREEN", "5X REVERSAL"
    if g >= 5: return "RED", "5X REVERSAL"
    if r >= 4: return "GREEN", "4X REVERSAL"
    if g >= 4: return "RED", "4X REVERSAL"
    if pattern[-3:] == ["R", "R", "R"]: return "RED", "3X TREND"
    if pattern[-3:] == ["G", "G", "G"]: return "GREEN", "3X TREND"
    if pattern[-2:] == ["R", "R"]: return "RED", "2X TREND"
    if pattern[-2:] == ["G", "G"]: return "GREEN", "2X TREND"
    if r > g: return "RED", "COUNT"
    elif g > r: return "GREEN", "COUNT"
    else: return "RED", "TIE"


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  LEVEL CALCULATOR
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def make_levels(balance, start_total, multiplier):
    levels = []
    per_market = max(1, math.ceil(start_total / 2))
    risk = 0
    lvl = 1
    while True:
        total = per_market * 2
        if risk + total > balance:
            break
        risk += total
        levels.append({
            "level": lvl, "color_bet": per_market, "bs_bet": per_market,
            "total_bet": total, "cumulative_risk": risk
        })
        nxt = math.ceil(per_market * multiplier)
        if nxt <= per_market: nxt = per_market + 1
        per_market = nxt
        lvl += 1
        if lvl > 50: break
    return levels


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  AUTO BET ENGINE
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class BDGWinAutoBetEngine:
    def __init__(self, username, password, game_code, total_bet, multiplier, confidence_pct):
        self.username = username
        self.password = password
        self.game_code = game_code
        self.start_total_bet = total_bet
        self.multiplier = multiplier
        self.confidence_pct = confidence_pct
        self.checker = BDGWinAccountChecker(username, password)
        self.running = False
        self.start_balance = 0.0
        self.current_balance = 0.0
        self.net_profit = 0.0
        self.levels = []
        self.current_level = 0
        self.win = 0
        self.loss = 0
        self.break_even = 0
        self.double_win = 0
        self.double_loss = 0
        self.pending = None
        self.last_seen_period = None
        self.history = []
        self.stopped = False
        self.status = "FIRST ROUND"
        self._draw_cache = {"ts": 0.0, "data": []}

    def login(self):
        print(col("Logging in to BDGWin...", Style.CYAN))
        if not self.checker.perform_login():
            raise RuntimeError("Login failed: " + self.checker.message)
        print(col("Fetching user info...", Style.CYAN))
        self.checker.fetch_user_info()
        ud = self.checker.user_info
        balance = None
        for key in ("amount", "balance", "money", "coin", "points"):
            if key in ud:
                try:
                    bal = float(ud[key])
                    if bal > 0:
                        balance = bal
                        break
                except:
                    pass
        if balance is None:
            balance = 0
        self.start_balance = self.current_balance = balance
        self.levels = make_levels(self.current_balance, self.start_total_bet, self.multiplier)
        print(col(f"Balance: {fmt_money(self.start_balance)}", Style.GREEN))

    def refresh_balance(self):
        self.checker.fetch_user_info()
        ud = self.checker.user_info
        for key in ("amount", "balance", "money", "coin", "points"):
            if key in ud:
                try:
                    self.current_balance = float(ud[key])
                    break
                except:
                    pass
        self.net_profit = self.current_balance - self.start_balance

    def fetch_open_issue(self):
        draw_urls = ["https://draw.ar-lottery06.com", self.checker.lottery_draw_base_url]
        for base in draw_urls:
            try:
                url = f"{base}/WinGo/{self.game_code}/GetCurrentIssue.json"
                resp = requests.get(url, timeout=5, verify=False, headers={"User-Agent": "Mozilla/5.0"})
                data = resp.json()
                if data.get("code") == 0 and "data" in data:
                    return str(data["data"]["issueNumber"])
            except:
                pass
        issues = self.fetch_draw_history(1)
        if issues:
            last = issues[0]["issueNumber"]
            prefix = last[:-3]
            num = int(last[-3:]) + 1
            return f"{prefix}{num:03d}"
        return None

    def fetch_draw_history(self, page_size=6):
        now = time.time()
        if self._draw_cache["data"] and now - self._draw_cache["ts"] < 1.0:
            return self._draw_cache["data"]
        draw_urls = ["https://draw.ar-lottery06.com", self.checker.lottery_draw_base_url]
        for base in draw_urls:
            try:
                ts = int(now * 1000)
                url = f"{base}/WinGo/{self.game_code}/GetHistoryIssuePage.json?pageSize={page_size}&ts={ts}"
                resp = requests.get(url, timeout=6, verify=False, headers={"User-Agent": "Mozilla/5.0"})
                data = resp.json()
                if isinstance(data, dict) and data.get("code") == 0:
                    issues = data["data"]["list"]
                    issues.sort(key=lambda x: x["issueNumber"], reverse=True)
                    self._draw_cache = {"ts": now, "data": issues}
                    return issues
            except:
                pass
        return self._draw_cache["data"] or []

    def place_dual_bet(self, issue, bs_side, color_side, bs_bet, color_bet):
        for attempt in range(5):
            try:
                bs_content = f"BigSmall_{bs_side.capitalize()}"
                color_content = f"Color_{color_side.capitalize()}"
                self.checker.place_wingo_bet(issue, bs_bet, 1, bs_content, self.game_code)
                self.checker.place_wingo_bet(issue, color_bet, 1, color_content, self.game_code)
                return
            except Exception as e:
                if "not exist" in str(e).lower():
                    time.sleep(1)
                    issue = self.fetch_open_issue()
                    if not issue:
                        raise RuntimeError("Cannot find valid open issue")
                    continue
                raise

    def evaluate_pending(self, actual_period, actual_num):
        if not self.pending or str(self.pending["period"]) != str(actual_period):
            return
        actual_bs = "BIG" if actual_num >= 5 else "SMALL"
        actual_color = "GREEN" if actual_num in GREEN_NUMS else "RED"
        bs_match = self.pending["bs_prediction"] == actual_bs
        color_match = self.pending["color_prediction"] == actual_color
        if bs_match and color_match:
            result = "DOUBLE WIN"
            self.double_win += 1
            self.current_level = 0
        elif bs_match or color_match:
            result = "BREAK EVEN"
            self.break_even += 1
        else:
            result = "DOUBLE LOSS"
            self.double_loss += 1
            self.current_level += 1
            if self.current_level >= len(self.levels):
                self.stopped = True
                self.status = "LEVEL FINISHED - STOP"
        rec = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "period": actual_period,
            "level": self.pending["level"],
            "color_bet": self.pending["color_bet"],
            "bs_bet": self.pending["bs_bet"],
            "total_bet": self.pending["total_bet"],
            "pred_bs": self.pending["bs_prediction"],
            "pred_color": self.pending["color_prediction"],
            "actual_bs": actual_bs,
            "actual_color": actual_color,
            "actual_num": actual_num,
            "bs_hit": bs_match,
            "color_hit": color_match,
            "result": result
        }
        self.history.append(rec)
        self.history = self.history[-100:]
        self.pending = None
        if not self.stopped:
            self.status = result
        self.refresh_balance()

    def print_header(self):
        print(col("""
 ____  _    _  _____    _____ ____  _  ____
| __ )| |  | |/ _ \\ \\  / / ___/ __ \\| |/ /
|  _ \\| |  | | | | \\ \\/ /\\__ \\ / _` | ' /
| |_) | |__| | |_| |\\  /  __/ / (_| | . \\
|____/ \\____/ \\___/  \\/  |___/\\__,_|_|\\_\\
""", Style.CYAN))
        print(col("     BDGWIN AUTO BET - DUAL LEVEL ENGINE", Style.MAGENTA + Style.BOLD))
        print(col(f"     Game: {self.game_code} | Start Bet: {self.start_total_bet} | Mult: {self.multiplier}x | Min Conf: {self.confidence_pct}%", Style.YELLOW))
        print(col(rule("=", 110), Style.CYAN))
        print(f"{'Period':<15}{'Prediction':<22}{'Bet':<12}{'Actual':<18}{'Result':<24}{'Balance':<12}")
        print("-" * 110)

    def print_round(self, per, bs, co, bs_b, co_b, act_num, result):
        act_bs = "BIG" if act_num >= 5 else "SMALL"
        act_co = "GREEN" if act_num in GREEN_NUMS else "RED"
        line = f"{per[-12:]:<15}{bs+'-'+co:<22}{bs_b+co_b:<12}{act_bs+'-'+act_co+'('+str(act_num)+')':<18}{result:<24}{self.current_balance:<12.2f}"
        clr = Style.GREEN if "WIN" in result else Style.RED if "LOSS" in result else Style.YELLOW
        print(col(line, clr))

    def run_loop(self):
        self.running = True
        self.login()
        # Fetch AR token for lottery API
        print(col("Fetching AR token for lottery...", Style.CYAN))
        try:
            self.checker.fetch_ar_token(self.game_code)
            print(col("AR token obtained!", Style.GREEN))
        except Exception as e:
            print(col(f"AR token error: {e}", Style.YELLOW))
        self.print_header()
        while self.running:
            try:
                data = self.fetch_draw_history(6)
                if not data:
                    time.sleep(1)
                    continue
                latest = str(data[0]["issueNumber"])
                if latest == self.last_seen_period:
                    time.sleep(1)
                    continue
                self.last_seen_period = latest
                nums = [int(x["number"]) for x in data[:6]]
                actual_num = nums[0]

                if self.pending:
                    self.evaluate_pending(latest, actual_num)
                    if self.pending:
                        continue
                    if self.history:
                        last = self.history[-1]
                        self.print_round(last["period"], last["pred_bs"], last["pred_color"],
                                         last["bs_bet"], last["color_bet"], last["actual_num"], last["result"])

                if self.stopped:
                    print(col("Level limit reached. Bot stopped.", Style.RED))
                    break

                if not self.pending:
                    pattern_bs = [("B" if n >= 5 else "S") for n in reversed(nums)]
                    pattern_co = [("G" if n in GREEN_NUMS else "R") for n in reversed(nums)]
                    bs_pred, bs_rule = predict_bs(pattern_bs)
                    co_pred, co_rule = predict_color(pattern_co)

                    if bs_pred == "SKIP":
                        print(col(f"{latest[-12:]:<15}{'SKIP':<22}{'':<12}{'':<18}Low confidence{self.current_balance:<12.2f}", Style.MAGENTA))
                        time.sleep(1)
                        continue

                    open_issue = self.fetch_open_issue()
                    if not open_issue:
                        time.sleep(1)
                        continue

                    lv = self.levels[self.current_level]
                    self.place_dual_bet(open_issue, bs_pred, co_pred, lv["bs_bet"], lv["color_bet"])
                    self.pending = {
                        "period": open_issue,
                        "level": lv["level"],
                        "color_bet": lv["color_bet"],
                        "bs_bet": lv["bs_bet"],
                        "total_bet": lv["total_bet"],
                        "bs_prediction": bs_pred,
                        "color_prediction": co_pred,
                    }
                    print(col(f"Bet placed on {open_issue[-12:]} -> {bs_pred}/{co_pred} (L{lv['level']}, total {lv['total_bet']})", Style.CYAN))

                time.sleep(1)

            except KeyboardInterrupt:
                print(col("\nUser stopped.", Style.YELLOW))
                break
            except Exception as e:
                print(col(f"Error: {e}", Style.RED))
                time.sleep(3)

        self.checker.close()
        print(col("Bot stopped.", Style.CYAN))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  MAIN
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def main():
    print(col("BDGWin Dual Level Engine", Style.CYAN + Style.BOLD))
    username = input("Username/Mobile: ").strip()
    password = getpass.getpass("Password: ")
    if not username or not password:
        print(col("Credentials required.", Style.RED))
        return 1
    
    print("\n1. WinGo 30 sec")
    print("2. WinGo 1 min")
    print("3. WinGo 3 min")
    print("4. WinGo 5 min")
    print("5. WinGo 10 min")
    choice = input("Choose (1-5): ").strip()
    game = GAME_CODES.get(choice, "WinGo_30S")
    
    tb = input(f"Start total bet [2]: ").strip()
    try:
        tb = int(tb) if tb else 2
    except:
        tb = 2
    
    mult = input(f"Multiplier (1.5/2/3) [2.0]: ").strip()
    try:
        mult = float(mult) if mult else 2.0
    except:
        mult = 2.0

    engine = BDGWinAutoBetEngine(username, password, game, tb, mult, 55)
    try:
        engine.run_loop()
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(col(f"FATAL: {e}", Style.RED))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())