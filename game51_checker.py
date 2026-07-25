#!/usr/bin/env python3
"""
51gamet.com Account Checker & Betting Engine
Full working: Login + Captcha Solve + Draw History + Place Bets
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

import requests
import urllib3
from PIL import Image, ImageFilter, ImageOps

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GREEN_NUMS = {1, 3, 5, 7, 9}
RED_NUMS = {0, 2, 4, 6, 8}


class Game51AccountChecker:
    def __init__(self, username: str, password: str):
        self.username = username.strip()
        self.password = password.strip()
        self.base_url = "https://51gamet.com"
        self.api_base_url = "https://api.api51gameapi.com"
        self.client = requests.Session()
        self.timeout = 25
        self.verify_ssl = False
        self.jwt_token: str | None = None
        self.token_header: str | None = None
        self.refresh_token: str | None = None
        self.auth_token_candidates: list[str] = []
        self.user_info: dict[str, Any] = {}
        self.status = "unknown"
        self.message = ""
        self._lottery_cache: dict[str, Any] = {}
        self._lottery_cache_time: float = 0

    def is_rate_limited(self, message: str | None) -> bool:
        text = (message or "").lower()
        return any(kw in text for kw in ("too frequent", "too many", "rate limit", "try again later"))

    def backoff_seconds(self, attempt: int) -> int:
        return min(90, 20 + (attempt * 15))

    def update_headers(self) -> None:
        self.client.headers.update({
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Mobile Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/json;charset=UTF-8",
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
        return hashlib.md5(f'{{"language":{language},"random":"{random_val}"}}'.encode()).hexdigest().upper()

    def generate_login_signature(self, params: dict[str, Any]) -> str:
        sig_fields = ["username", "captchaId", "pwd", "phonetype", "logintype", "deviceId", "language", "random"]
        filtered = {k: params[k] for k in sig_fields if k in params}
        parts = []
        for key in sorted(filtered.keys()):
            v = filtered[key]
            parts.append(f'"{key}":{v}' if isinstance(v, int) else f'"{key}":"{v}"')
        return hashlib.md5(("{" + ",".join(parts) + "}").encode()).hexdigest().upper()

    def generate_ar_signature_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        signed = dict(payload)
        signed["random"] = random.randint(100000000000, 999999999999)
        sign_params = {}
        for key in sorted(signed.keys()):
            value = signed[key]
            if key in {"signature"} or value is None or value == "":
                continue
            if isinstance(value, (dict, list)):
                continue
            sign_params[key] = 0 if value == 0 else value
        sign_str = json.dumps(sign_params, separators=(",", ":"), sort_keys=True)
        signed["signature"] = hashlib.md5(sign_str.encode()).hexdigest().upper()
        signed["timestamp"] = int(time.time())
        return signed

    def parse_json_response(self, response: requests.Response, api_name: str) -> dict[str, Any]:
        body = response.text.strip()
        if not body:
            raise RuntimeError(f"{api_name} empty response. HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError:
            raise RuntimeError(f"{api_name} non-JSON. HTTP {response.status_code}")

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
            raise RuntimeError(f"Network error for {endpoint}: {exc}") from exc

    def post_signed(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        signed = self.generate_ar_signature_payload(payload)
        self.update_headers()
        if self.jwt_token:
            self.client.headers["Authorization"] = f"Bearer {self.jwt_token}"
        response = self.post_api(endpoint, signed)
        return self.parse_json_response(response, endpoint)

    # ── Captcha System ──────────────────────────────────────────
    def b64img(self, b64_str: str) -> Image.Image | None:
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        try:
            return Image.open(io.BytesIO(base64.b64decode(b64_str))).convert("RGBA")
        except Exception as exc:
            logger.error("Image decode error: %s", exc)
            return None

    def solve_captcha_image(self, bg_b64: str, slider_b64: str) -> float | None:
        bg_img = self.b64img(bg_b64)
        slider_img = self.b64img(slider_b64)
        if bg_img is None or slider_img is None:
            return None

        alpha = slider_img.getchannel("A")
        bbox = alpha.point(lambda px: 255 if px > 15 else 0).getbbox()
        if bbox is None:
            return None

        piece = slider_img.crop(bbox)
        piece_mask = alpha.crop(bbox).point(lambda px: 255 if px > 15 else 0)
        py1 = bbox[1]
        pw, ph = piece.size

        bg_rgb = bg_img.convert("RGB")
        piece_rgb = piece.convert("RGB")
        bg_px = bg_rgb.load()
        piece_px = piece_rgb.load()
        mask_px = piece_mask.load()

        best_direct = (float("inf"), 0)
        for ox in range(0, bg_rgb.width - pw + 1):
            score = 0.0
            samples = 0
            for y in range(ph):
                for x in range(pw):
                    if mask_px[x, y] <= 0:
                        continue
                    br, bgr, bb = bg_px[ox + x, py1 + y]
                    pr, pgr, pb = piece_px[x, y]
                    score += abs(br - pr) + abs(bgr - pgr) + abs(bb - pb)
                    samples += 1
            if samples > 0:
                score /= samples
            if score < best_direct[0]:
                best_direct = (score, ox)

        bg_gray = bg_rgb.convert("L")
        piece_gray = piece_rgb.convert("L")
        bg_edges_img = ImageOps.autocontrast(bg_gray.filter(ImageFilter.FIND_EDGES))
        piece_edges_img = ImageOps.autocontrast(piece_gray.filter(ImageFilter.FIND_EDGES))
        bg_edges = bg_edges_img.load()
        piece_edges = piece_edges_img.load()

        best_edge = (float("inf"), 0)
        for ox in range(0, bg_rgb.width - pw + 1):
            score = 0.0
            samples = 0
            for y in range(ph):
                for x in range(pw):
                    if mask_px[x, y] <= 0:
                        continue
                    score += abs(bg_edges[ox + x, py1 + y] - piece_edges[x, y])
                    samples += 1
            if samples > 0:
                score /= samples
            if score < best_edge[0]:
                best_edge = (score, ox)

        best_x = best_direct[1] if best_direct[0] < best_edge[0] else best_edge[1]
        return best_x * (340.0 / bg_img.width)

    def generate_track(self, target_x: float) -> list[dict[str, int]]:
        tracks = []
        t = random.randint(80, 120)
        tracks.append({"x": 10, "y": random.randint(-3, 0), "t": t})
        total_steps = random.randint(35, 50)
        overshoot = random.randint(3, 8)
        final_x = target_x + overshoot
        for i in range(total_steps):
            progress = (i + 1) / total_steps
            if progress < 0.7:
                eased = (progress / 0.7) ** 0.5 * 0.85
            else:
                eased = 0.85 + 0.15 * (1 - ((1 - progress) / 0.3) ** 2)
            x = int(10 + (final_x - 10) * eased)
            t += random.randint(15, 35)
            tracks.append({"x": x, "y": random.randint(-2, 2), "t": t})
        for _ in range(random.randint(3, 6)):
            t += random.randint(20, 40)
            tracks.append({"x": int(target_x + random.randint(-1, 1)), "y": random.randint(-1, 1), "t": t})
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
                    self.message = data.get("msg") or f"Captcha code {data.get('code')}"
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
            target_x = self.solve_captcha_image(
                captcha_data.get("backgroundImage", ""),
                captcha_data.get("sliderImage", ""),
            )
            if target_x is None:
                self.status = "error"
                self.message = "Captcha solve failed."
                return False
            time.sleep(random.uniform(1.0, 2.5))
            random_val = hashlib.md5(f"{time.time()}{random.randint(100000, 999999)}".encode()).hexdigest()
            device_id = hashlib.md5(f"device_{time.time()}_{random.random()}".encode()).hexdigest()
            username_to_use = self.username if self.username.startswith("91") else f"91{self.username}"
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
            track = self.generate_track(target_x)
            now = datetime.now(timezone.utc)
            end = now + timedelta(milliseconds=track[-1]["t"])
            payload = {
                **login_params,
                "track": {
                    "backgroundImageWidth": 340,
                    "backgroundImageHeight": 212,
                    "sliderImageWidth": 68,
                    "sliderImageHeight": 212,
                    "startTime": now.isoformat().replace("+00:00", "Z"),
                    "endTime": end.isoformat().replace("+00:00", "Z"),
                    "tracks": track,
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
                    self.jwt_token = login_data.get("token")
                    self.token_header = login_data.get("tokenHeader")
                    self.refresh_token = login_data.get("refreshToken")
                    self.auth_token_candidates = self.extract_token_candidates(data)
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

    # ── API Methods (51gamet uses typeID, not gameCode) ──────────
    def fetch_user_info(self) -> dict[str, Any]:
        if not self.jwt_token:
            return {}
        try:
            data = self.post_signed("/api/webapi/GetUserInfo", {"language": 0})
            if data.get("code") == 0:
                self.user_info = data["data"]
        except Exception as exc:
            logger.error("Fetch user info error: %s", exc)
        return self.user_info

    def get_balance(self) -> float:
        user_info = self.fetch_user_info()
        if user_info:
            for key in ("amount", "balance", "money", "coin", "points"):
                if key in user_info:
                    try:
                        return float(user_info[key])
                    except (ValueError, TypeError):
                        pass
        return 0.0

    def fetch_wingo_type_list(self) -> list:
        try:
            data = self.post_signed("/api/webapi/GetTypeList", {"language": 0})
            if data.get("code") == 0:
                return data.get("data", [])
        except Exception as e:
            logger.error("Fetch WinGo types error: %s", e)
        return []

    def fetch_game_issue(self, type_id: int = 30) -> dict:
        try:
            data = self.post_signed("/api/webapi/GetGameIssue", {"typeID": type_id, "language": 0})
            if data.get("code") == 0:
                return data.get("data", {})
        except Exception as e:
            logger.error("Fetch game issue error: %s", e)
        return {}

    def fetch_draw_history(self, type_id: int = 30, page_size: int = 10) -> list:
        try:
            data = self.post_signed("/api/webapi/GetNoaverageEmerdList", {
                "typeID": type_id, "pageSize": page_size, "pageNo": 1, "language": 0,
            })
            if data.get("code") == 0:
                issues = data.get("data", {}).get("list", [])
                issues.sort(key=lambda x: x.get("issueNumber", ""), reverse=True)
                return issues
        except Exception as e:
            logger.error("Fetch draw history error: %s", e)
        return []

    def fetch_lottery_token(self, game_code: str = "WinGo_30S", force: bool = False) -> dict:
        now = time.time()
        if not force and self._lottery_cache and (now - self._lottery_cache_time) < 60:
            return self._lottery_cache
        for attempt in range(3):
            try:
                data = self.post_signed("/api/webapi/GetGameUrl", {
                    "gameCode": game_code,
                    "vendorCode": "ARLottery",
                    "returnUrl": self.base_url,
                    "deviceType": 1,
                })
                launch_url = ""
                if data.get("code") == 0:
                    d = data.get("data", {})
                    launch_url = d.get("url", "") if isinstance(d, dict) else str(d)
                if not launch_url:
                    if attempt < 2:
                        time.sleep(2)
                        continue
                    raise RuntimeError("Could not get lottery URL")
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(launch_url)
                query = parse_qs(parsed.query)
                token = (query.get("Token") or query.get("token") or [""])[0]
                if not token:
                    raise RuntimeError("Could not extract AR token")
                result = {"token": token, "lottery_api": f"{parsed.scheme}://{parsed.netloc}"}
                self._lottery_cache = result
                self._lottery_cache_time = now
                return result
            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                    continue
                raise

    def fetch_open_issue(self, type_id: int = 30) -> str | None:
        game_code_map = {30: "WinGo_30S", 1: "WinGo_1M", 2: "WinGo_3M", 3: "WinGo_5M", 4: "WinGo_10M"}
        game_code = game_code_map.get(type_id, "WinGo_30S")
        for base in ["draw.ar-lottery01.com", "draw.ar-lottery06.com"]:
            try:
                resp = requests.get(
                    f"https://{base}/WinGo/{game_code}/GetHistoryIssuePage.json?pageSize=1&pageNo=1",
                    timeout=8, verify=False,
                )
                data = resp.json()
                if data.get("code") == 0:
                    issues = data["data"]["list"]
                    if issues:
                        latest = issues[0]["issueNumber"]
                        prefix = str(latest)[:-3]
                        num = int(str(latest)[-3:]) + 1
                        return f"{prefix}{num:03d}"
            except Exception:
                continue
        issue_data = self.fetch_game_issue(type_id)
        if issue_data:
            return str(issue_data.get("issueNumber", ""))
        return None

    def place_wingo_bet(self, issue_number: str, type_id: int, amount: float,
                         bet_content: str, bet_multiple: int = 1) -> dict:
        game_code_map = {30: "WinGo_30S", 1: "WinGo_1M", 2: "WinGo_3M", 3: "WinGo_5M", 4: "WinGo_10M"}
        game_code = game_code_map.get(type_id, "WinGo_30S")

        for attempt in range(2):
            lottery = self.fetch_lottery_token(game_code, force=(attempt > 0))
            ar_token = lottery["token"]
            lottery_api = lottery["lottery_api"]

            payload = {
                "gameCode": game_code,
                "issueNumber": issue_number,
                "amount": amount,
                "betMultiple": bet_multiple,
                "betContent": bet_content,
                "language": "en",
                "random": random.randint(100000000000, 999999999999),
            }
            sign_params = {}
            for key in sorted(payload.keys()):
                val = payload[key]
                if val is None or val == "" or key in ("signature",):
                    continue
                sign_params[key] = val
            sign_str = json.dumps(sign_params, separators=(",", ":"), sort_keys=True)
            payload["signature"] = hashlib.md5(sign_str.encode()).hexdigest().upper()
            payload["timestamp"] = int(time.time())

            headers = {
                "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
                "Content-Type": "application/json;charset=UTF-8",
                "Authorization": f"Bearer {ar_token}",
                "Origin": lottery_api,
                "Referer": f"{lottery_api}/",
            }
            try:
                import urllib3 as _urllib3
                _urllib3.disable_warnings(_urllib3.exceptions.InsecureRequestWarning)
                resp = requests.post(
                    f"{lottery_api}/api/Lottery/WinGoBet",
                    json=payload, headers=headers, timeout=15, verify=False,
                )
                if resp.status_code == 401 and attempt == 0:
                    self._lottery_cache = {}
                    self._lottery_cache_time = 0
                    continue
                data = self.parse_json_response(resp, "WinGoBet")
                if data.get("code") != 0:
                    raise RuntimeError(data.get("msg") or "Bet failed")
                return data
            except requests.RequestException as exc:
                if "401" in str(exc) and attempt == 0:
                    self._lottery_cache = {}
                    self._lottery_cache_time = 0
                    continue
                raise RuntimeError(f"Lottery bet error: {exc}") from exc
        raise RuntimeError("Bet failed after retries")

    def place_dual_bet(self, issue_number: str, type_id: int,
                       bs_bet: float, color_bet: float,
                       bs_content: str, color_content: str) -> dict:
        game_code_map = {30: "WinGo_30S", 1: "WinGo_1M", 2: "WinGo_3M", 3: "WinGo_5M", 4: "WinGo_10M"}
        game_code = game_code_map.get(type_id, "WinGo_30S")

        lottery = self.fetch_lottery_token(game_code)
        ar_token = lottery["token"]
        lottery_api = lottery["lottery_api"]

        auth_modes = ["bearer", "authorization", "token", "x-token"]
        fallback_urls = [lottery_api, "https://h5.ar-lottery06.com"]

        results = {}
        for label, amount, content in [("bs", bs_bet, bs_content), ("color", color_bet, color_content)]:
            payload = {
                "gameCode": game_code,
                "issueNumber": issue_number,
                "amount": amount,
                "betMultiple": 1,
                "betContent": content,
                "language": "en",
                "random": random.randint(100000000000, 999999999999),
            }

            bet_result = None
            for base_url in fallback_urls:
                if bet_result is not None:
                    break
                for attempt in range(2):
                    if attempt > 0:
                        lottery = self.fetch_lottery_token(game_code, force=True)
                        ar_token = lottery["token"]
                        base_url = lottery["lottery_api"]
                    signed = self.generate_ar_signature_payload(payload)
                    for auth_mode in auth_modes:
                        try:
                            self.update_headers()
                            token_val = ar_token.replace("Bearer ", "") if ar_token.lower().startswith("bearer ") else ar_token
                            if auth_mode == "bearer":
                                self.client.headers["Authorization"] = f"Bearer {token_val}"
                            elif auth_mode == "authorization":
                                self.client.headers["Authorization"] = token_val
                            elif auth_mode == "token":
                                self.client.headers["Token"] = token_val
                            elif auth_mode == "x-token":
                                self.client.headers["X-Token"] = token_val
                            self.client.headers["Origin"] = base_url
                            self.client.headers["Referer"] = f"{base_url}/"
                            resp = self.client.post(
                                f"{base_url}/api/Lottery/WinGoBet",
                                json=signed, timeout=10, allow_redirects=True, verify=False,
                            )
                            if resp.status_code == 403:
                                logger.warning("51GAME 403 on %s mode=%s, trying next", base_url, auth_mode)
                                continue
                            if resp.status_code == 401:
                                break
                            data = self.parse_json_response(resp, "WinGoBet")
                            bet_result = data
                            break
                        except Exception as e:
                            logger.error("51GAME bet attempt error: %s", e)
                            continue
            results[label] = bet_result or {"error": "All bet attempts failed"}
            time.sleep(0.1)

        return results

    def close(self):
        self.client.close()


# ── Prediction System ───────────────────────────────────────
def predict_bs(pattern: list[str]) -> tuple[str, str]:
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
    if b >= 5:
        return "SMALL", "5X REVERSAL"
    if s >= 5:
        return "BIG", "5X REVERSAL"
    if b >= 4:
        return "SMALL", "4X REVERSAL"
    if s >= 4:
        return "BIG", "4X REVERSAL"
    if pattern[-3:] == ["B", "B", "B"]:
        return "BIG", "3X TREND"
    if pattern[-3:] == ["S", "S", "S"]:
        return "SMALL", "3X TREND"
    if pattern[-2:] == ["B", "B"]:
        return "BIG", "2X TREND"
    if pattern[-2:] == ["S", "S"]:
        return "SMALL", "2X TREND"
    if b > s:
        return "BIG", "COUNT"
    elif s > b:
        return "SMALL", "COUNT"
    return "BIG", "TIE"


def predict_color(pattern: list[str]) -> tuple[str, str]:
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
    if r >= 5:
        return "GREEN", "5X REVERSAL"
    if g >= 5:
        return "RED", "5X REVERSAL"
    if r >= 4:
        return "GREEN", "4X REVERSAL"
    if g >= 4:
        return "RED", "4X REVERSAL"
    if pattern[-3:] == ["R", "R", "R"]:
        return "RED", "3X TREND"
    if pattern[-3:] == ["G", "G", "G"]:
        return "GREEN", "3X TREND"
    if pattern[-2:] == ["R", "R"]:
        return "RED", "2X TREND"
    if pattern[-2:] == ["G", "G"]:
        return "GREEN", "2X TREND"
    if r > g:
        return "RED", "COUNT"
    elif g > r:
        return "GREEN", "COUNT"
    return "RED", "TIE"


def result_to_bs(number: int) -> str:
    return "BIG" if number >= 5 else "SMALL"


def result_to_color(number: int) -> str:
    if number in GREEN_NUMS:
        return "GREEN"
    elif number in RED_NUMS:
        return "RED"
    return "VIOLET"


def generate_bet_content(bet_type: str, selection: str) -> str:
    if bet_type == "color":
        bet_map = {"RED": "1", "GREEN": "2", "VIOLET": "3"}
        return bet_map.get(selection, "1")
    elif bet_type == "number":
        return str(int(selection))
    elif bet_type == "bigsmall":
        return "5" if selection == "BIG" else "6"
    elif bet_type == "oddEven":
        return "7" if selection == "ODD" else "8"
    return "1"


# ── CLI Mode ────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  51gamet.com Auto-Bet Bot (Full Working)")
    print("=" * 50)
    username = input("Username (phone): ").strip()
    password = input("Password: ").strip()

    checker = Game51AccountChecker(username, password)

    print("\n🔐 Logging in...")
    if not checker.perform_login():
        print(f"❌ Login Failed: {checker.message}")
        exit(1)

    print(f"✅ Login Success!")
    balance = checker.get_balance()
    print(f"💰 Balance: ₹{balance}")

    types = checker.fetch_wingo_type_list()
    print(f"\n🎮 Available Games:")
    for t in types:
        print(f"  [{t['typeID']}] {t['typeName']} ({t['intervalM']}min)")

    type_id = int(input("\nSelect Game Type ID (e.g. 30): ") or "30")

    print(f"\n📊 Fetching draws for typeID={type_id}...")
    history = checker.fetch_draw_history(type_id, page_size=20)
    if history:
        print(f"  Last {len(history)} draws:")
        for h in history[:10]:
            num = int(h.get("number", 0))
            color = h.get("colour", "")
            bs = "BIG" if num >= 5 else "SMALL"
            print(f"  #{h['issueNumber']}: {num} [{color}] {bs}")

    issue = checker.fetch_game_issue(type_id)
    if issue:
        print(f"\n🎯 Current Issue: #{issue.get('issueNumber')}")
        print(f"  Start: {issue.get('startTime')}")
        print(f"  End: {issue.get('endTime')}")

    print(f"\n🤖 Auto-Bet Settings:")
    bet_type = input("Bet type (color/number/bigsmall/oddEven): ").strip() or "color"
    selection = input("Selection (RED/GREEN/0-9/BIG/SMALL/ODD/EVEN): ").strip() or "RED"
    base_amount = float(input("Base amount: ") or "10")
    levels = int(input("Max levels: ") or "5")
    multiplier = float(input("Multiplier: ") or "2.0")

    print(f"\n🚀 Starting auto-bet...")
    print(f"  Type: {bet_type}, Selection: {selection}")
    print(f"  Base: ₹{base_amount}, Levels: {levels}, Multiplier: {multiplier}")

    current_level = 0
    total_profit = 0
    consecutive_losses = 0

    while current_level < levels:
        try:
            issue = checker.fetch_game_issue(type_id)
            if not issue:
                time.sleep(1)
                continue

            issue_num = str(issue.get("issueNumber", ""))
            amount = base_amount * (multiplier ** current_level)
            bet_content = generate_bet_content(bet_type, selection)

            print(f"\n  📍 Issue #{issue_num} | Level {current_level+1} | ₹{amount:.0f} on {selection}")

            try:
                result = checker.place_wingo_bet(issue_num, type_id, amount, bet_content)
                print(f"  ✅ Bet placed!")
            except Exception as e:
                print(f"  ❌ Bet error: {e}")
                time.sleep(2)
                continue

            # Wait for result
            print(f"  ⏳ Waiting for result...")
            time.sleep(65)

            history = checker.fetch_draw_history(type_id, page_size=1)
            if history:
                last = history[0]
                num = int(last.get("number", 0))
                color = last.get("colour", "")
                bs = "BIG" if num >= 5 else "SMALL"

                win = False
                if bet_type == "color" and selection.lower() in color.lower():
                    win = True
                elif bet_type == "bigsmall" and selection == bs:
                    win = True
                elif bet_type == "number" and str(num) == selection:
                    win = True

                if win:
                    win_amount = amount * 2
                    profit = win_amount - amount
                    total_profit += profit
                    consecutive_losses = 0
                    print(f"  🎉 WON! #{issue_num}: {num} [{color}] {bs} | +₹{profit:.0f}")
                    current_level = 0
                else:
                    loss = amount
                    total_profit -= loss
                    consecutive_losses += 1
                    print(f"  😢 LOST. #{issue_num}: {num} [{color}] {bs} | -₹{loss:.0f}")
                    current_level += 1

                print(f"  📊 Profit: ₹{total_profit:.0f} | Level: {current_level+1}/{levels}")

            balance = checker.get_balance()
            print(f"  💰 Balance: ₹{balance}")

            if current_level >= levels:
                print(f"\n  ⚠️ Max levels reached! Resetting...")
                current_level = 0
                time.sleep(5)

        except KeyboardInterrupt:
            print(f"\n\n🛑 Stopped. Total Profit: ₹{total_profit:.0f}")
            break
        except Exception as e:
            print(f"  ⚠️ Error: {e}")
            time.sleep(3)

    print(f"\n📊 Session Summary:")
    print(f"  Total Profit: ₹{total_profit:.0f}")
    print(f"  Final Balance: ₹{checker.get_balance():.0f}")
    checker.close()
