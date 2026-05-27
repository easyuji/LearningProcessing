import os
import subprocess
from dotenv import load_dotenv

load_dotenv()


def _keychain(account: str) -> str:
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", account, "-s", "gmail_newsletter_tts", "-w"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "easyuji@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD") or _keychain("GMAIL_APP_PASSWORD")
NEWSLETTER_LABEL = os.getenv("NEWSLETTER_LABEL", "newsletter")
PROCESSED_LABEL = os.getenv("PROCESSED_LABEL", "newsletter-tts-done")

TTS_VOICE_EDGE = os.getenv("TTS_VOICE_EDGE", "ja-JP-NanamiNeural")
TTS_VOICE_EN = os.getenv("TTS_VOICE_EN", "en-US-AriaNeural")   # 英語セクション用
TTS_VOICE_OPENAI = os.getenv("TTS_VOICE_OPENAI", "nova")  # nova/shimmer/alloy/echo/onyx/fable

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") or _keychain("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or _keychain("OPENAI_API_KEY")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or _keychain("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "easyuji/LearningProcessing")
GITHUB_RELEASE_TAG = os.getenv("GITHUB_RELEASE_TAG", "podcast-mp3s")

PODCAST_AUTHOR = os.getenv("PODCAST_AUTHOR", "Yuji")
PODCAST_BASE_URL = os.getenv("PODCAST_BASE_URL", "https://easyuji.github.io/LearningProcessing")

# 後方互換用（単一フィード時代の設定）
PODCAST_TITLE = os.getenv("PODCAST_TITLE", "My Newsletter Podcast")
PODCAST_DESCRIPTION = os.getenv("PODCAST_DESCRIPTION", "Gmailのメルマガを音声で聴く")
PODCAST_FEED_PATH = os.getenv("PODCAST_FEED_PATH", "docs/podcast/feed.xml")

# ── マルチフィード設定 ──────────────────────────────
# match_from: 差出人メールアドレスに含まれる文字列
_RAW_BASE = "https://raw.githubusercontent.com/easyuji/LearningProcessing/master"

FEED_ROUTES = [
    {
        "name": "lib",
        "match_from": "mag2premium.com",
        "title": "週刊Life is beautiful Podcast",
        "description": "中島聡のメルマガを音声で聴く",
        "feed_path": "docs/podcast/feed_lib.xml",
        "cover_url": f"{_RAW_BASE}/docs/podcast/images/ep_202605_915244.jpg",
    },
    {
        "name": "kinyu",
        "match_from": "yakan-hiko.com",
        "title": "週刊金融日記 Podcast",
        "description": "藤沢数希の週刊金融日記を音声で聴く",
        "feed_path": "docs/podcast/feed_kinyu.xml",
        "cover_url": f"{_RAW_BASE}/docs/podcast/images/ep_kinyu_nikki.jpg",
    },
    {
        "name": "yuna",
        "match_from": "note.com",
        "title": "ゆな先生のAIメルマガ Podcast",
        "description": "ゆな先生のnoteメルマガを音声で聴く",
        "feed_path": "docs/podcast/feed_yuna.xml",
        "cover_url": f"{_RAW_BASE}/docs/podcast/images/ep_202605_674094.jpg",
    },
]

def get_feed_route(sender: str) -> dict:
    """差出人メアドからフィードルートを返す。マッチしない場合は最初のルート。"""
    sender_lower = sender.lower()
    for route in FEED_ROUTES:
        if route["match_from"] in sender_lower:
            return route
    return FEED_ROUTES[0]
