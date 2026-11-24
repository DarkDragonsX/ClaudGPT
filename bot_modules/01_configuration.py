"""Open-source project | Original owner: Rad Lamine | Repository: https://github.com/RadLamine/ClaudGPT."""

                       
"""
بوت ذكاء اصطناعي لتيليجرام - جاهز للاستضافة على Render (الخطة المجانية)
طريقة التشغيل نفس main.py القديم: البوت في Thread + Flask + Keep Alive
"""
import os, io, re, time, html, sqlite3, threading, logging, subprocess, tempfile
import shutil, asyncio, base64, collections, glob, warnings, json, random, ast, operator
import math, ipaddress, socket, sys, zipfile, posixpath, hashlib, uuid, stat
import datetime as dt
from datetime import timezone, timedelta
from types import SimpleNamespace as NS
from urllib.parse import urlparse

import requests
import telebot
from telebot import types
from telebot import apihelper
from flask import Flask
from dotenv import load_dotenv
from groq import Groq
from PIL import Image
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass
try:
    import pillow_avif                                    
except Exception:
    pass

load_dotenv()


                         

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
ENV_AI_KEY = (os.getenv("AI_API_KEY") or os.getenv("GROQ_API_KEY") or "").strip()

AI_KEYS = []
for _k in [ENV_AI_KEY] + [x.strip() for x in (os.getenv("AI_API_KEYS") or "").split(",")]:
    if _k and _k not in AI_KEYS:
        AI_KEYS.append(_k)
MODEL_FALLBACKS = [x.strip() for x in os.getenv("MODEL_FALLBACKS", "").split(",") if x.strip()]
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "120"))
MAX_CONTINUATIONS = max(0, int(os.getenv("MAX_CONTINUATIONS", "10")))                                        
SITE_URL = (os.getenv("SITE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
BOT_NAME = os.getenv("BOT_NAME", "المساعد الذكي")


GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
LEADER_MODEL = os.getenv("LEADER_MODEL", "gemini-3.5-flash-lite")


AGENT_GROQ_KEYS = []

for _k in [os.getenv("AGENT_GROQ_API_KEY", "").strip()] + [
    x.strip() for x in (os.getenv("AGENT_GROQ_API_KEYS") or "").split(",")
]:
    if _k and _k not in AGENT_GROQ_KEYS:
        AGENT_GROQ_KEYS.append(_k)


AGENTS_MODEL = os.getenv("AGENTS_MODEL", "openai/gpt-oss-120b").strip()


AGENTS_REASONING_EFFORT = os.getenv(
    "AGENTS_REASONING_EFFORT", "high"
).strip().lower()

if AGENTS_REASONING_EFFORT not in ("low", "medium", "high"):
    AGENTS_REASONING_EFFORT = "high"


TEXT_MODEL = os.getenv("TEXT_MODEL", "qwen/qwen3.8-27b")
VISION_MODEL = os.getenv("VISION_MODEL", TEXT_MODEL)

CHAT_MODEL = os.getenv("CHAT_MODEL", "openai/gpt-oss-20b").strip() or TEXT_MODEL
CHAT_REASONING_EFFORT = os.getenv("CHAT_REASONING_EFFORT", "low").strip().lower()
if CHAT_REASONING_EFFORT not in ("low", "medium", "high"):
    CHAT_REASONING_EFFORT = "low"
STT_MODEL = os.getenv("STT_MODEL", "whisper-large-v3-turbo")
MAX_COMPLETION_TOKENS = min(16384, max(1024, int(os.getenv("MAX_COMPLETION_TOKENS", "16384"))))
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "none")

MEMORY_LIMIT = min(8000, max(1000, int(os.getenv("MEMORY_LIMIT", "8000"))))
MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "8000"))
MAX_FILE_BYTES = 10 * 1024 * 1024                                                                              
MAX_CODE_FILE_BYTES = min(60 * 1024, max(1, int(os.getenv("MAX_CODE_FILE_BYTES", str(60 * 1024)))))
MAX_IMAGE_BYTES = min(1024 * 1024, max(1, int(os.getenv("MAX_IMAGE_BYTES", str(1024 * 1024)))))
MAX_TEMP_STORAGE_BYTES = min(5 * 1024 * 1024, max(1, int(os.getenv("MAX_TEMP_STORAGE_BYTES", str(5 * 1024 * 1024)))))
MAX_OUTPUT_FILE_CHARS = min(3000000, max(1000, int(os.getenv("MAX_OUTPUT_FILE_CHARS", "1000000"))))
MAX_PDF_PAGES = min(100, max(1, int(os.getenv("MAX_PDF_PAGES", "100"))))
MAX_PDF_TEXT_CHARS = int(os.getenv("MAX_PDF_TEXT_CHARS", "300000"))
MAX_PDF_AI_CHARS = int(os.getenv("MAX_PDF_AI_CHARS", "100000"))
MAX_PDF_OCR_PAGES = min(MAX_PDF_PAGES, max(0, int(os.getenv("MAX_PDF_OCR_PAGES", "30"))))


MAX_ZIP_BYTES = min(5 * 1024 * 1024, int(os.getenv("MAX_ZIP_BYTES", str(5 * 1024 * 1024))))
MAX_PROJECT_FILE_BYTES = min(MAX_CODE_FILE_BYTES, int(os.getenv("MAX_PROJECT_FILE_BYTES", str(MAX_CODE_FILE_BYTES))))
MAX_PROJECT_FILES = int(os.getenv("MAX_PROJECT_FILES", "400"))
MAX_PROJECT_UNZIPPED = min(5 * 1024 * 1024, int(os.getenv("MAX_PROJECT_UNZIPPED", str(5 * 1024 * 1024))))
PROJECT_BATCH_CHARS = max(4000, int(os.getenv("PROJECT_BATCH_CHARS", "28000")))                          
PROJECT_MAX_CHARS = int(os.getenv("PROJECT_MAX_CHARS", "600000"))
PROJECT_AGENTS = max(1, int(os.getenv("PROJECT_AGENTS", "2")))                                          
PROJECT_WAIT_SEC = max(1, int(os.getenv("PROJECT_WAIT_SEC", "3")))                                                
PROJECT_MAX_FIX_FILES = int(os.getenv("PROJECT_MAX_FIX_FILES", "20"))


MAX_FILE_WORDS = max(500, int(os.getenv("MAX_FILE_WORDS", "15000")))
SAVED_FILE_CHARS = 400000                                                                     


QUEUE_MAX_WAITING = max(1, int(os.getenv("QUEUE_MAX_WAITING", "100")))
QUEUE_TASK_TIMEOUT = max(30, int(os.getenv("QUEUE_TASK_TIMEOUT", "900")))
CHAT_CONCURRENCY = max(1, int(os.getenv("CHAT_CONCURRENCY", "1")))
PROJECT_CONCURRENCY = max(1, int(os.getenv("PROJECT_CONCURRENCY", "1")))
CODE_EDIT_CONCURRENCY = max(1, int(os.getenv("CODE_EDIT_CONCURRENCY", "1")))
PDF_CONCURRENCY = max(1, int(os.getenv("PDF_CONCURRENCY", "1")))
REMBG_CONCURRENCY = max(1, int(os.getenv("REMBG_CONCURRENCY", "1")))
EMERGENCY_DISK_PCT = min(99.0, max(50.0, float(os.getenv("EMERGENCY_DISK_PCT", "88"))))
EMERGENCY_RAM_PCT = min(99.0, max(50.0, float(os.getenv("EMERGENCY_RAM_PCT", "90"))))
EMERGENCY_DB_PCT = min(99.0, max(50.0, float(os.getenv("EMERGENCY_DB_PCT", "88"))))
EMERGENCY_TEMP_PCT = min(99.0, max(1.0, float(os.getenv("EMERGENCY_TEMP_PCT", "85"))))
EMERGENCY_QUEUE_PCT = min(100.0, max(1.0, float(os.getenv("EMERGENCY_QUEUE_PCT", "85"))))

LITE_MAX_BATCHES = max(1, int(os.getenv("LITE_MAX_BATCHES", "2")))
LITE_MAX_FIX_FILES = max(1, int(os.getenv("LITE_MAX_FIX_FILES", "5")))
BMO_URL = os.getenv("BMO_URL", "https://t.me/dexwepbot")
CF_ACCOUNTS = []
_cid = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
_ctok = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
if _cid and _ctok:
    CF_ACCOUNTS.append((_cid, _ctok))
for _pair in (os.getenv("CLOUDFLARE_ACCOUNTS") or "").split(","):
    if ":" in _pair:
        _a, _t = [x.strip() for x in _pair.split(":", 1)]
        if _a and _t and (_a, _t) not in CF_ACCOUNTS:
            CF_ACCOUNTS.append((_a, _t))
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")
IMAGE_DAILY_LIMIT = max(1, int(os.getenv("IMAGE_DAILY_LIMIT", "3")))


USER_RETENTION_DAYS = int(os.getenv("USER_RETENTION_DAYS", "90"))
CHAT_RETENTION_DAYS = int(os.getenv("CHAT_RETENTION_DAYS", "30"))
DB_MAX_MB = int(os.getenv("DB_MAX_MB", "140"))
DB_MAX_MESSAGES = max(1000, int(os.getenv("DB_MAX_MESSAGES", "30000")))
DB_MAX_USERS = max(1000, int(os.getenv("DB_MAX_USERS", "50000")))
DB_MAX_REPORTS = max(100, int(os.getenv("DB_MAX_REPORTS", "5000")))


TZ_OFFSET_HOURS = int(os.getenv("TZ_OFFSET_HOURS", "1"))                         
LOCAL_TZ = timezone(timedelta(hours=TZ_OFFSET_HOURS))
CLEAN_HOUR = int(os.getenv("CLEAN_HOUR", "0"))                                     
CLEAN_INACTIVE_HOURS = int(os.getenv("CLEAN_INACTIVE_HOURS", "24"))                                   
CLEAN_GRACE_MIN = int(os.getenv("CLEAN_GRACE_MIN", "20"))                              

ENABLE_REACTIONS = os.getenv("ENABLE_REACTIONS", "1") == "1"
DONATE_AMOUNTS = (10, 50, 100, 500)                                               

CHANNEL_UPDATES = "@dexwep1"
CHANNEL_DEXWEP = "@dexwep2"
CHANNEL_UPDATES_URL = "https://t.me/dexwep1"
CHANNEL_DEXWEP_URL = "https://t.me/dexwep2"
_LOCKED_CHANNEL_DIGEST = "f3a7f38f1a4844641fd1c7a1b3be8d5fd0c22bf264b124b2caade3cbe86c6cc1"


def _verify_locked_channels():
    names = ("CHANNEL_UPDATES", "CHANNEL_DEXWEP", "CHANNEL_UPDATES_URL", "CHANNEL_DEXWEP_URL")
    values = [globals().get(name) for name in names]
    if any(value is None for value in values):
        raise RuntimeError("تم حذف إعداد قناة أساسية؛ تم إيقاف تشغيل البوت للحماية.")
    payload = "\n".join(str(value) for value in values).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != globals().get("_LOCKED_CHANNEL_DIGEST"):
        raise RuntimeError("تم تغيير قناة أساسية أو رابطها؛ تم إيقاف تشغيل البوت للحماية.")


def _parse_extra_channel(env_name, label):
    raw = (os.environ.get(env_name) or "").strip()
    if not raw:
        return None

    candidate = raw
    if raw.startswith("t.me/"):
        candidate = "https://" + raw
    if candidate.startswith(("https://", "http://")):
        parsed = urlparse(candidate)
        if parsed.netloc.lower() not in ("t.me", "www.t.me"):
            raise RuntimeError(f"قيمة {env_name} يجب أن تكون اسم قناة عامة أو رابط t.me.")
        candidate = parsed.path.strip("/")
        if "/" in candidate or not candidate:
            raise RuntimeError(f"رابط {env_name} غير صالح؛ استخدم رابط قناة عامة مثل https://t.me/channel.")

    username = candidate[1:] if candidate.startswith("@") else candidate
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", username):
        raise RuntimeError(f"قيمة {env_name} غير صالحة؛ استخدم @channel أو https://t.me/channel.")

    return {
        "chat_id": "@" + username,
        "url": "https://t.me/" + username,
        "label": label,
        "source": env_name,
    }


def required_subscription_channels():
    _verify_locked_channels()
    channels = [
        {"chat_id": CHANNEL_UPDATES, "url": CHANNEL_UPDATES_URL, "label": "قناة تحديثات البوت"},
        {"chat_id": CHANNEL_DEXWEP, "url": CHANNEL_DEXWEP_URL, "label": "قناة منصة dexwep"},
    ]
    seen = {str(item["chat_id"]).lower() for item in channels}
    extras = (
        _parse_extra_channel("CHANNEL_UPDATES", "القناة الإضافية الأولى"),
        _parse_extra_channel("CHANNEL_DEXWEP", "القناة الإضافية الثانية"),
    )
    for item in extras:
        if item and item["chat_id"].lower() not in seen:
            channels.append(item)
            seen.add(item["chat_id"].lower())
    return tuple(channels)


_verify_locked_channels()


Image.MAX_IMAGE_PIXELS = 25_000_000
warnings.simplefilter("error", Image.DecompressionBombWarning)

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN غير موجود في ملف .env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

apihelper.SESSION_TIME_TO_LIVE = 300
apihelper.RETRY_ON_ERROR = True
apihelper.RETRY_ENGINE = 2
apihelper.MAX_RETRIES = 5
apihelper.RETRY_TIMEOUT = 1
apihelper.CONNECT_TIMEOUT = 20
apihelper.READ_TIMEOUT = 60
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=12)
app = Flask(__name__)

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

