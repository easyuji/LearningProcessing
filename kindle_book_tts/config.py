import os
import subprocess
from dotenv import load_dotenv

load_dotenv()


def _keychain(account: str, service: str = "kindle_book_tts") -> str:
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        # gmail_newsletter_tts のキーチェーンも参照
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-a", account, "-s", "gmail_newsletter_tts", "-w"],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") or _keychain("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or _keychain("OPENAI_API_KEY")

TTS_VOICE_EDGE = os.getenv("TTS_VOICE_EDGE", "ja-JP-NanamiNeural")
TTS_VOICE_OPENAI = os.getenv("TTS_VOICE_OPENAI", "nova")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or _keychain("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "easyuji/LearningProcessing")

PODCAST_TITLE = os.getenv("PODCAST_TITLE", "Kindle読書ポッドキャスト")
PODCAST_DESCRIPTION = os.getenv("PODCAST_DESCRIPTION", "Kindle本を音声で聴く")
PODCAST_AUTHOR = os.getenv("PODCAST_AUTHOR", "Yuji")
PODCAST_BASE_URL = os.getenv("PODCAST_BASE_URL", "https://easyuji.github.io/LearningProcessing")
PODCAST_FEED_PATH = os.getenv("PODCAST_FEED_PATH", "docs/podcast/kindle_feed.xml")

# Kindle Cloud Reader 設定
KINDLE_PROFILE_DIR = os.path.expanduser("~/.kindle_playwright_profile")
