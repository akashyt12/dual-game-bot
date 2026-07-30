#!/usr/bin/env python3
"""
BDGWIN Account Checker & Betting Engine
Works with bdgwin79.com - Same backend as JAI Club (AR Lottery)
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse, parse_qs

import requests
import urllib3
from PIL import Image, ImageFilter, ImageOps

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GREEN_NUMS = {1, 3, 5, 7, 9}
RED_NUMS = {0, 2, 4, 6, 8}


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
        self.ar_launch_url: str | None = None
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

    # Captcha Solving
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
                    parsed = urlparse(launch_url or "")
                    query = parse_qs(parsed.query)
                    token = (query.get("Token") or query.get("token") or [""])[0]
                    if token:
                        self.ar_token = token
                        self.ar_launch_url = launch_url
                        return {"token": token, "url": launch_url}
            else:
                logger.warning("GetGameUrl: %s", data.get("msg"))
        except Exception as e:
            logger.error("GetGameUrl error: %s", e)
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

    def fetch_draw_history(self, game_code="WinGo_30S", count=6):
        time.sleep(1)
        try:
            url = f"{self.lottery_draw_base_url}/{game_code}/GetHistoryIssuePage.json"
            params = {"pageNum": 1, "pageSize": count}
            resp = self.client.get(url, params=params, timeout=self.timeout, verify=self.verify_ssl)
            data = resp.json()
            issues = data.get("data", {}).get("list", []) if isinstance(data.get("data"), dict) else []
            results = []
            for item in issues:
                results.append({
                    "issueNumber": item.get("issueNumber", ""),
                    "number": item.get("number", 0),
                })
            return results if results else None
        except Exception as e:
            logger.error("fetch_draw_history error: %s", e)
            return None

    def fetch_open_issue(self, game_code="WinGo_30S"):
        time.sleep(1)
        try:
            url = f"{self.lottery_draw_base_url}/{game_code}/GetHistoryIssuePage.json"
            params = {"pageNum": 1, "pageSize": 1}
            resp = self.client.get(url, params=params, timeout=self.timeout, verify=self.verify_ssl)
            data = resp.json()
            issues = data.get("data", {}).get("list", []) if isinstance(data.get("data"), dict) else []
            if issues:
                latest_issue = issues[0].get("issueNumber", "")
                if latest_issue:
                    parts = str(latest_issue).split("-")
                    if len(parts) >= 2:
                        num = int(parts[-1])
                        next_num = num + 1
                        prefix = "-".join(parts[:-1])
                        return f"{prefix}-{next_num:04d}"
                    return str(latest_issue)
            return None
        except Exception as e:
            logger.error("fetch_open_issue error: %s", e)
            return None

    def place_dual_bet(self, issue_number, game_code, bs_pred, color_pred, bs_amount, color_amount):
        bs_content = f"BigSmall_{bs_pred.capitalize()}"
        color_content = f"Color_{color_pred.capitalize()}"
        results = {}
        try:
            bs_result = self.place_wingo_bet(issue_number, bs_amount, 1, bs_content, game_code)
            results["bs"] = bs_result
        except Exception as e:
            logger.error("BS bet error: %s", e)
            results["bs"] = {"error": str(e)}
        time.sleep(0.5)
        try:
            color_result = self.place_wingo_bet(issue_number, color_amount, 1, color_content, game_code)
            results["color"] = color_result
        except Exception as e:
            logger.error("Color bet error: %s", e)
            results["color"] = {"error": str(e)}
        return results

    def close(self):
        self.client.close()


# Prediction functions (same as JAI Club)
def predict_bs(pattern):
    if len(pattern) < 2:
        return "BIG", "DEFAULT"
    p = " ".join(pattern)
    rules = {
        "S S S B B B": "SMALL", "B B B S S S": "BIG",
        "B B S S B B": "BIG", "S S B B S S": "SMALL",
        "B S B S B S": "BIG", "S B S B S B": "SMALL",
    }
    if p in rules:
        return rules[p], "PATTERN"
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
    p = " ".join(pattern)
    rules = {
        "R R R G G G": "RED", "G G G R R R": "GREEN",
        "R R G G R R": "RED", "G G R R G G": "GREEN",
    }
    if p in rules:
        return rules[p], "PATTERN"
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

def result_to_bs(num):
    return "BIG" if num >= 5 else "SMALL"

def result_to_color(num):
    if num in {0, 5}:
        return "VIOLET"
    return "GREEN" if num in GREEN_NUMS else "RED"