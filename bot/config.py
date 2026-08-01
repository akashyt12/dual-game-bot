import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
BOT_VERSION = os.getenv("BOT_VERSION", "Predictor 2.0")
CREATOR = os.getenv("CREATOR", "Lord Senku")
REFERRAL_POINTS = int(os.getenv("REFERRAL_POINTS", "50"))
REQUIRED_POINTS = int(os.getenv("REQUIRED_POINTS", "100"))
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR = Path(__file__).parent.parent / "images"
