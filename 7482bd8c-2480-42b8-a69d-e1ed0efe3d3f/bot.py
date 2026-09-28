#!/usr/bin/env python3
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ShortnerBypass — Production-Ready Telegram Auto Link Bypass Bot
  Developer & Updates: @ProviderBotz
  Features:
    - Real Colored Inline Buttons (Bot API 9.4+ ButtonStyle: PRIMARY, SUCCESS, DANGER)
    - Telethon Userbot (DZHQ Group Flow + Alex DM Flow)
    - Dynamic Auto-Generated PUBLIC_URL
    - Promo/Ad Links Stripped (Preserving valid t.me destinations)
    - Obsidian Red Telegram Mini App + Flask Server
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import time
import re
import html
import json
import uuid
import secrets
import logging
import asyncio
import threading
import urllib.parse
from enum import Enum
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional, Dict, Any, List, Tuple, Union

import aiohttp
from flask import Flask, request, jsonify, send_file
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.network.connection.tcpabridged import ConnectionTcpAbridged
from telethon.tl.types import MessageEntityUrl, MessageEntityTextUrl

# ══════════════════════════════════════════════════════════════
#  ENV LOADER (.env support)
# ══════════════════════════════════════════════════════════════
def load_env(path: str = ".env"):
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass

load_env()

# ══════════════════════════════════════════════════════════════
#  CONFIGURATION & DYNAMIC AUTO-URL GENERATION
# ══════════════════════════════════════════════════════════════
DEVELOPER = "@ProviderBotz"
BRAND_NAME = "ProviderBotz"
OFFICIAL_CHANNEL = "https://t.me/ProviderBotz"

# Public Bot Credentials
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8678804822:AAHgPfZQBwx5P1bodAcQCdYtR6WMn6yucbY").strip()
BOT_USERNAME = os.environ.get("BOT_USERNAME", "TheLinkzoBot").strip().lstrip("@")
OWNER_ID_RAW = os.environ.get("OWNER_ID", "7931847651").strip()
OWNER_ID = int(OWNER_ID_RAW) if OWNER_ID_RAW.isdigit() else None

# Telethon Userbot Credentials
TELEGRAM_API_ID_RAW = os.environ.get("TELEGRAM_API_ID", "36805393").strip()
TELEGRAM_API_ID = int(TELEGRAM_API_ID_RAW) if TELEGRAM_API_ID_RAW.isdigit() else 0
TELEGRAM_API_HASH = os.environ.get("TELEGRAM_API_HASH", "cfd5ff24d915c1691d88b0f3b51b96f5").strip()
TELEGRAM_SESSION = os.environ.get("TELEGRAM_SESSION", "1BVtsOIEBu8XGF6y9Vp-7TSbgzqjs3xLUbM08joW34XJWMUsyv5BLt0hR5eqiZ5VDZ4qVwwBT2q6tbsiWp36BskZFR9pS82-ZM-dSJS4MrGNqgKUoWVdtLApLR7q_dgP3lLbB3Dz5bCFgjTq_5Kozqp5qetXSPcnB0s1T0il-6DCFW3tsYHPNcG7aeySrRCdT7Km6aeDFoMf56_g3BXR9EIkCvWY8lL7d59M7M66GaW7y3xLm_ZD1PZBrNLb3So45v3Va6VtndaryhtR4KqPq_dUV6xqbitSC7Hd2PED-Di4izNutICVSeFrNsFhjhikZk0S5cDvUJkrVfVQ1B5ub840Eck0vHrU=").strip()

# External Bypass Bots (Only DZHQ Group & Alex DM allowed)
DZHQ_BOT = os.environ.get("DZHQ_BOT_USERNAME", "@DZHQ_BypassBot").strip()
DZHQ_GROUP = -1003644908415  # Dedicated Telegram Group for DZHQ
ALEX_BOT = os.environ.get("ALEX_BOT_USERNAME", "@alexbypassbot").strip()

# Web Server & Port Configuration
PORT = int(os.environ.get("PORT", "5000"))
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ProviderPro").strip()

# Dynamic Public URL Detection
_CURRENT_PUBLIC_URL: Optional[str] = None

def get_auto_public_url() -> str:
    """Return the dynamically resolved public URL for the Mini App and webhooks."""
    global _CURRENT_PUBLIC_URL
    if _CURRENT_PUBLIC_URL and not _CURRENT_PUBLIC_URL.startswith("http://localhost"):
        return _CURRENT_PUBLIC_URL

    env_public = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
    if env_public and not env_public.startswith("http://localhost"):
        _CURRENT_PUBLIC_URL = env_public
        return _CURRENT_PUBLIC_URL

    app_url = os.environ.get("APP_URL", "").strip().rstrip("/")
    if app_url:
        _CURRENT_PUBLIC_URL = app_url
        return _CURRENT_PUBLIC_URL

    render_url = os.environ.get("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if render_url:
        _CURRENT_PUBLIC_URL = render_url
        return _CURRENT_PUBLIC_URL

    railway_url = os.environ.get("RAILWAY_STATIC_URL", "").strip().rstrip("/") or os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip().rstrip("/")
    if railway_url:
        if not railway_url.startswith("http"):
            railway_url = f"https://{railway_url}"
        _CURRENT_PUBLIC_URL = railway_url
        return _CURRENT_PUBLIC_URL

    koyeb_url = os.environ.get("KOYEB_PUBLIC_DOMAIN", "").strip().rstrip("/")
    if koyeb_url:
        if not koyeb_url.startswith("http"):
            koyeb_url = f"https://{koyeb_url}"
        _CURRENT_PUBLIC_URL = koyeb_url
        return _CURRENT_PUBLIC_URL

    return f"http://localhost:{PORT}"

# Timeouts
BYPASS_IDLE_TIMEOUT_SEC = float(os.environ.get("BYPASS_IDLE_TIMEOUT_SEC", "30"))
ALEX_DM_TIMEOUT_SEC = float(os.environ.get("ALEX_DM_TIMEOUT_SEC", "75"))
MAX_BYPASS_TIMEOUT_SEC = float(os.environ.get("MAX_BYPASS_TIMEOUT_SEC", "120"))

# Rate Limiting & User Concurrency
RATE_LIMIT_SECONDS = float(os.environ.get("RATE_LIMIT_SECONDS", "3"))
MAX_CONCURRENT_PER_USER = int(os.environ.get("MAX_CONCURRENT_PER_USER", "2"))
TRACE_BOTS = os.environ.get("TRACE_BOTS", "false").lower() in ("true", "1", "yes")

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("ProviderBotz")
logging.getLogger("telethon").setLevel(logging.WARNING)

# ══════════════════════════════════════════════════════════════
#  PYROGRAM & BOT API 9.4+ REAL COLORED BUTTON STYLE SYSTEM
# ══════════════════════════════════════════════════════════════
class ButtonStyle(str, Enum):
    """
    Telegram Bot API 9.4+ Native Colored Button Styles:
    - PRIMARY: 🔵 Dark Blue / Accent (bg_primary)
    - SUCCESS: 🟢 Green (bg_success)
    - DANGER:  🔴 Red (bg_danger)
    """
    PRIMARY = "primary"  # 🔵 Dark Blue / Accent
    SUCCESS = "success"  # 🟢 Green
    DANGER = "danger"    # 🔴 Red

class InlineKeyboardButton:
    """Inline Keyboard Button supporting Bot API 9.4+ native colors and Pyrogram syntax."""
    def __init__(
        self,
        text: str,
        url: Optional[str] = None,
        callback_data: Optional[str] = None,
        web_app: Optional[Dict[str, str]] = None,
        style: Optional[Union[ButtonStyle, str]] = None
    ):
        self.text = text
        self.url = url
        self.callback_data = callback_data
        self.web_app = web_app
        if isinstance(style, ButtonStyle):
            self.style = style.value
        else:
            self.style = style

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"text": self.text}
        if self.url:
            d["url"] = self.url
        if self.callback_data:
            d["callback_data"] = self.callback_data
        if self.web_app:
            d["web_app"] = self.web_app
        if self.style:
            d["style"] = self.style
        return d

class InlineKeyboardMarkup:
    """Inline Keyboard Markup containing rows of InlineKeyboardButtons."""
    def __init__(self, inline_keyboard: List[List[InlineKeyboardButton]]):
        self.inline_keyboard = inline_keyboard

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inline_keyboard": [
                [btn.to_dict() if isinstance(btn, InlineKeyboardButton) else btn for btn in row]
                for row in self.inline_keyboard
            ]
        }

# ══════════════════════════════════════════════════════════════
#  MANDATORY SMALL-CAPS UNICODE ALPHABET
#  ᴧ ʙ ᴄ ᴅ є ꜰ ɢ ʜ ι ᴊ ᴋ ʟ ᴍ ɴ σ ᴩ ǫ ʀ ѕ т υ ν ω ᥊ ʏ ᴢ
# ══════════════════════════════════════════════════════════════
SMALL_CAPS_MAP = {
    'a': 'ᴧ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'є', 'f': 'ꜰ',
    'g': 'ɢ', 'h': 'ʜ', 'i': 'ι', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ',
    'm': 'ᴍ', 'n': 'ɴ', 'o': 'σ', 'p': 'ᴩ', 'q': 'ǫ', 'r': 'ʀ',
    's': 'ѕ', 't': 'т', 'u': 'υ', 'v': 'ν', 'w': 'ω', 'x': '᥊',
    'y': 'ʏ', 'z': 'ᴢ',
    'A': 'ᴧ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'є', 'F': 'ꜰ',
    'G': 'ɢ', 'H': 'ʜ', 'I': 'ι', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ',
    'M': 'ᴍ', 'N': 'ɴ', 'O': 'σ', 'P': 'ᴩ', 'Q': 'ǫ', 'R': 'ʀ',
    'S': 'ѕ', 'T': 'т', 'U': 'υ', 'V': 'ν', 'W': 'ω', 'X': '᥊',
    'Y': 'ʏ', 'Z': 'ᴢ'
}

def to_small_caps(text: str) -> str:
    """Transform string into the mandatory ProviderBotz small-caps font."""
    return "".join(SMALL_CAPS_MAP.get(c, c) for c in text)

def _trace(provider: str, message: str):
    if TRACE_BOTS:
        logger.info(f"[TRACE][{provider}] {message}")

# ══════════════════════════════════════════════════════════════
#  PROMO & JUNK URL FILTERING (ALLOWING LEGITIMATE T.ME DESTINATIONS)
# ══════════════════════════════════════════════════════════════
_PROMO_USERNAMES = {
    "dzhqbypass",
    "dzhq_official",
    "dzhq_bypassbot",
    "alexmodz",
    "alexbypassbot",
    "apkamitrr",
    "nick_bypass_bot"
}

def clean_url(u: str) -> str:
    """Normalize extracted URLs and remove sentence punctuation from edges."""
    if not u:
        return ""
    cleaned = re.sub(r'[\*`\'\"✔️✅]+', '', u).strip()
    return cleaned.rstrip('.,;:!?)>]\'"}').strip()

def normalize_for_comparison(u: str) -> str:
    """Normalize URL for identical comparison (strips scheme and trailing slash)."""
    if not u:
        return ""
    u = clean_url(u).lower()
    u = re.sub(r'^https?://', '', u)
    u = re.sub(r'^www\.', '', u)
    return u.rstrip('/')

def is_same_url(u1: str, u2: str) -> bool:
    """Check if two URLs resolve to the exact same link."""
    n1 = normalize_for_comparison(u1)
    n2 = normalize_for_comparison(u2)
    if not n1 or not n2:
        return False
    return n1 == n2

def is_valid_bypassed_destination(url: str, original_url: str) -> bool:
    """
    Strictly verifies that a candidate URL is a true final bypassed destination.
    Allows ALL legitimate destination domains (including valid t.me posts/files/bots,
    mega.nz, Google Drive, direct links), while strictly filtering out:
    - Identical input links
    - Telegram share action buttons
    - External bypass providers' own promotional ads and channels
    """
    if not url or not url.startswith(("http://", "https://")):
        return False
    if is_same_url(url, original_url):
        return False

    try:
        parsed = urllib.parse.urlsplit(url)
        host = (parsed.hostname or "").lower()
        path = parsed.path.strip("/")

        # 1. Reject Telegram share intent action links
        if "share/url" in url.lower():
            return False

        # 2. Handle Telegram URLs (t.me, telegram.me, telegram.dog)
        if any(tg_host in host for tg_host in ("t.me", "telegram.me", "telegram.dog")):
            segments = [s.lower() for s in path.split("/") if s]
            if segments:
                first_seg = segments[0].lstrip("@")
                # Reject only known external provider promo channels & bots
                if first_seg in _PROMO_USERNAMES:
                    return False
            # Valid Telegram destinations:
            # - t.me/c/... (Private channel/group file)
            # - t.me/ChannelName/123 (Public channel post/file)
            # - t.me/SomeBot?start=xyz (Bot download link)
            # - t.me/+InviteCode (Private invite link)
            return True

        # 3. Reject provider promo websites
        if any(promo in host for promo in ("dzhq", "alexmodz")):
            return False

        return True
    except Exception:
        return False

def extract_valid_urls_from_text(text: str, original_url: str = "") -> List[str]:
    """Extract valid http/https URLs from a block of text, stripping promo links."""
    if not text:
        return []
    raw_urls = re.findall(r'https?://[^\s\n\)\]>"\']+', text)
    result = []
    for r in raw_urls:
        c = clean_url(r)
        if is_valid_bypassed_destination(c, original_url):
            if c not in result:
                result.append(c)
    return result

# ══════════════════════════════════════════════════════════════
#  PARSERS (DZHQ GROUP & ALEX DM)
# ══════════════════════════════════════════════════════════════

# DZHQ Regexes
_RX_IN = re.compile(r'In\s+Link[^:\n]*?:-\s*\*{0,4}\s*(https?://[^\s*\n]+)', re.I)
_RX_GOT = re.compile(r'Got\s+Result[^:\n]*?:-\s*\*{0,4}\s*(https?://[^\s*\n]+)', re.I)
_RX_ERR = re.compile(
    r'invalid\s*link|not\s*support|unsupported|no\s*script|not\s*found|'
    r'error|failed|cannot|wrong|sorry|got\s+error',
    re.I
)
_RX_RATE = re.compile(r'rate\s*limit|flood|wait\s*\d+|try\s*again', re.I)
_RX_INTERMEDIATE = re.compile(
    r'^[\*\s]*bypass(?:ing)?\.{0,6}[\*\s]*$'
    r'|^[\*\s]*processing\.{0,6}[\*\s]*$'
    r'|^[\*\s]*please\s*wait[\*\s]*$'
    r'|^[\*\s]*fetching[\*\s]*$'
    r'|^[\*\s]*checking[\*\s]*$'
    r'|bypassing\.\.\.'
    r'|processing\.\.\.'
    r'|checking link\.\.\.'
    r'|almost done\.\.\.'
    r'|bypass started',
    re.I | re.M
)
_RX_GOT_ERR = re.compile(r'Got\s+Error[^:\n]*?:-\s*[`*\s]*(.*?)\s*[`*]*\s*$', re.I | re.M)
_RX_SEP = re.compile(r'━{3,}.*?✦.*?━{3,}')

def parse_dzhq_message(text: str, entities: list, sent_link: str) -> List[Dict[str, Any]]:
    """Parse DZHQ bot Telegram group response, rejecting promo links."""
    if not text:
        return [{"status": "empty"}]
    stripped = text.strip()

    if _RX_INTERMEDIATE.search(stripped) and len(stripped) < 200:
        return [{"status": "intermediate", "raw": stripped[:80]}]

    if _RX_RATE.search(text):
        return [{"status": "rate_limit", "error": "Rate limited by DZHQ bot"}]

    if _RX_ERR.search(text):
        err_m = _RX_GOT_ERR.search(text)
        clean_err = clean_url(err_m.group(1)) if err_m else stripped[:120]
        return [{"status": "failed", "error": clean_err}]

    ent_urls = []
    if entities:
        for ent in entities:
            off = getattr(ent, 'offset', None)
            lng = getattr(ent, 'length', None)
            url = getattr(ent, 'url', None)
            if not url:
                if isinstance(ent, MessageEntityUrl) and off is not None and lng:
                    url = text[off:off + lng]
                else:
                    continue
            url = clean_url(url)
            if is_valid_bypassed_destination(url, sent_link):
                ent_urls.append((url, url))

    results = []
    blocks = _RX_SEP.split(text)
    blocks = [b.strip() for b in blocks if b.strip()]
    for block in blocks:
        if 'Powered By' in block and 'DZHQBypass' in block and len(block) < 80:
            continue
        r = _parse_dzhq_block(block, ent_urls, sent_link)
        if r:
            results.append(r)

    if not results:
        r = _parse_dzhq_block(text, ent_urls, sent_link)
        if r:
            results.append(r)

    if not results:
        return [{"status": "no_link", "error": "No valid bypassed link found", "raw": text[:300]}]
    return results

def _parse_dzhq_block(block: str, ent_urls: list, sent_link: str) -> Optional[Dict[str, Any]]:
    original = None

    m_in = _RX_IN.search(block)
    if m_in:
        original = clean_url(m_in.group(1))

    # Priority 1: Exact "Got Result :-" link is the ONLY authentic destination
    m_got = _RX_GOT.search(block)
    if m_got:
        u = clean_url(m_got.group(1))
        if is_valid_bypassed_destination(u, sent_link):
            return {
                "status": "ok",
                "original": original or sent_link,
                "bypassed": u,
                "all_bypassed": [u]
            }

    # Priority 2: Fallback only if no Got Result pattern matched
    bypassed = []
    for _, url in ent_urls:
        if is_valid_bypassed_destination(url, sent_link) and url not in bypassed:
            bypassed.append(url)

    if not bypassed:
        for u in extract_valid_urls_from_text(block, sent_link):
            if u not in bypassed:
                bypassed.append(u)

    if not bypassed:
        return None

    return {
        "status": "ok",
        "original": original or sent_link,
        "bypassed": bypassed[0],
        "all_bypassed": bypassed
    }

# ══════════════════════════════════════════════════════════════
#  ALEX BOT PARSER (TELEGRAM DM ONLY)
# ══════════════════════════════════════════════════════════════
_SMALLCAPS_FOLD_MAP = {
    'ᴀ': 'a', 'ʙ': 'b', 'ᴄ': 'c', 'ᴅ': 'd', 'ᴇ': 'e', 'ꜰ': 'f', 'ɢ': 'g', 'ʜ': 'h', 'ɪ': 'i', 'ᴊ': 'j',
    'ᴋ': 'k', 'ʟ': 'l', 'ᴍ': 'm', 'ɴ': 'n', 'ᴏ': 'o', 'ᴩ': 'p', 'ᴘ': 'p', 'q': 'q', 'ǫ': 'q', 'ʀ': 'r',
    'ꜱ': 's', 'ѕ': 's', 'ᴛ': 't', 'ᴜ': 'u', 'ᴠ': 'v', 'ᴡ': 'w', 'x': 'x', 'ʏ': 'y', 'ᴢ': 'z', 'є': 'e',
    'σ': 'o', 'υ': 'u', 'ν': 'v', 'ω': 'w', '᥊': 'x', 'ι': 'i'
}

def fold_small_caps(s: str) -> str:
    """Fold small-caps Unicode characters into plain ASCII for regex matching."""
    return ''.join(_SMALLCAPS_FOLD_MAP.get(ch, ch) for ch in (s or ''))

_RX_ALEX_BYPASSED = re.compile(r'bypass(?:ed)?\s*link[^:\n]*:?-?\s*\**\s*\n?\s*(https?://\S+)', re.I)
_RX_ALEX_PROGRESS = re.compile(
    r'initialis|initializ|fetching|scanning|bypassing\s*security|cracking|decoding|solving|'
    r'processing|please\s*wait|\d{1,3}\s*%|[▰▱]|checking|working|loading|almost\s*done',
    re.I
)
_RX_ALEX_FAIL = re.compile(
    r'bypass\s*(?:failed|error)|invalid\s*link|not\s*support(?:ed)?|unsupported|'
    r'no\s*script|not\s*found|unable|unable\s+to|cannot|can[\'’]t|'
    r'could\s*not|couldn[\'’]t|not\s*possible|does\s*not\s*support|'
    r'doesn[\'’]t\s*support|failed|error',
    re.I
)

def parse_alex_message(text: str, entities: list, sent_link: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    stripped = text.strip()
    folded = fold_small_caps(stripped)

    if (
        _RX_ALEX_PROGRESS.search(folded)
        and not _RX_ALEX_BYPASSED.search(folded)
        and not _RX_ALEX_FAIL.search(folded)
    ):
        return {"status": "intermediate", "raw": stripped[:100]}

    if _RX_INTERMEDIATE.search(folded) and len(folded) < 140:
        return {"status": "intermediate", "raw": stripped[:100]}

    if _RX_RATE.search(folded):
        return {"status": "rate_limit", "error": "Alex bot rate limited", "raw": stripped[:200]}

    if _RX_ALEX_FAIL.search(folded) and not _RX_ALEX_BYPASSED.search(folded):
        return {"status": "failed", "error": stripped[:200], "raw": stripped[:200]}

    m = _RX_ALEX_BYPASSED.search(folded)
    if m:
        u = clean_url(m.group(1))
        if is_valid_bypassed_destination(u, sent_link):
            return {
                "status": "ok",
                "original": sent_link,
                "bypassed": u,
                "raw": stripped[:200]
            }

    urls_found = []
    if entities:
        for ent in entities:
            off = getattr(ent, 'offset', None)
            lng = getattr(ent, 'length', None)
            url = getattr(ent, 'url', None)
            if not url:
                if isinstance(ent, MessageEntityUrl) and off is not None and lng:
                    url = text[off:off + lng]
                else:
                    continue
            url = clean_url(url)
            if is_valid_bypassed_destination(url, sent_link) and url not in urls_found:
                urls_found.append(url)

    if not urls_found:
        for u in extract_valid_urls_from_text(text, sent_link):
            if u not in urls_found:
                urls_found.append(u)

    if urls_found:
        return {
            "status": "ok",
            "original": sent_link,
            "bypassed": urls_found[0],
            "all": urls_found,
            "raw": stripped[:200]
        }

    return None

# ══════════════════════════════════════════════════════════════
#  RUNTIME STATE & JOB ENGINE
# ══════════════════════════════════════════════════════════════
class JobState:
    WAITING = "WAITING"
    PROCESSING = "PROCESSING"
    RESULT_FOUND = "RESULT_FOUND"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"

class BypassEngine:
    def __init__(self):
        self.active_jobs: Dict[str, Dict[str, Any]] = {}
        self.jobs_lock = threading.Lock()
        self.user_active_jobs: Dict[int, int] = defaultdict(int)
        self.user_last_request: Dict[int, float] = {}
        self.rate_lock = threading.Lock()

        # Telethon Userbot & entity caches
        self.userbot: Optional[TelegramClient] = None
        self.userbot_connected = False
        self.alex_bot_id: Optional[int] = None
        self.dzhq_bot_id: Optional[int] = None
        self.dzhq_group_entity: Any = None

        # FIFO Queue for Alex DM jobs
        self.alex_dm_queue: List[str] = []
        self.alex_queue_lock = threading.Lock()

        # Statistics
        self.total_bypasses = 0
        self.successful_bypasses = 0
        self.failed_bypasses = 0
        self.start_time = time.time()

    def check_user_rate_limit(self, user_id: int) -> Tuple[bool, str]:
        with self.rate_lock:
            now = time.time()
            last_ts = self.user_last_request.get(user_id, 0)
            if now - last_ts < RATE_LIMIT_SECONDS:
                wait_sec = round(RATE_LIMIT_SECONDS - (now - last_ts), 1)
                return False, f"⏳ Rate limit reached. Please wait {wait_sec}s before sending another link."

            if self.user_active_jobs[user_id] >= MAX_CONCURRENT_PER_USER:
                return False, f"⚠️ You have {self.user_active_jobs[user_id]} active bypass jobs. Please wait for them to finish."

            self.user_last_request[user_id] = now
            self.user_active_jobs[user_id] += 1
            return True, ""

    def release_user_job(self, user_id: int):
        with self.rate_lock:
            if self.user_active_jobs[user_id] > 0:
                self.user_active_jobs[user_id] -= 1

    def create_job(self, url: str, user_id: Optional[int] = None, source: str = "auto") -> Tuple[str, Dict[str, Any]]:
        job_id = secrets.token_hex(8)
        job = {
            "id": job_id,
            "url": url,
            "user_id": user_id,
            "state": JobState.WAITING,
            "status_msg": "Initializing...",
            "provider": None,
            "created_at": time.time(),
            "last_activity_ts": time.time(),
            "final_url": None,
            "error": None,
            "event": asyncio.Event(),
            "dzhq_sent_id": None,
            "alex_sent_id": None,
            "source_origin": source
        }
        with self.jobs_lock:
            self.active_jobs[job_id] = job
        return job_id, job

    def cleanup_job(self, job_id: str):
        with self.jobs_lock:
            job = self.active_jobs.pop(job_id, None)

        if job and job.get("user_id"):
            self.release_user_job(job["user_id"])

        with self.alex_queue_lock:
            if job_id in self.alex_dm_queue:
                self.alex_dm_queue.remove(job_id)

    async def log_to_owner(self, text: str):
        logger.info(f"[OWNER LOG] {text}")
        if bot_api and OWNER_ID:
            try:
                await bot_api.send_message(OWNER_ID, f"🛡 <b>[ProviderBotz Audit]</b>\n{text}")
            except Exception as e:
                _trace("LOG", f"Failed to deliver log to owner: {e}")

engine = BypassEngine()

# ══════════════════════════════════════════════════════════════
#  USERBOT TELEGRAM HANDLERS (DZHQ GROUP ONLY + ALEX DM ONLY)
# ══════════════════════════════════════════════════════════════
def setup_userbot_handlers(client: TelegramClient):
    """
    DZHQ operates strictly in DZHQ_GROUP (-1003644908415).
    Alex operates strictly in private DM.
    """

    # 1. DZHQ Handler — STRICTLY IN TELEGRAM GROUP
    async def on_dzhq_message(event):
        if event.chat_id != DZHQ_GROUP and (engine.dzhq_group_entity and event.chat_id != engine.dzhq_group_entity.id):
            return

        msg = event.message
        text = msg.text or ""
        if not text:
            return

        sender_id = event.sender_id
        if engine.dzhq_bot_id and sender_id != engine.dzhq_bot_id:
            return

        rt_obj = getattr(msg, 'reply_to', None)
        reply_to_id = getattr(rt_obj, 'reply_to_msg_id', None) if rt_obj else None
        if not reply_to_id:
            return

        target_job = None
        with engine.jobs_lock:
            for job in engine.active_jobs.values():
                if job.get("dzhq_sent_id") == reply_to_id and job["state"] in (JobState.WAITING, JobState.PROCESSING):
                    target_job = job
                    break

        if not target_job:
            return

        parsed = parse_dzhq_message(text, msg.entities or [], target_job["url"])
        status = parsed[0].get("status") if parsed else "empty"
        _trace("DZHQ_GROUP", f"Job {target_job['id']} update: status={status}")

        target_job["last_activity_ts"] = time.time()

        if status == "intermediate":
            target_job["state"] = JobState.PROCESSING
            target_job["status_msg"] = "⏳ ᴘʀσᴄєѕѕιɴɢ... (DZHQ group bypass)"
            return

        # Auto-click Delete button on DZHQ result message
        buttons = getattr(msg, 'buttons', None)
        if buttons:
            async def _click_delete():
                try:
                    for row in buttons:
                        for btn in row:
                            bt = (getattr(btn, 'text', '') or '').lower()
                            if any(k in bt for k in ('delete', '🗑', '❌')):
                                await btn.click()
                                _trace("DZHQ_GROUP", "Auto-clicked delete button on result")
                                return
                except Exception as e:
                    _trace("DZHQ_GROUP", f"Delete button click error: {e}")
            asyncio.create_task(_click_delete())

        if status == "ok" and parsed[0].get("bypassed"):
            bypassed_link = parsed[0]["bypassed"]
            if is_valid_bypassed_destination(bypassed_link, target_job["url"]):
                target_job["final_url"] = bypassed_link
                target_job["provider"] = "dzhq"
                target_job["state"] = JobState.RESULT_FOUND
                target_job["event"].set()
        elif status in ("failed", "rate_limit", "no_link"):
            target_job["error"] = parsed[0].get("error", "DZHQ failed to bypass link")
            target_job["state"] = JobState.FAILED
            target_job["event"].set()

    client.add_event_handler(on_dzhq_message, events.NewMessage(chats=DZHQ_GROUP))
    client.add_event_handler(on_dzhq_message, events.MessageEdited(chats=DZHQ_GROUP))

    # 2. Alex DM Handler — STRICTLY IN PRIVATE DM
    async def on_alex_message(event):
        msg = event.message
        text = msg.text or msg.caption or ""
        if not text:
            return

        sender_id = event.sender_id
        if engine.alex_bot_id and sender_id != engine.alex_bot_id:
            return

        with engine.alex_queue_lock:
            if not engine.alex_dm_queue:
                return
            target_job_id = engine.alex_dm_queue[0]

        with engine.jobs_lock:
            target_job = engine.active_jobs.get(target_job_id)

        if not target_job or target_job["state"] not in (JobState.WAITING, JobState.PROCESSING):
            with engine.alex_queue_lock:
                if engine.alex_dm_queue and engine.alex_dm_queue[0] == target_job_id:
                    engine.alex_dm_queue.pop(0)
            return

        incoming_id = getattr(msg, "id", None)
        sent_id = target_job.get("alex_sent_id")
        if sent_id and incoming_id and incoming_id <= sent_id:
            return

        parsed = parse_alex_message(text, msg.entities or [], target_job["url"])
        _trace("ALEX_DM", f"Job {target_job['id']} Alex message received: parsed={parsed}")

        target_job["last_activity_ts"] = time.time()

        if not parsed or parsed.get("status") == "intermediate":
            target_job["state"] = JobState.PROCESSING
            target_job["status_msg"] = "🔄 ʙʏᴘᴀѕѕιɴɢ... (Alex DM solving)"
            return

        if parsed.get("status") == "ok" and parsed.get("bypassed"):
            with engine.alex_queue_lock:
                if engine.alex_dm_queue and engine.alex_dm_queue[0] == target_job_id:
                    engine.alex_dm_queue.pop(0)

            bypassed_link = parsed["bypassed"]
            if is_valid_bypassed_destination(bypassed_link, target_job["url"]):
                target_job["final_url"] = bypassed_link
                target_job["provider"] = "alex_dm"
                target_job["state"] = JobState.RESULT_FOUND
                target_job["event"].set()
        elif parsed.get("status") in ("failed", "rate_limit"):
            with engine.alex_queue_lock:
                if engine.alex_dm_queue and engine.alex_dm_queue[0] == target_job_id:
                    engine.alex_dm_queue.pop(0)

            target_job["error"] = parsed.get("error", "Alex DM bypass failed")
            target_job["state"] = JobState.FAILED
            target_job["event"].set()

    client.add_event_handler(on_alex_message, events.NewMessage(incoming=True, func=lambda e: e.is_private))
    client.add_event_handler(on_alex_message, events.MessageEdited(incoming=True, func=lambda e: e.is_private))

# ══════════════════════════════════════════════════════════════
#  BYPASS WORKFLOW EXECUTOR
# ══════════════════════════════════════════════════════════════
async def execute_bypass_job(job_id: str) -> Dict[str, Any]:
    with engine.jobs_lock:
        job = engine.active_jobs.get(job_id)
    if not job:
        return {"status": False, "message": "Job not found"}

    target_url = job["url"]
    t0 = time.time()

    if not engine.userbot or not engine.userbot_connected:
        job["state"] = JobState.FAILED
        job["error"] = "Telethon Userbot is not connected"
        return {"status": False, "message": job["error"]}

    is_alex_favored = any(k in target_url.lower() for k in ("urlking", "monteolympus", "alex", "shortx"))
    primary_provider = "alex_dm" if is_alex_favored else "dzhq"
    fallback_provider = "dzhq" if is_alex_favored else "alex_dm"

    providers_to_try = [primary_provider, fallback_provider]

    for current_provider in providers_to_try:
        job["provider"] = current_provider
        job["state"] = JobState.PROCESSING
        job["event"].clear()
        job["last_activity_ts"] = time.time()

        _trace("ENGINE", f"Executing job {job_id} on {current_provider}")

        try:
            if current_provider == "dzhq":
                group_target = engine.dzhq_group_entity if engine.dzhq_group_entity else DZHQ_GROUP
                sent = await engine.userbot.send_message(group_target, f"/b {target_url}")
                job["dzhq_sent_id"] = sent.id
            elif current_provider == "alex_dm":
                with engine.alex_queue_lock:
                    engine.alex_dm_queue.append(job_id)
                sent = await engine.userbot.send_message(ALEX_BOT, target_url)
                job["alex_sent_id"] = sent.id

            provider_timeout = ALEX_DM_TIMEOUT_SEC if current_provider == "alex_dm" else BYPASS_IDLE_TIMEOUT_SEC
            while time.time() - t0 < MAX_BYPASS_TIMEOUT_SEC:
                now = time.time()
                if now - job["last_activity_ts"] > provider_timeout:
                    _trace("ENGINE", f"Provider {current_provider} idle timeout ({provider_timeout}s)")
                    break

                try:
                    await asyncio.wait_for(asyncio.shield(job["event"].wait()), timeout=1.0)
                except asyncio.TimeoutError:
                    pass

                if job["state"] in (JobState.RESULT_FOUND, JobState.FAILED):
                    break

            if job["state"] == JobState.RESULT_FOUND and job.get("final_url"):
                duration_ms = int((time.time() - t0) * 1000)
                engine.total_bypasses += 1
                engine.successful_bypasses += 1

                log_entry = (
                    f"✅ <b>Bypass Success</b>\n"
                    f"• User: <code>{job.get('user_id', 'API')}</code>\n"
                    f"• Provider: <code>{current_provider.upper()}</code>\n"
                    f"• Time: <code>{duration_ms}ms</code>\n"
                    f"• Original: {job['url']}\n"
                    f"• Destination: {job['final_url']}"
                )
                asyncio.create_task(engine.log_to_owner(log_entry))

                return {
                    "status": True,
                    "developer": DEVELOPER,
                    "response_ms": f"{duration_ms}ms",
                    "source": current_provider,
                    "url": job["final_url"],
                    "links": {
                        "original": job["url"],
                        "bypassed": job["final_url"]
                    }
                }

        except Exception as e:
            _trace("ENGINE", f"Provider {current_provider} error: {e}")

        _trace("ENGINE", f"Primary {current_provider} did not resolve. Attempting fallback.")

    duration_ms = int((time.time() - t0) * 1000)
    engine.total_bypasses += 1
    engine.failed_bypasses += 1
    job["state"] = JobState.FAILED

    fail_log = (
        f"❌ <b>Bypass Failed</b>\n"
        f"• User: <code>{job.get('user_id', 'API')}</code>\n"
        f"• Original: {job['url']}\n"
        f"• Time: <code>{duration_ms}ms</code>\n"
        f"• Reason: All providers (DZHQ group + Alex DM) timed out or rejected."
    )
    asyncio.create_task(engine.log_to_owner(fail_log))

    return {
        "status": False,
        "developer": DEVELOPER,
        "message": "All bypass providers failed to resolve this link.",
        "response_ms": f"{duration_ms}ms"
    }

# ══════════════════════════════════════════════════════════════
#  TELEGRAM BOT API (REAL COLORED BUTTONS VIA BOT API 9.4+)
# ══════════════════════════════════════════════════════════════
class TelegramBotAPI:
    """
    Direct Telegram Bot API client that natively sends Bot API 9.4+ button styles:
    - style: 'primary' (Dark Blue Accent)
    - style: 'success' (Emerald Green)
    - style: 'danger'  (Red)
    """
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.session: Optional[aiohttp.ClientSession] = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45))
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def call(self, method: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        session = await self.get_session()
        url = f"{self.base_url}/{method}"
        try:
            async with session.post(url, json=data or {}) as resp:
                result = await resp.json()
                return result
        except Exception as e:
            _trace("BOT_API", f"Error calling {method}: {e}")
            return {"ok": False, "description": str(e)}

    async def get_me(self) -> Dict[str, Any]:
        return await self.call("getMe")

    async def send_message(
        self,
        chat_id: Union[int, str],
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        reply_to_message_id: Optional[int] = None,
        parse_mode: str = "HTML"
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup.to_dict()
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        res = await self.call("sendMessage", payload)
        if not res.get("ok") and "reply_markup" in payload:
            # Fallback if server does not accept style field
            fallback_payload = dict(payload)
            fallback_payload["reply_markup"] = self._strip_styles(payload["reply_markup"])
            res = await self.call("sendMessage", fallback_payload)
        return res

    async def edit_message_text(
        self,
        chat_id: Union[int, str],
        message_id: int,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        parse_mode: str = "HTML"
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup.to_dict()
        res = await self.call("editMessageText", payload)
        if not res.get("ok") and "reply_markup" in payload:
            fallback_payload = dict(payload)
            fallback_payload["reply_markup"] = self._strip_styles(payload["reply_markup"])
            res = await self.call("editMessageText", fallback_payload)
        return res

    @staticmethod
    def _strip_styles(markup_dict: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(markup_dict, dict) or "inline_keyboard" not in markup_dict:
            return markup_dict
        new_keyboard = []
        for row in markup_dict.get("inline_keyboard", []):
            new_row = []
            for btn in row:
                if isinstance(btn, dict):
                    new_row.append({k: v for k, v in btn.items() if k != "style"})
                else:
                    new_row.append(btn)
            new_keyboard.append(new_row)
        return {"inline_keyboard": new_keyboard}

    async def answer_callback_query(self, callback_query_id: str, text: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        return await self.call("answerCallbackQuery", payload)

    async def delete_message(self, chat_id: Union[int, str], message_id: int) -> Dict[str, Any]:
        return await self.call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

bot_api: Optional[TelegramBotAPI] = None

# ══════════════════════════════════════════════════════════════
#  REAL COLORED BUTTON BUILDERS (PRIMARY, SUCCESS, DANGER)
# ══════════════════════════════════════════════════════════════
def get_start_buttons() -> InlineKeyboardMarkup:
    """
    Start screen buttons with REAL native Bot API 9.4 colored styles:
    - Primary (🔵 Dark Blue Accent)
    - Success (🟢 Green)
    - Danger  (🔴 Red)
    """
    public_url = get_auto_public_url()
    add_group_url = f"https://t.me/{BOT_USERNAME}?startgroup=true" if BOT_USERNAME else "https://t.me/"

    buttons = [
        # PRIMARY BUTTON: 🔵 Add To Your Group (Dark Blue)
        [
            InlineKeyboardButton(
                text="➕ ᴧᴅᴅ тσ ʏσυʀ ɢʀσυᴩ",
                url=add_group_url,
                style=ButtonStyle.PRIMARY
            )
        ]
    ]

    if public_url and not public_url.startswith("http://localhost"):
        # SUCCESS BUTTON: 🟢 Open Mini App (Green)
        buttons.append([
            InlineKeyboardButton(
                text="🚀 σᴩєɴ ᴍιɴι ᴧᴩᴩ",
                web_app={"url": public_url},
                style=ButtonStyle.SUCCESS
            )
        ])

    # VIBRANT PROVIDERBOTZ TELEGRAM CHANNEL BUTTON (Primary Style)
    buttons.append([
        InlineKeyboardButton(
            text="📢 ᴩʀσᴠιᴅєʀʙσтᴢ ᴄʜᴧɴɴєʟ",
            url=OFFICIAL_CHANNEL,
            style=ButtonStyle.PRIMARY
        )
    ])

    # DANGER & SUCCESS ROW: 🔴 Help (Red) | 🟢 About (Green)
    buttons.append([
        InlineKeyboardButton(
            text="❌ ʜєʟᴩ",
            callback_data="cmd_help",
            style=ButtonStyle.DANGER
        ),
        InlineKeyboardButton(
            text="✅ ᴧʙσυт",
            callback_data="cmd_about",
            style=ButtonStyle.SUCCESS
        )
    ])

    return InlineKeyboardMarkup(buttons)

# Retry cache for safe 64-byte Telegram callback_data
_RETRY_CACHE: Dict[str, str] = {}

def get_retry_callback_data(job_url: str) -> str:
    token = secrets.token_hex(6)
    _RETRY_CACHE[token] = job_url
    if len(_RETRY_CACHE) > 500:
        for k in list(_RETRY_CACHE.keys())[:100]:
            _RETRY_CACHE.pop(k, None)
    return f"retry:{token}"

def get_result_buttons(final_url: str, job_url: str) -> InlineKeyboardMarkup:
    """
    Final Result buttons with REAL native Bot API 9.4 colored styles:
    - SUCCESS: 🟢 Open Link (Green)
    - PRIMARY: 🔵 Copy Link via Mini App (Blue)
    - PRIMARY: 🟣 ProviderBotz Channel (Purple/Blue Accent)
    - DANGER:  🔴 Retry (Red) | 🔴 Close (Red)
    """
    public_url = get_auto_public_url()
    retry_cb = get_retry_callback_data(job_url)
    buttons = [
        # SUCCESS BUTTON: 🟢 Open Link
        [
            InlineKeyboardButton(
                text="🟢 🔗 ᴏᴩєɴ ʟιɴᴋ",
                url=final_url,
                style=ButtonStyle.SUCCESS
            )
        ]
    ]

    if public_url and not public_url.startswith("http://localhost"):
        # PRIMARY BUTTON: 🔵 Copy Link (Auto-copy in Mini App)
        mini_app_copy_url = f"{public_url}/?copy={urllib.parse.quote(final_url)}"
        buttons.append([
            InlineKeyboardButton(
                text="🔵 📋 ᴄσᴩʏ ʟιɴᴋ",
                web_app={"url": mini_app_copy_url},
                style=ButtonStyle.PRIMARY
            )
        ])

    # VIBRANT PROVIDERBOTZ TELEGRAM CHANNEL BUTTON
    buttons.append([
        InlineKeyboardButton(
            text="🟣 📢 ᴩʀσᴠιᴅєʀʙσтᴢ ᴄʜᴧɴɴєʟ",
            url=OFFICIAL_CHANNEL,
            style=ButtonStyle.PRIMARY
        )
    ])

    # DANGER BUTTONS: 🔴 Retry | 🔴 Close
    buttons.append([
        InlineKeyboardButton(
            text="🔴 🔄 ʀєтʀʏ ʙʏᴩᴧѕѕ",
            callback_data=retry_cb,
            style=ButtonStyle.DANGER
        ),
        InlineKeyboardButton(
            text="🔴 ❌ ᴄʟσѕє",
            callback_data="cmd_close",
            style=ButtonStyle.DANGER
        )
    ])

    return InlineKeyboardMarkup(buttons)

def get_failed_buttons(job_url: str) -> InlineKeyboardMarkup:
    """Failure buttons with colored styles."""
    retry_cb = get_retry_callback_data(job_url)
    buttons = [
        [
            InlineKeyboardButton(
                text="🔴 🔄 ʀєтʀʏ ʙʏᴩᴧѕѕ",
                callback_data=retry_cb,
                style=ButtonStyle.DANGER
            )
        ],
        [
            InlineKeyboardButton(
                text="🟣 📢 ᴩʀσᴠιᴅєʀʙσтᴢ ᴄʜᴧɴɴєʟ",
                url=OFFICIAL_CHANNEL,
                style=ButtonStyle.PRIMARY
            )
        ],
        [
            InlineKeyboardButton(
                text="🔵 🏠 ʜσᴍє",
                callback_data="cmd_home",
                style=ButtonStyle.PRIMARY
            )
        ]
    ]
    return InlineKeyboardMarkup(buttons)

def get_help_buttons() -> InlineKeyboardMarkup:
    """Help screen buttons with native Bot API 9.4 styles."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="🟣 📢 ᴩʀσᴠιᴅєʀʙσтᴢ ᴄʜᴧɴɴєʟ",
                url=OFFICIAL_CHANNEL,
                style=ButtonStyle.PRIMARY
            )
        ],
        [
            InlineKeyboardButton(
                text="🔵 🏠 ʜσᴍє",
                callback_data="cmd_home",
                style=ButtonStyle.PRIMARY
            ),
            InlineKeyboardButton(
                text="🟢 ✅ ᴧʙσυт",
                callback_data="cmd_about",
                style=ButtonStyle.SUCCESS
            )
        ]
    ])

def get_about_buttons() -> InlineKeyboardMarkup:
    """About screen buttons with native Bot API 9.4 styles."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="🟣 📢 ᴩʀσᴠιᴅєʀʙσтᴢ ᴄʜᴧɴɴєʟ",
                url=OFFICIAL_CHANNEL,
                style=ButtonStyle.PRIMARY
            )
        ],
        [
            InlineKeyboardButton(
                text="🔵 🏠 ʜσᴍє",
                callback_data="cmd_home",
                style=ButtonStyle.PRIMARY
            ),
            InlineKeyboardButton(
                text="🔴 ❌ ʜєʟᴩ",
                callback_data="cmd_help",
                style=ButtonStyle.DANGER
            )
        ]
    ])

def extract_input_url(data: Union[Dict[str, Any], str]) -> Optional[str]:
    """Extract any target URL from a Telegram message dict or string (handles plain text, caption, and entities)."""
    if isinstance(data, dict):
        text = (data.get("text") or data.get("caption") or "").strip()
        entities = data.get("entities") or data.get("caption_entities") or []
        for ent in entities:
            if ent.get("type") == "text_link" and ent.get("url"):
                u = clean_url(ent["url"])
                if is_valid_bypassed_destination(u, ""):
                    return u
            elif ent.get("type") == "url":
                offset = ent.get("offset", 0)
                length = ent.get("length", 0)
                if text and offset is not None and length:
                    u = clean_url(text[offset:offset + length])
                    if u and not u.startswith(('/start', '/help', '/about')):
                        return u
    else:
        text = str(data or "").strip()

    if not text:
        return None

    if text.startswith("/bypass"):
        text = text[len("/bypass"):].strip()

    # 1. Match full http/https URLs
    m = re.search(r'https?://[^\s\n\)\]>"\']+', text)
    if m:
        return clean_url(m.group(0))

    # 2. Match bare domain/path (e.g. droplink.co/abc, gplinks.co/xyz)
    m_bare = re.search(r'(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?', text)
    if m_bare:
        candidate = m_bare.group(0)
        if not candidate.startswith(('@', '/')) and '.' in candidate and not candidate.startswith(('t.me/', 'telegram.me/')):
            return "https://" + clean_url(candidate)
    return None

# ══════════════════════════════════════════════════════════════
#  TELEGRAM BOT WORKER & LONG POLLING (ALEX BYPASS BOT STYLE)
# ══════════════════════════════════════════════════════════════
async def process_user_link(chat_id: int, user_id: int, target_url: str, reply_msg_id: Optional[int] = None):
    """
    Automatically bypasses links with dynamic animated progress frames
    and displays the final clean result formatted like @alexbypassbot (no raw JSON, no internal source leaked).
    """
    allowed, rate_msg = engine.check_user_rate_limit(user_id)
    if not allowed:
        await bot_api.send_message(chat_id, rate_msg, reply_to_message_id=reply_msg_id)
        return

    job_id, _ = engine.create_job(target_url, user_id=user_id, source="telegram")

    # Initial Animation Frame (10%)
    initial_frame = (
        f"🔄 <b>{to_small_caps('bypassing link...')}</b> [▰▱▱▱▱▱▱▱▱▱] 10%\n"
        f"🔍 <i>{to_small_caps('fetching link data...')}</i>"
    )
    initial_msg = await bot_api.send_message(
        chat_id,
        initial_frame,
        reply_to_message_id=reply_msg_id
    )
    status_msg_id = initial_msg.get("result", {}).get("message_id")

    stop_updater = asyncio.Event()

    async def _status_ticker():
        # Fast, responsive animation frames like AlexBypassBot
        frames = [
            (
                f"🔄 <b>{to_small_caps('bypassing link...')}</b> [▰▰▰▱▱▱▱▱▱▱] 35%\n"
                f"🔓 <i>{to_small_caps('bypassing security & captcha...')}</i>"
            ),
            (
                f"🔄 <b>{to_small_caps('bypassing link...')}</b> [▰▰▰▰▰▱▱▱▱▱] 60%\n"
                f"⚙️ <i>{to_small_caps('decoding shortlink tokens...')}</i>"
            ),
            (
                f"🔄 <b>{to_small_caps('bypassing link...')}</b> [▰▰▰▰▰▰▰▱▱▱] 80%\n"
                f"📡 <i>{to_small_caps('solving destination redirect...')}</i>"
            ),
            (
                f"🔄 <b>{to_small_caps('bypassing link...')}</b> [▰▰▰▰▰▰▰▰▰▱] 95%\n"
                f"✨ <i>{to_small_caps('verifying clean destination...')}</i>"
            )
        ]
        idx = 0
        while not stop_updater.is_set():
            await asyncio.sleep(1.2)
            if stop_updater.is_set():
                break
            if status_msg_id:
                try:
                    await bot_api.edit_message_text(chat_id, status_msg_id, frames[idx])
                except Exception:
                    pass
            idx = (idx + 1) % len(frames)

    ticker_task = asyncio.create_task(_status_ticker())

    try:
        result = await execute_bypass_job(job_id)
    finally:
        stop_updater.set()
        ticker_task.cancel()
        engine.cleanup_job(job_id)

    # Output formatted PROPERLY like AlexBypassBot message:
    # No raw JSON! No internal source name shown! Single tap monospace copy!
    if result.get("status") is True and result.get("url"):
        final_url = result["url"]
        duration_ms = int(result.get("response_ms", "1000ms").replace("ms", ""))
        duration_formatted = f"{duration_ms / 1000:.1f}s" if duration_ms >= 1000 else f"{duration_ms}ms"

        res_text = (
            f"⚡ <b>Link Bypassed Successfully!</b>\n\n"
            f"🔗 <b>Original Link:</b>\n"
            f"<code>{html.escape(target_url)}</code>\n\n"
            f"🎯 <b>Bypassed Link:</b>\n"
            f"<code>{html.escape(final_url)}</code>\n\n"
            f"⏱ <b>Time Taken:</b> <code>{duration_formatted}</code>\n\n"
            f"👆 <i>Tap the bypassed link above to copy immediately!</i>"
        )
        reply_markup = get_result_buttons(final_url, target_url)
        if status_msg_id:
            try:
                await bot_api.edit_message_text(chat_id, status_msg_id, res_text, reply_markup=reply_markup)
            except Exception:
                await bot_api.send_message(chat_id, res_text, reply_markup=reply_markup)
        else:
            await bot_api.send_message(chat_id, res_text, reply_markup=reply_markup)
    else:
        err_text = (
            f"❌ <b>Bypass Failed!</b>\n\n"
            f"⚠️ <i>The link could not be bypassed or expired.</i>\n\n"
            f"🔗 <b>Original Link:</b>\n"
            f"<code>{html.escape(target_url)}</code>\n\n"
            f"• <i>Please check if the link is active and valid.</i>\n"
            f"• <i>Tap Retry below to try bypassing again.</i>"
        )
        reply_markup = get_failed_buttons(target_url)
        if status_msg_id:
            try:
                await bot_api.edit_message_text(chat_id, status_msg_id, err_text, reply_markup=reply_markup)
            except Exception:
                await bot_api.send_message(chat_id, err_text, reply_markup=reply_markup)
        else:
            await bot_api.send_message(chat_id, err_text, reply_markup=reply_markup)

async def run_bot_polling():
    """Continuous async long-polling loop for the public bot."""
    global bot_api
    if not BOT_TOKEN:
        logger.warning("⚠️ BOT_TOKEN is missing. Public bot polling will not run.")
        return

    bot_api = TelegramBotAPI(BOT_TOKEN)
    me = await bot_api.get_me()
    if not me.get("ok"):
        logger.error(f"❌ Failed to connect to Telegram Bot API with BOT_TOKEN: {me.get('description')}")
        return

    global BOT_USERNAME
    bot_info = me.get("result", {})
    BOT_USERNAME = bot_info.get("username", BOT_USERNAME)
    logger.info(f"✅ Public Bot API online: @{BOT_USERNAME} (Bot API 9.4 Colored Buttons Enabled)")

    offset = 0
    while True:
        try:
            updates = await bot_api.call("getUpdates", {"offset": offset, "timeout": 25})
            if not updates.get("ok"):
                await asyncio.sleep(2)
                continue

            for u in updates.get("result", []):
                offset = max(offset, u["update_id"] + 1)

                # 1. Handle Messages
                if "message" in u:
                    msg = u["message"]
                    chat_id = msg.get("chat", {}).get("id")
                    user = msg.get("from", {})
                    user_id = user.get("id")
                    text = (msg.get("text") or msg.get("caption") or "").strip()
                    first_name = html.escape(user.get("first_name", "Friend") or "Friend")

                    if not text or not chat_id:
                        continue

                    if text == "/start":
                        start_text = (
                            f"Welcome {first_name} 🌹\n\n"
                            f"This is the fastest and powerful auto link bypass bot ∆\n\n"
                            f"⚡ <b>ᴩʀσᴠιᴅєʀʙσтᴢ ᴇɴɢιɴє</b>\n"
                            f"Send any supported shortener link below to bypass instantly.\n\n"
                            f"📢 <b>Official Updates:</b> @ProviderBotz"
                        )
                        await bot_api.send_message(chat_id, start_text, reply_markup=get_start_buttons())

                    elif text == "/help":
                        help_text = (
                            f"📖 <b>{to_small_caps('help guide')}</b>\n\n"
                            f"1. <b>{to_small_caps('send a link')}</b>: Simply paste any supported shortlink.\n"
                            f"2. <b>{to_small_caps('automatic processing')}</b>: The bot resolves the link through DZHQ and Alex DM engines.\n"
                            f"3. <b>{to_small_caps('clean result')}</b>: Only the pure final destination URL is returned (all promotional ads stripped).\n"
                            f"4. <b>{to_small_caps('copy link')}</b>: Tap on the monospace URL to copy instantly to your clipboard.\n"
                            f"5. <b>{to_small_caps('retry system')}</b>: If a link temporarily fails, tap the Retry button.\n\n"
                            f"🛡 <i>{to_small_caps('powered by')} @ProviderBotz</i>"
                        )
                        await bot_api.send_message(chat_id, help_text, reply_markup=get_help_buttons())

                    elif text == "/about":
                        about_text = (
                            f"ℹ️ <b>{to_small_caps('about')} ShortnerBypass</b>\n\n"
                            f"• <b>{to_small_caps('developer')}</b>: {DEVELOPER}\n"
                            f"• <b>{to_small_caps('engines')}</b>: DZHQ Group Engine + Alex DM Engine\n"
                            f"• <b>{to_small_caps('speed')}</b>: High-Speed Async Telethon Userbot\n"
                            f"• <b>{to_small_caps('clean links')}</b>: Zero ads, zero spam channels\n"
                            f"• <b>{to_small_caps('buttons')}</b>: Native Bot API 9.4 Colored Styles\n"
                            f"• <b>{to_small_caps('mini app')}</b>: Obsidian Red Glassmorphism Dashboard\n\n"
                            f"🚀 <i>{to_small_caps('crafted for speed and reliability')}</i>"
                        )
                        await bot_api.send_message(chat_id, about_text, reply_markup=get_about_buttons())

                    elif text.startswith("/bypass"):
                        url_to_bypass = extract_input_url(msg)
                        if url_to_bypass:
                            asyncio.create_task(process_user_link(chat_id, user_id, url_to_bypass, reply_msg_id=msg.get("message_id")))
                        else:
                            bypass_help = (
                                f"⚠️ <b>{to_small_caps('please provide a link')}</b>:\n"
                                f"<code>/bypass https://example.com/shortlink</code>\n\n"
                                f"<i>Or simply paste any supported shortener link directly into the chat!</i>"
                            )
                            await bot_api.send_message(chat_id, bypass_help)

                    else:
                        target = extract_input_url(msg)
                        if target:
                            asyncio.create_task(process_user_link(chat_id, user_id, target, reply_msg_id=msg.get("message_id")))

                # 2. Handle Callback Queries
                elif "callback_query" in u:
                    cq = u["callback_query"]
                    cq_id = cq["id"]
                    cq_data = cq.get("data", "")
                    cq_msg = cq.get("message", {})
                    chat_id = cq_msg.get("chat", {}).get("id")
                    msg_id = cq_msg.get("message_id")
                    user = cq.get("from", {})
                    first_name = html.escape(user.get("first_name", "Friend") or "Friend")

                    await bot_api.answer_callback_query(cq_id)

                    if cq_data == "cmd_home":
                        start_text = (
                            f"Welcome {first_name} 🌹\n\n"
                            f"This is the fastest and powerfull auto link bypass bot ∆\n\n"
                            f"⚡ <b>ᴩʀσᴠιᴅєʀʙσтᴢ ᴇɴɢιɴє</b>\n"
                            f"Send any supported shortener link below to bypass instantly.\n\n"
                            f"📢 <b>Official Updates:</b> @ProviderBotz"
                        )
                        await bot_api.edit_message_text(chat_id, msg_id, start_text, reply_markup=get_start_buttons())

                    elif cq_data == "cmd_help":
                        help_text = (
                            f"📖 <b>{to_small_caps('help guide')}</b>\n\n"
                            f"1. <b>{to_small_caps('send a link')}</b>: Simply paste any supported shortlink.\n"
                            f"2. <b>{to_small_caps('automatic processing')}</b>: The bot resolves the link through DZHQ and Alex DM engines.\n"
                            f"3. <b>{to_small_caps('clean result')}</b>: Only the pure final destination URL is returned.\n"
                            f"4. <b>{to_small_caps('copy link')}</b>: Tap on the monospace URL to copy instantly.\n\n"
                            f"🛡 <i>{to_small_caps('powered by')} @ProviderBotz</i>"
                        )
                        await bot_api.edit_message_text(chat_id, msg_id, help_text, reply_markup=get_help_buttons())

                    elif cq_data == "cmd_about":
                        about_text = (
                            f"ℹ️ <b>{to_small_caps('about')} ShortnerBypass</b>\n\n"
                            f"• <b>{to_small_caps('developer')}</b>: {DEVELOPER}\n"
                            f"• <b>{to_small_caps('engines')}</b>: DZHQ Group Engine + Alex DM Engine\n"
                            f"• <b>{to_small_caps('speed')}</b>: High-Speed Async Telethon Userbot\n"
                            f"• <b>{to_small_caps('mini app')}</b>: Obsidian Red Glassmorphism Dashboard\n\n"
                            f"🚀 <i>{to_small_caps('crafted for speed and reliability')}</i>"
                        )
                        await bot_api.edit_message_text(chat_id, msg_id, about_text, reply_markup=get_about_buttons())

                    elif cq_data == "cmd_close":
                        await bot_api.delete_message(chat_id, msg_id)

                    elif cq_data.startswith("retry:"):
                        token = cq_data.split("retry:", 1)[1]
                        url_to_retry = _RETRY_CACHE.get(token, token)
                        if url_to_retry:
                            asyncio.create_task(process_user_link(chat_id, user.get("id"), url_to_retry, reply_msg_id=msg_id))

        except asyncio.CancelledError:
            break
        except Exception as e:
            _trace("POLLING", f"Polling error: {e}")
            await asyncio.sleep(2)

# ══════════════════════════════════════════════════════════════
#  FLASK SERVER & API
# ══════════════════════════════════════════════════════════════
app = Flask(__name__)
app.secret_key = SECRET_KEY

GLOBAL_ASYNC_LOOP: Optional[asyncio.AbstractEventLoop] = None

@app.before_request
def auto_detect_host_url():
    global _CURRENT_PUBLIC_URL
    if not _CURRENT_PUBLIC_URL or _CURRENT_PUBLIC_URL.startswith("http://localhost"):
        proto = request.headers.get("X-Forwarded-Proto") or ("https" if request.is_secure else "http")
        host = request.headers.get("X-Forwarded-Host") or request.host
        if host and not host.startswith("localhost") and not host.startswith("127.0.0.1"):
            _CURRENT_PUBLIC_URL = f"{proto}://{host}".rstrip("/")
        elif request.host_url:
            detected = request.host_url.rstrip("/")
            if not detected.startswith("http://localhost"):
                _CURRENT_PUBLIC_URL = detected

@app.route("/", methods=["GET"])
def route_index():
    index_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    if os.path.exists(index_path):
        return send_file(index_path)
    return "<h1>ShortnerBypass — Telegram Mini App Ready</h1>", 200

@app.route("/health", methods=["GET"])
def route_health():
    return jsonify({
        "status": "ok",
        "service": "ShortnerBypass",
        "developer": DEVELOPER,
        "public_url": get_auto_public_url(),
        "userbot_online": engine.userbot_connected,
        "bot_api_online": bool(bot_api)
    }), 200

@app.route("/bypass", methods=["GET"])
def route_bypass():
    raw_url = request.args.get("url") or request.args.get("link") or ""
    raw_url = raw_url.strip()

    if not raw_url:
        return jsonify({
            "status": False,
            "developer": DEVELOPER,
            "message": "Missing 'url' query parameter. Example: /bypass?url=https://..."
        }), 400

    if not raw_url.startswith(("http://", "https://")):
        raw_url = "https://" + raw_url

    if not GLOBAL_ASYNC_LOOP:
        return jsonify({
            "status": False,
            "developer": DEVELOPER,
            "message": "Engine async loop is not initialized"
        }), 503

    job_id, _ = engine.create_job(raw_url, source="api")

    try:
        future = asyncio.run_coroutine_threadsafe(execute_bypass_job(job_id), GLOBAL_ASYNC_LOOP)
        result = future.result(timeout=MAX_BYPASS_TIMEOUT_SEC + 5)
        status_code = 200 if result.get("status") is True else 422
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({
            "status": False,
            "developer": DEVELOPER,
            "message": f"Bypass request timed out or encountered an error: {e}"
        }), 504
    finally:
        engine.cleanup_job(job_id)

@app.route("/admin/status", methods=["GET"])
def route_admin_status():
    uptime = int(time.time() - engine.start_time)
    with engine.jobs_lock:
        active_count = len(engine.active_jobs)

    return jsonify({
        "developer": DEVELOPER,
        "public_url": get_auto_public_url(),
        "uptime_sec": uptime,
        "active_jobs": active_count,
        "total_bypasses": engine.total_bypasses,
        "successful_bypasses": engine.successful_bypasses,
        "failed_bypasses": engine.failed_bypasses,
        "providers": {
            "dzhq": {"configured": bool(DZHQ_BOT), "group": DZHQ_GROUP, "entity_resolved": bool(engine.dzhq_group_entity)},
            "alex_dm": {"configured": bool(ALEX_BOT)}
        }
    }), 200

# ══════════════════════════════════════════════════════════════
#  STARTUP & LIFECYCLE
# ══════════════════════════════════════════════════════════════
async def main_async():
    global GLOBAL_ASYNC_LOOP
    GLOBAL_ASYNC_LOOP = asyncio.get_running_loop()

    # 1. Start Telethon Userbot (Strictly handles DZHQ Group + Alex DM)
    if TELEGRAM_API_ID and TELEGRAM_API_HASH and TELEGRAM_SESSION:
        logger.info("Connecting Telethon Userbot...")
        try:
            userbot = TelegramClient(
                StringSession(TELEGRAM_SESSION),
                TELEGRAM_API_ID,
                TELEGRAM_API_HASH,
                connection=ConnectionTcpAbridged,
                auto_reconnect=True
            )
            await userbot.start()
            if await userbot.is_user_authorized():
                engine.userbot = userbot
                engine.userbot_connected = True

                # Resolve DZHQ group entity specifically
                try:
                    engine.dzhq_group_entity = await userbot.get_entity(DZHQ_GROUP)
                    logger.info(f"✅ DZHQ Group resolved: {getattr(engine.dzhq_group_entity, 'title', DZHQ_GROUP)}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not resolve DZHQ Group ({DZHQ_GROUP}): {e}")

                try:
                    d_ent = await userbot.get_entity(DZHQ_BOT)
                    engine.dzhq_bot_id = d_ent.id
                except Exception:
                    logger.warning(f"⚠️ Could not resolve {DZHQ_BOT}")

                try:
                    a_ent = await userbot.get_entity(ALEX_BOT)
                    engine.alex_bot_id = a_ent.id
                except Exception:
                    logger.warning(f"⚠️ Could not resolve {ALEX_BOT}")

                setup_userbot_handlers(userbot)
                me = await userbot.get_me()
                logger.info(f"✅ Userbot connected: {me.first_name} (@{getattr(me, 'username', 'N/A')})")
            else:
                logger.error("❌ Telethon Session is not authorized. Check TELEGRAM_SESSION.")
        except Exception as e:
            logger.error(f"❌ Userbot startup failed: {e}")
    else:
        logger.warning("⚠️ Telethon Userbot credentials missing in .env (API_ID, API_HASH, or TELEGRAM_SESSION).")

    # 2. Launch Telegram Bot Polling (with Real Colored Buttons)
    polling_task = asyncio.create_task(run_bot_polling())

    # 3. Print Startup Banner
    detected_url = get_auto_public_url()
    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ProviderBotz Auto Bypass
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Flask: running (Port {PORT})
Public Bot API: {'online (@' + BOT_USERNAME + ')' if BOT_TOKEN else 'offline'}
Button Styles: PRIMARY (Blue), SUCCESS (Green), DANGER (Red)
Telethon Userbot: {'connected' if engine.userbot_connected else 'offline'}
DZHQ: Group Flow ({DZHQ_BOT} in {DZHQ_GROUP})
Alex DM: DM Flow ({ALEX_BOT})
Auto Public URL: {detected_url}
Health: {detected_url}/health
Mini App: {detected_url}/
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""", flush=True)

    await polling_task

def run_flask_thread():
    logger.info(f"Flask HTTP server starting on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False, threaded=True)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask_thread, daemon=True, name="FlaskThread")
    flask_thread.start()

    try:
        asyncio.run(main_async())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 ProviderBotz stopped.")
