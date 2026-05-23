import os
from dotenv import load_dotenv

load_dotenv()

CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH", "credentials.json")
TOKEN_PATH = os.getenv("TOKEN_PATH", "token.json")
NEWSLETTER_LABEL = os.getenv("NEWSLETTER_LABEL", "newsletter")
PROCESSED_LABEL = os.getenv("PROCESSED_LABEL", "newsletter-tts-done")

TTS_VOICE = os.getenv("TTS_VOICE", "ja-JP-NanamiNeural")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")
GITHUB_RELEASE_TAG = os.getenv("GITHUB_RELEASE_TAG", "podcast-mp3s")

PODCAST_TITLE = os.getenv("PODCAST_TITLE", "Newsletter Podcast")
PODCAST_DESCRIPTION = os.getenv("PODCAST_DESCRIPTION", "Gmail newsletters as audio")
PODCAST_AUTHOR = os.getenv("PODCAST_AUTHOR", "")
PODCAST_BASE_URL = os.getenv("PODCAST_BASE_URL", "")
PODCAST_FEED_PATH = os.getenv("PODCAST_FEED_PATH", "docs/podcast/feed.xml")
