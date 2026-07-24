#!/usr/bin/env python3
"""
Jai Club Bot Runner – Auto-restart + Logging + Config
"""
import json
import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "bot_config.json"
LOG_DIR = Path(__file__).parent / "logs"
BOT_SCRIPT = Path(__file__).parent / "JAI_CLUB_BOT.py"

def load_config():
    if not CONFIG_FILE.exists():
        print(f"Config not found: {CONFIG_FILE}")
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        return json.load(f)

def ensure_log_dir():
    LOG_DIR.mkdir(exist_ok=True)

def get_log_file():
    date_str = datetime.now().strftime("%Y-%m-%d")
    return LOG_DIR / f"bot_{date_str}.log"

def run_bot():
    config = load_config()
    ensure_log_dir()
    log_file = get_log_file()

    username = config.get("username", "")
    password = config.get("password", "")

    if not username or not password:
        print("Set username/password in bot_config.json first!")
        username = input("Username: ").strip()
        password = input("Password: ").strip()
        if not username or not password:
            print("Credentials required.")
            return 1
        config["username"] = username
        config["password"] = password
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)

    game = config.get("game", "1")
    total_bet = config.get("total_bet", 2)
    multiplier = config.get("multiplier", 2.0)
    confidence = config.get("confidence", 55)
    auto_restart = config.get("auto_restart", True)
    max_restarts = config.get("max_restarts", 10)

    restart_count = 0

    while restart_count < max_restarts:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{timestamp}] Starting bot (attempt {restart_count + 1}/{max_restarts})")
        print(f"Log: {log_file}")

        try:
            env = os.environ.copy()
            env["JAI_USERNAME"] = username
            env["JAI_PASSWORD"] = password

            process = subprocess.Popen(
                [sys.executable, str(BOT_SCRIPT)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                cwd=str(BOT_SCRIPT.parent)
            )

            with open(log_file, "a") as log:
                log.write(f"\n{'='*60}\n")
                log.write(f"[{timestamp}] Bot started (attempt {restart_count + 1})\n")
                log.write(f"{'='*60}\n")

                for line in process.stdout:
                    print(line, end="")
                    log.write(line)
                    log.flush()

            exit_code = process.wait()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{timestamp}] Bot exited with code: {exit_code}")

            with open(log_file, "a") as log:
                log.write(f"\n[{timestamp}] Bot exited with code: {exit_code}\n")

            if exit_code == 0 or exit_code == 130:
                print("Clean exit. Stopping.")
                break

            if not auto_restart:
                print("Auto-restart disabled. Stopping.")
                break

            restart_count += 1
            if restart_count < max_restarts:
                wait_time = min(30, 5 * restart_count)
                print(f"Restarting in {wait_time} seconds...")
                time.sleep(wait_time)

        except KeyboardInterrupt:
            print("\nStopped by user.")
            break
        except Exception as e:
            print(f"Error: {e}")
            restart_count += 1
            if restart_count < max_restarts:
                time.sleep(5)

    print(f"Bot stopped after {restart_count} restarts.")
    return 0

if __name__ == "__main__":
    sys.exit(run_bot())
