#!/usr/bin/env python3
"""
Jai Club / AR Lottery Auto‑Bet CLI (Dual Level Engine – BN Last King Logic)

- Full AccountChecker for login & betting
- Manual balance entry if API returns 0
- Dual bet: half on Color, half on Big/Small
- Level staking: double loss → next level, break‑even → repeat, double win → reset
- 1‑second polling, real open issue fetch
"""

from __future__ import annotations

import base64
from collections import defaultdict
import getpass
import hashlib
import io
import json
import logging
import math
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests
import urllib3

try:
    from PIL import Image, ImageFilter, ImageOps
except ImportError:
    print("Install missing libraries: pip install requests urllib3 pillow")
    raise

# ── Colors ───────────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
NEON_GREEN = "\033[92m"
NEON_MAGENTA = "\033[95m"
NEON_CYAN = "\033[96m"

def col(text, code):
    return f"{code}{text}{RESET}" if sys.stdout.isatty() else text

# ── Constants ────────────────────────────────────────────────
GAME_CODES = {"1": "WinGo_30S", "2": "WinGo_1M"}
DEFAULT_BASE_TOTAL_BET = 2
DEFAULT_CONFIDENCE = 55          # percent
DEFAULT_MULTIPLIER = 2.0
PROFIT_TARGET_PCT = 50.0
RESULT_POLL_TIMEOUT = 60
LOOP_PAUSE = 1                   # 1 second

GREEN_NUMS = {1, 3, 5, 7, 9}
RED_NUMS   = {0, 2, 4, 6, 8}

LOTTERY_AUTH_MODES = ("bearer", "authorization", "token", "x-token", "token-lower")

logging.basicConfig(level=logging.INFO)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── AccountChecker ───────────────────────────────────────────
class AccountChecker:
    def __init__(self, username: str, password: str):
        self.username = username.strip()
        self.password = password.strip()
        self.base_url = os.environ.get("JAI_BASE_URL", "https://www.jaiclub06.com").rstrip("/")
        self.api_base_url = os.environ.get("JAI_API_BASE_URL", "https://api.jaiclubapi.com").rstrip("/")
        self.lottery_api_base_url = os.environ.get("JAI_LOTTERY_API_BASE_URL", "https://h5.ar-lottery06.com").rstrip("/")
        self.lottery_draw_base_url = os.environ.get("JAI_LOTTERY_DRAW_BASE_URL", "https://draw.ar-lottery06.com").rstrip("/")
        self.client = requests.Session()
        self.timeout = 25
        self.verify_ssl = False
        self.jwt_token: str | None = None
        self.ar_token: str | None = None
        self.ar_launch_url: str | None = None
        self.auth_token_candidates: list[str] = []
        self.lottery_auth_mode = "bearer"
        self.lottery_debug: list[dict[str, Any]] = []
        self.user_info: dict[str, Any] = {}
        self.status = "unknown"
        self.message = ""

    def is_rate_limited(self, message: str | None) -> bool:
        text = (message or "").lower()
        keywords = (
            "too frequent",
            "too many",
            "rate limit",
            "rate-limit",
            "try again later",
            "request too fast",
        )
        return any(keyword in text for keyword in keywords)

    def backoff_seconds(self, attempt: int) -> int:
        return min(90, 20 + (attempt * 15))

    def update_headers(self) -> None:
        self.client.headers.update(
            {
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
            }
        )

    def update_lottery_headers(self) -> None:
        self.client.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Mobile Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json;charset=UTF-8",
                "Origin": "https://h5.ar-lottery06.com",
                "Referer": "https://h5.ar-lottery06.com/",
                "Connection": "keep-alive",
            }
        )

    def mask_token(self, token: str | None) -> str:
        token = (token or "").strip()
        if not token:
            return "missing"
        if len(token) <= 14:
            return f"{token[:4]}...({len(token)})"
        return f"{token[:8]}...{token[-6:]} ({len(token)})"

    def generate_signature(self, params_dict: dict[str, Any]) -> str:
        language = params_dict.get("language", 0)
        random_val = params_dict.get("random", "")
        param_str = f'{{"language":{language},"random":"{random_val}"}}'
        return hashlib.md5(param_str.encode()).hexdigest().upper()

    def generate_login_signature(self, params: dict[str, Any]) -> str:
        sig_fields = [
            "username",
            "captchaId",
            "pwd",
            "phonetype",
            "logintype",
            "deviceId",
            "language",
            "random",
        ]
        filtered_params = {k: params[k] for k in sig_fields if k in params}
        parts = []
        for key in sorted(filtered_params.keys()):
            value = filtered_params[key]
            if isinstance(value, int):
                parts.append(f'"{key}":{value}')
            else:
                parts.append(f'"{key}":"{value}"')
        return hashlib.md5(("{" + ",".join(parts) + "}").encode()).hexdigest().upper()

    def generate_generic_signature(self, params: dict[str, Any]) -> str:
        sign_params = {
            key: value
            for key, value in params.items()
            if key not in {"signature", "timestamp"} and value is not None and value != ""
        }
        json_str = json.dumps(sign_params, separators=(",", ":"), sort_keys=True)
        return hashlib.md5(json_str.encode()).hexdigest().upper()

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
            raise RuntimeError(f"{api_name} returned empty response. HTTP {response.status_code}.")
        try:
            return response.json()
        except ValueError as exc:
            content_type = response.headers.get("content-type", "unknown")
            preview = body[:300].replace("\n", " ").replace("\r", " ")
            raise RuntimeError(
                f"{api_name} returned non-JSON response. HTTP {response.status_code}, "
                f"content-type: {content_type}, body: {preview}"
            ) from exc

    def extract_token_candidates(self, obj: Any) -> list[str]:
        candidates: list[str] = []
        token_words = ("token", "jwt", "authorization", "access", "auth")

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                for key, nested in value.items():
                    key_text = str(key).lower()
                    if isinstance(nested, str) and any(word in key_text for word in token_words):
                        cleaned = nested.strip()
                        if len(cleaned) >= 20 and cleaned not in candidates:
                            candidates.append(cleaned)
                    elif isinstance(nested, (dict, list)):
                        walk(nested)
                    elif isinstance(nested, str) and nested.count(".") == 2 and len(nested) >= 20:
                        cleaned = nested.strip()
                        if cleaned not in candidates:
                            candidates.append(cleaned)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(obj)
        return candidates

    def post_api(self, endpoint: str, payload: dict[str, Any]) -> requests.Response:
        try:
            return self.client.post(
                f"{self.api_base_url}{endpoint}",
                json=payload,
                timeout=self.timeout,
                allow_redirects=True,
                verify=self.verify_ssl,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Network/API connection failed for {endpoint}: {exc}.") from exc

    def post_signed_webapi(self, endpoint: str, payload: dict[str, Any]) -> requests.Response:
        signed_payload = self.generate_ar_signature_payload(payload)
        self.update_headers()
        if self.jwt_token:
            token = self.jwt_token.strip()
            self.client.headers["Authorization"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"
        return self.post_api(endpoint, signed_payload)

    def get_lottery_api(self, endpoint: str, params: dict[str, Any]) -> requests.Response:
        signed_params = self.generate_ar_signature_payload(params)
        return self.client.get(
            f"{self.lottery_api_base_url}{endpoint}",
            params=signed_params,
            timeout=self.timeout,
            allow_redirects=True,
            verify=self.verify_ssl,
        )

    def post_lottery_api(self, endpoint: str, payload: dict[str, Any]) -> requests.Response:
        signed_payload = self.generate_ar_signature_payload(payload)
        return self.client.post(
            f"{self.lottery_api_base_url}{endpoint}",
            json=signed_payload,
            timeout=self.timeout,
            allow_redirects=True,
            verify=self.verify_ssl,
        )

    def base64_to_image(self, b64_str: str) -> Image.Image | None:
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        try:
            img_data = base64.b64decode(b64_str)
            return Image.open(io.BytesIO(img_data)).convert("RGBA")
        except Exception as exc:
            logger.error("Image decode error: %s", exc)
            return None

    def extract_slider_piece(self, slider: Image.Image) -> tuple[Image.Image, Image.Image] | tuple[None, None]:
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

    def score_slider_position(self, bg_edges, slider_edges, slider_mask, start_x, step=2):
        bg_crop = bg_edges.crop((start_x, 0, start_x + slider_edges.width, slider_edges.height))
        bg_px = bg_crop.load()
        slider_px = slider_edges.load()
        mask_px = slider_mask.load()
        score = 0.0
        samples = 0
        for y in range(0, slider_edges.height, step):
            for x in range(0, slider_edges.width, step):
                if mask_px[x, y] <= 0:
                    continue
                score += abs(bg_px[x, y] - slider_px[x, y])
                samples += 1
        if samples == 0:
            return float("inf")
        return score / samples

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
        if bg_edges.width <= 0 or slider_edges.width <= 0 or bg_edges.width < slider_edges.width:
            return 0
        best_score = float("inf")
        best_x = 0
        max_x = bg_edges.width - slider_edges.width
        for offset_x in range(0, max_x + 1):
            score = self.score_slider_position(bg_edges, slider_edges, slider_mask, offset_x)
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
                        captcha_payload = data.get("data") or {}
                        required = {"captchaId", "backgroundImage", "sliderImage"}
                        if sorted(required - set(captcha_payload)):
                            self.message = "Captcha response missing fields."
                            return None
                        return captcha_payload
                    self.message = data.get("msg") or f"Captcha API code {data.get('code')}"
                    if self.is_rate_limited(self.message):
                        time.sleep(self.backoff_seconds(retry))
                        continue
                else:
                    self.message = f"Captcha HTTP {response.status_code}"
            except Exception as exc:
                self.message = f"Captcha error: {exc}"
            time.sleep(2)
        return None

    def perform_login(self) -> bool:
        for attempt in range(5):
            if attempt > 0:
                time.sleep(random.uniform(3, 6))
            captcha_data = self.get_captcha()
            if not captcha_data:
                if self.is_rate_limited(self.message):
                    time.sleep(self.backoff_seconds(attempt))
                    continue
                self.status = "error"
                return False
            target_x = self.solve_captcha_image(captcha_data.get("backgroundImage", ""), captcha_data.get("sliderImage", ""))
            if target_x is None:
                self.status = "error"
                self.message = "Captcha solve failed."
                return False
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
                    self.status = "error"
                    self.message = f"Login HTTP {response.status_code}"
                    return False
                data = self.parse_json_response(response, "Login")
                if data.get("code") == 0:
                    login_data = data.get("data", {})
                    self.auth_token_candidates = self.extract_token_candidates(data)
                    self.jwt_token = login_data.get("token") or (self.auth_token_candidates[0] if self.auth_token_candidates else None)
                    if self.jwt_token and self.jwt_token not in self.auth_token_candidates:
                        self.auth_token_candidates.insert(0, self.jwt_token)
                    if not self.jwt_token:
                        self.status = "error"
                        self.message = "Token not found."
                        return False
                    self.status = "active"
                    self.message = "Login successful."
                    return True
                self.message = data.get("msg") or f"Login code {data.get('code')}"
                lowered = self.message.lower()
                if self.is_rate_limited(self.message):
                    time.sleep(self.backoff_seconds(attempt))
                    continue
                if "password" in lowered or "exist" in lowered:
                    self.status = "invalid"
                elif "freeze" in lowered:
                    self.status = "banned"
                else:
                    self.status = "failed"
                return False
            except Exception as exc:
                self.status = "error"
                self.message = f"Login error: {exc}"
                return False
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
        except Exception as exc:
            logger.error("Fetch user info error: %s", exc)
        return self.user_info

    def attach_token(self, jwt_token, auth_mode=None):
        self.jwt_token = jwt_token
        self.update_lottery_headers()
        self.lottery_auth_mode = auth_mode or self.lottery_auth_mode or "bearer"
        token_value = (self.jwt_token or "").strip()
        bare_token = token_value[7:].strip() if token_value.lower().startswith("bearer ") else token_value
        for header in ("Authorization", "Token", "X-Token", "token"):
            self.client.headers.pop(header, None)
        if self.lottery_auth_mode == "bearer":
            self.client.headers["Authorization"] = f"Bearer {bare_token}"
        elif self.lottery_auth_mode == "authorization":
            self.client.headers["Authorization"] = bare_token
        elif self.lottery_auth_mode == "token":
            self.client.headers["Token"] = bare_token
        elif self.lottery_auth_mode == "x-token":
            self.client.headers["X-Token"] = bare_token
        elif self.lottery_auth_mode == "token-lower":
            self.client.headers["token"] = bare_token

    def extract_ar_launch_data(self, launch_url):
        parsed = urlparse(launch_url or "")
        query = parse_qs(parsed.query)
        token = (query.get("Token") or query.get("token") or [""])[0]
        lang = (query.get("Lang") or query.get("language") or ["en"])[0]
        skin = (query.get("Skin") or [""])[0]
        if parsed.scheme and parsed.netloc:
            origin = f"{parsed.scheme}://{parsed.netloc}"
            self.lottery_api_base_url = origin
            self.lottery_draw_base_url = origin.replace("h5.", "draw.")
        return {"token": token, "lang": lang, "skin": skin, "url": launch_url or "", "apiBase": self.lottery_api_base_url, "drawBase": self.lottery_draw_base_url}

    def fetch_ar_token(self, game_code="WinGo_30S"):
        payloads = [
            {"gameCode": game_code, "vendorCode": "ARLottery", "returnUrl": self.base_url, "deviceType": 1},
            {"gameCode": game_code, "vendorCode": "ARLottery", "returnUrl": self.base_url, "deviceType": 0},
            {"gameCode": game_code, "vendorCode": "ARLottery", "returnUrl": self.base_url, "deviceType": "H5"},
            {"gameCode": game_code, "vendorCode": "ARLottery", "returnUrl": self.base_url, "phonetype": 1},
            {"vendorCode": "ARLottery", "returnUrl": self.base_url, "deviceType": 1},
        ]
        for payload in payloads:
            try:
                response = self.post_signed_webapi("/api/webapi/GetGameUrl", payload)
                data = self.parse_json_response(response, "GetGameUrl")
                if response.status_code == 200 and data.get("code") == 0:
                    launch_url = data.get("data", {}).get("url") if isinstance(data.get("data"), dict) else data.get("data")
                    launch_data = self.extract_ar_launch_data(launch_url)
                    if launch_data["token"]:
                        self.ar_token = launch_data["token"]
                        self.ar_launch_url = launch_url
                        return launch_data
            except Exception:
                pass
        raise RuntimeError("Could not fetch AR token.")

    def lottery_auth_mode_order(self):
        modes = list(LOTTERY_AUTH_MODES)
        if self.lottery_auth_mode in modes:
            modes.remove(self.lottery_auth_mode)
            modes.insert(0, self.lottery_auth_mode)
        return modes

    def run_lottery_request(self, api_name, request_factory):
        token_candidates = []
        for token in [self.ar_token, self.jwt_token] + self.auth_token_candidates:
            if token and token not in token_candidates:
                token_candidates.append(token)
        last_error = None
        for token in token_candidates:
            for auth_mode in self.lottery_auth_mode_order():
                self.attach_token(token, auth_mode)
                try:
                    response = request_factory()
                except Exception as e:
                    last_error = e
                    continue
                if response.status_code == 401 or response.status_code == 403:
                    continue
                try:
                    data = self.parse_json_response(response, api_name)
                except RuntimeError as e:
                    last_error = e
                    continue
                msg = str(data.get("msg", "")).lower()
                if data.get("code") in {401, 4010} or "unauthor" in msg or ("token" in msg and "invalid" in msg):
                    continue
                self.jwt_token = token
                self.lottery_auth_mode = auth_mode
                return response, data
        raise RuntimeError(f"{api_name}: All tokens rejected. Last error: {last_error}")

    def place_wingo_bet(self, issue_number, amount, bet_multiple, bet_content, game_code="WinGo_30S", language="en"):
        payload = {
            "gameCode": game_code,
            "issueNumber": issue_number,
            "amount": amount,
            "betMultiple": bet_multiple,
            "betContent": bet_content,
            "language": language,
            "random": random.randint(100000000000, 999999999999),
        }
        response, data = self.run_lottery_request("WinGoBet", lambda: self.post_lottery_api("/api/Lottery/WinGoBet", payload))
        if response.status_code != 200 or data.get("code") != 0:
            raise RuntimeError(data.get("msg") or "WinGoBet failed")
        return data

    def close(self):
        self.client.close()


# ── SIMPLE PREDICTION SYSTEM ──────────────────────────────
def predict_bs(pattern):
    """
    Predict Big/Small based on last 6 results
    pattern: list of "B" (>=5) or "S" (<5) 
    Returns: (prediction, rule)
    """
    if len(pattern) < 2:
        return "BIG", "DEFAULT"
    
    p = " ".join(pattern)
    
    # Exact pattern matches (top 10 most common)
    rules = {
        "S S S B B B": "SMALL",
        "B B B S S S": "BIG",
        "B B S S B B": "BIG",
        "S S B B S S": "SMALL",
        "B S B S B S": "BIG",
        "S B S B S B": "SMALL",
        "B B B B S S": "BIG",
        "S S S S B B": "SMALL",
        "B S S B B S": "SMALL",
        "S B B S S B": "BIG",
    }
    
    if p in rules:
        return rules[p], "PATTERN"
    
    b = pattern.count("B")
    s = pattern.count("S")
    
    # Reversal rules
    if b >= 5:
        return "SMALL", "5X REVERSAL"
    if s >= 5:
        return "BIG", "5X REVERSAL"
    if b >= 4:
        return "SMALL", "4X REVERSAL"
    if s >= 4:
        return "BIG", "4X REVERSAL"
    
    # Trend rules (3 in a row)
    if pattern[-3:] == ["B", "B", "B"]:
        return "BIG", "3X TREND"
    if pattern[-3:] == ["S", "S", "S"]:
        return "SMALL", "3X TREND"
    
    # Trend rules (2 in a row)
    if pattern[-2:] == ["B", "B"]:
        return "BIG", "2X TREND"
    if pattern[-2:] == ["S", "S"]:
        return "SMALL", "2X TREND"
    
    # Count rule (fallback)
    if b > s:
        return "BIG", "COUNT"
    elif s > b:
        return "SMALL", "COUNT"
    else:
        return "BIG", "TIE"


def predict_color(pattern):
    """
    Predict Red/Green based on last 6 results
    pattern: list of "G" (odd numbers) or "R" (even numbers)
    Returns: (prediction, rule)
    """
    if len(pattern) < 2:
        return "RED", "DEFAULT"
    
    p = " ".join(pattern)
    
    # Exact pattern matches
    rules = {
        "R R R G G G": "RED",
        "G G G R R R": "GREEN",
        "R R G G R R": "RED",
        "G G R R G G": "GREEN",
        "R G R G R G": "RED",
        "G R G R G R": "GREEN",
        "R R R R G G": "RED",
        "G G G G R R": "GREEN",
        "R G G R R G": "RED",
        "G R R G G R": "GREEN",
    }
    
    if p in rules:
        return rules[p], "PATTERN"
    
    r = pattern.count("R")
    g = pattern.count("G")
    
    # Reversal rules
    if r >= 5:
        return "GREEN", "5X REVERSAL"
    if g >= 5:
        return "RED", "5X REVERSAL"
    if r >= 4:
        return "GREEN", "4X REVERSAL"
    if g >= 4:
        return "RED", "4X REVERSAL"
    
    # Trend rules (3 in a row)
    if pattern[-3:] == ["R", "R", "R"]:
        return "RED", "3X TREND"
    if pattern[-3:] == ["G", "G", "G"]:
        return "GREEN", "3X TREND"
    
    # Trend rules (2 in a row)
    if pattern[-2:] == ["R", "R"]:
        return "RED", "2X TREND"
    if pattern[-2:] == ["G", "G"]:
        return "GREEN", "2X TREND"
    
    # Count rule (fallback)
    if r > g:
        return "RED", "COUNT"
    elif g > r:
        return "GREEN", "COUNT"
    else:
        return "RED", "TIE"


def calc_confidence(bs_rule, color_rule):
    """
    Calculate confidence percentage based on rules used
    """
    conf = 55  # Base confidence
    
    # Pattern rules = highest confidence
    if "PATTERN" in bs_rule:
        conf += 20
    if "PATTERN" in color_rule:
        conf += 20
    
    # Trend rules = medium confidence
    if "TREND" in bs_rule:
        conf += 10
    if "TREND" in color_rule:
        conf += 10
    
    # Reversal rules = good confidence
    if "REVERSAL" in bs_rule:
        conf += 15
    if "REVERSAL" in color_rule:
        conf += 15
    
    return min(conf, 95)


# ── Level Calculator ────────────────────────────────────────
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


# ── AutoBet Engine ──────────────────────────────────────────
class AutoBetEngine:
    def __init__(self, username, password, game_code, total_bet, multiplier, confidence_pct):
        self.username = username; self.password = password
        self.game_code = game_code; self.start_total_bet = total_bet
        self.multiplier = multiplier; self.confidence_pct = confidence_pct
        self.checker = AccountChecker(username, password)
        self.running = False
        self.start_balance = 0.0; self.current_balance = 0.0; self.net_profit = 0.0
        self.levels = []; self.current_level = 0
        self.win = 0; self.loss = 0; self.break_even = 0
        self.double_win = 0; self.double_loss = 0
        self.pending = None; self.last_seen_period = None
        self.history = []; self.stopped = False; self.status = "FIRST ROUND"

    def login(self):
        if not self.checker.perform_login():
            raise RuntimeError("Login failed: " + self.checker.message)
        self.checker.fetch_user_info()
        ud = self.checker.user_info
        balance = None
        for key in ("amount", "balance", "money", "coin", "points"):
            if key in ud:
                try:
                    bal = float(ud[key])
                    if bal > 0: balance = bal; break
                except: pass
        if balance is None or balance == 0:
            balance = 0
        self.start_balance = self.current_balance = balance
        self.levels = make_levels(self.current_balance, self.start_total_bet, self.multiplier)

    def refresh_balance(self):
        self.checker.fetch_user_info()
        ud = self.checker.user_info
        bal = None
        for key in ("amount", "balance", "money", "coin", "points"):
            if key in ud:
                try: bal = float(ud[key]); break
                except: pass
        if bal is not None and bal > 0:
            self.current_balance = bal
        self.net_profit = self.current_balance - self.start_balance

    def fetch_open_issue(self):
        """Return the currently open issue number (the one you can bet on)."""
        draw_urls = [
            os.environ.get("JAI_LOTTERY_DRAW_BASE_URL", "https://draw.ar-lottery06.com").rstrip("/"),
            "https://draw.ar-lottery01.com",
        ]
        for base in draw_urls:
            try:
                url = f"{base}/WinGo/{self.game_code}/GetCurrentIssue.json"
                resp = requests.get(url, timeout=5, verify=False)
                data = resp.json()
                if data.get("code") == 0 and "data" in data:
                    return str(data["data"]["issueNumber"])
            except: pass
        issues = self.fetch_draw_history(1)
        if issues:
            last = issues[0]["issueNumber"]
            prefix = last[:-3]; num = int(last[-3:]) + 1
            return f"{prefix}{num:03d}"
        return None

    def fetch_draw_history(self, page_size=6):
        draw_urls = [
            os.environ.get("JAI_LOTTERY_DRAW_BASE_URL", "https://draw.ar-lottery06.com").rstrip("/"),
            "https://draw.ar-lottery01.com",
        ]
        for base in draw_urls:
            try:
                url = f"{base}/WinGo/{self.game_code}/GetHistoryIssuePage.json?pageSize={page_size}&pageNo=1"
                resp = requests.get(url, timeout=6, verify=False)
                data = resp.json()
                if data.get("code") == 0:
                    issues = data["data"]["list"]
                    issues.sort(key=lambda x: x["issueNumber"], reverse=True)
                    return issues
            except Exception as e: logging.error("draw history (%s): %s", base, e)
        return []

    def place_dual_bet(self, issue, bs_side, color_side, bs_bet, color_bet):
        max_retries = 5
        for attempt in range(max_retries):
            try:
                self.checker.place_wingo_bet(issue, bs_bet, 1, f"BigSmall_{bs_side.capitalize()}", self.game_code)
                self.checker.place_wingo_bet(issue, color_bet, 1, f"Color_{color_side.capitalize()}", self.game_code)
                return
            except Exception as e:
                if "does not exist" in str(e).lower() or "not open" in str(e).lower():
                    print(col(f"Issue {issue} not open yet, retrying in 1s...", YELLOW))
                    time.sleep(1)
                    issue = self.fetch_open_issue()
                    if not issue:
                        raise RuntimeError("Cannot find valid open issue")
                    continue
                else:
                    raise RuntimeError(f"Betting failed after {attempt+1} attempts: {e}")
        raise RuntimeError(f"Betting failed after {max_retries} retries")

    def evaluate_pending(self, actual_period, actual_num):
        if not self.pending or str(self.pending["period"]) != str(actual_period):
            return
        actual_bs = "BIG" if actual_num >= 5 else "SMALL"
        actual_color = "GREEN" if actual_num in GREEN_NUMS else "RED"
        bs_match = self.pending["bs_prediction"] == actual_bs
        color_match = self.pending["color_prediction"] == actual_color
        if bs_match and color_match:
            result = "DOUBLE WIN ✅✅"; self.double_win += 1; self.current_level = 0
        elif bs_match or color_match:
            result = "BREAK EVEN ✅❌"; self.break_even += 1
        else:
            result = "DOUBLE LOSS ❌❌"; self.double_loss += 1; self.current_level += 1
            if self.current_level >= len(self.levels):
                self.stopped = True; self.status = "LEVEL FINISHED - STOP"
        rec = {
            "time": datetime.now().strftime("%H:%M:%S"), "period": actual_period,
            "level": self.pending["level"], "color_bet": self.pending["color_bet"],
            "bs_bet": self.pending["bs_bet"], "total_bet": self.pending["total_bet"],
            "pred_bs": self.pending["bs_prediction"], "pred_color": self.pending["color_prediction"],
            "actual_bs": actual_bs, "actual_color": actual_color, "actual_num": actual_num,
            "bs_hit": bs_match, "color_hit": color_match, "result": result
        }
        self.history.append(rec); self.history = self.history[-100:]
        self.pending = None
        if not self.stopped: self.status = result
        self.refresh_balance()

    def run_loop(self):
        self.running = True
        self.login()
        if not self.checker.ar_token:
            self.checker.fetch_ar_token(self.game_code)
        self.print_header()
        while self.running:
            try:
                data = self.fetch_draw_history(6)
                if not data:
                    time.sleep(1); continue
                latest = str(data[0]["issueNumber"])
                if latest == self.last_seen_period:
                    time.sleep(1); continue
                self.last_seen_period = latest
                nums = [int(x["number"]) for x in data[:6]]
                actual_num = nums[0]

                # Evaluate pending bet first
                if self.pending:
                    self.evaluate_pending(latest, actual_num)
                    if self.pending:   # still waiting for result
                        continue
                    if self.history:
                        last = self.history[-1]
                        self.print_round(last["period"], last["pred_bs"], last["pred_color"],
                                         last["bs_bet"], last["color_bet"], last["actual_num"], last["result"])

                if self.stopped:
                    print(col("Level limit reached. Bot stopped.", RED)); break

                # Place next bet
                if not self.pending:
                    pattern_bs = [("B" if n >= 5 else "S") for n in reversed(nums)]
                    pattern_co = [("G" if n in GREEN_NUMS else "R") for n in reversed(nums)]
                    bs_pred, bs_rule = predict_bs(pattern_bs)
                    co_pred, co_rule = predict_color(pattern_co)
                    conf = calc_confidence(bs_rule, co_rule)

                    if conf < self.confidence_pct:
                        print(col(f"{latest[-12:]:<15}{'SKIP':<22}{'':<12}{'':<18}Low confidence{self.current_balance:<12.2f}", MAGENTA))
                        time.sleep(1); continue

                    open_issue = self.fetch_open_issue()
                    if not open_issue:
                        time.sleep(1); continue

                    lv = self.levels[self.current_level]
                    self.place_dual_bet(open_issue, bs_pred, co_pred, lv["bs_bet"], lv["color_bet"])
                    self.pending = {
                        "period": open_issue, "level": lv["level"],
                        "color_bet": lv["color_bet"], "bs_bet": lv["bs_bet"],
                        "total_bet": lv["total_bet"],
                        "bs_prediction": bs_pred, "color_prediction": co_pred,
                        "bs_rule": bs_rule, "color_rule": co_rule, "confidence": conf
                    }
                    print(col(f"⚡ Bet placed on {open_issue[-12:]} → {bs_pred}/{co_pred} (L{lv['level']}, total {lv['total_bet']})", CYAN))

                if self.start_balance > 0 and (self.net_profit / self.start_balance)*100 >= PROFIT_TARGET_PCT:
                    print(col(f"Profit target {PROFIT_TARGET_PCT}% reached. Stopping.", GREEN)); break
                time.sleep(1)

            except KeyboardInterrupt:
                print(col("\nUser stopped.", YELLOW)); break
            except Exception as e:
                print(col(f"Error: {e}", RED)); time.sleep(3)

        self.checker.close()
        print(col("Bot stopped.", CYAN))

    def print_header(self):
        print(col("""
   ▄████████    ▄████████ ████████▄     ▄████████ 
  ███    ███   ███    ███ ███   ▀███   ███    ███ 
  ███    █▀    ███    ███ ███    ███   ███    █▀  
  ███         ▄███▄▄▄▄██▀ ███    ███  ▄███        
▀███████████ ▀▀███▀▀▀▀▀   ███    ███ ▀▀███ ████▄  
         ███ ▀███████████ ███    ███   ███    ███ 
   ▄█    ███   ███    ███ ███   ▄███   ███    ███ 
 ▄████████▀    ███    ███ ████████▀    ██████████  
               ███    ███                         
""", NEON_CYAN))
        print(col("     JAI CLUB AUTO BET – DUAL LEVEL ENGINE", NEON_MAGENTA+BOLD))
        print(col(f"     Game: {self.game_code} | Start Total Bet: {self.start_total_bet} | Mult: {self.multiplier}x | Min Conf: {self.confidence_pct}%", YELLOW))
        print(col("="*110, CYAN))
        print(f"{'Period':<15}{'Prediction':<22}{'Bet':<12}{'Actual':<18}{'Result':<24}{'Balance':<12}")
        print("-"*110)

    def print_round(self, per, bs, co, bs_b, co_b, act_num, result):
        act_bs = "BIG" if act_num>=5 else "SMALL"
        act_co = "GREEN" if act_num in GREEN_NUMS else "RED"
        line = f"{per[-12:]:<15}{bs+'-'+co:<22}{bs_b+co_b:<12}{act_bs+'-'+act_co+'('+str(act_num)+')':<18}{result:<24}{self.current_balance:<12.2f}"
        clr = GREEN if "WIN" in result else RED if "LOSS" in result else YELLOW
        print(col(line, clr))


# ── Main ────────────────────────────────────────────────────
def main():
    print(col("Jai Club Dual Level Engine – BN Last King Patterns", CYAN+BOLD))
    username = input("Username/Mobile: ").strip()
    password = getpass.getpass("Password: ")
    if not username or not password:
        print(col("Credentials required.", RED)); return 1
    print("\n1. WinGo 30 sec\n2. WinGo 1 min")
    choice = input("Choose (1/2): ").strip()
    game = GAME_CODES.get(choice, "WinGo_30S")
    tb = input(f"Start total bet [{DEFAULT_BASE_TOTAL_BET}]: ").strip()
    try: tb = int(tb) if tb else DEFAULT_BASE_TOTAL_BET
    except: tb = DEFAULT_BASE_TOTAL_BET
    mult = input(f"Multiplier (1.5/2/3) [{DEFAULT_MULTIPLIER}]: ").strip()
    try: mult = float(mult) if mult else DEFAULT_MULTIPLIER
    except: mult = DEFAULT_MULTIPLIER

    engine = AutoBetEngine(username, password, game, tb, mult, DEFAULT_CONFIDENCE)
    try: engine.run_loop(); return 0
    except KeyboardInterrupt: return 130
    except Exception as e: print(col(f"FATAL: {e}", RED)); return 1

if __name__ == "__main__":
    raise SystemExit(main())