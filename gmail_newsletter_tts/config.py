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

TTS_VOICE = os.getenv("TTS_VOICE", "ja-JP-NanamiNeural")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or _keychain("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "easyuji/LearningProcessing")
GITHUB_RELEASE_TAG = os.getenv("GITHUB_RELEASE_TAG", "podcast-mp3s")

PODCAST_TITLE = os.getenv("PODCAST_TITLE", "My Newsletter Podcast")
PODCAST_DESCRIPTION = os.getenv("PODCAST_DESCRIPTION", "Gmailのメルマガを音声で聴く")
PODCAST_AUTHOR = os.getenv("PODCAST_AUTHOR", "Yuji")
PODCAST_BASE_URL = os.getenv("PODCAST_BASE_URL", "https://easyuji.github.io/LearningProcessing")
PODCAST_FEED_PATH = os.getenv("PODCAST_FEED_PATH", "docs/podcast/feed.xml")
