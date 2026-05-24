import os
import re
import sys
import tempfile
from datetime import datetime

import config
from cleanup import cleanup_old_audio
from gmail_client import GmailClient
from github_client import GitHubClient
from podcast_feed import PodcastFeed
from script_converter import convert_to_speech_script
from text_extractor import extract_text
from tts_client import text_to_mp3


def _slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:50].strip("-").lower()


def _check_env():
    missing = []
    if not config.GITHUB_TOKEN:
        missing.append("GITHUB_TOKEN")
    if not config.GITHUB_REPO:
        missing.append("GITHUB_REPO")
    if not config.GMAIL_APP_PASSWORD:
        missing.append("GMAIL_APP_PASSWORD")
    if missing:
        print(f"ERROR: Missing required config: {', '.join(missing)}")
        sys.exit(1)


def _mark_safe(gmail: GmailClient, message_id: str):
    try:
        gmail.mark_processed(message_id)
    except Exception as e:
        print(f"  Warning: mark_processed failed: {e}")


def main():
    _check_env()

    print("Initializing clients...")
    gmail = GmailClient()
    github = GitHubClient()
    feed = PodcastFeed()

    print("Fetching unprocessed newsletters...")
    try:
        emails = gmail.fetch_unprocessed()
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    if not emails:
        print("No unprocessed newsletters found.")
        return

    print(f"Found {len(emails)} newsletter(s) to process.")
    feed_updated = False

    for email in emails:
        subject = email["subject"]
        print(f"\n--- {subject} ---")

        if feed.has_episode(email["id"]):
            print("  Already in feed, skipping.")
            _mark_safe(gmail, email["id"])
            continue

        text = extract_text(email["html"], email["text"])
        if len(text) < 50:
            print(f"  Text too short ({len(text)} chars), skipping.")
            _mark_safe(gmail, email["id"])
            continue

        print(f"  Text: {len(text)} chars")

        # Claude APIで読み上げ用スクリプトに変換（APIキー未設定時はスキップ）
        if config.ANTHROPIC_API_KEY:
            print("  Converting to speech script via Claude...")
            try:
                script = convert_to_speech_script(text, subject)
                print(f"  Script: {len(script)} chars")
            except Exception as e:
                print(f"  Script conversion failed, using raw text: {e}")
                script = text
        else:
            script = text

        date_prefix = datetime.now().strftime("%Y%m%d")
        filename = f"{date_prefix}_{_slugify(subject)}.mp3"

        with tempfile.TemporaryDirectory() as tmpdir:
            mp3_path = os.path.join(tmpdir, filename)

            print("  Generating MP3 via Edge TTS...")
            try:
                duration = text_to_mp3(script, mp3_path)
            except Exception as e:
                print(f"  TTS failed: {e}")
                continue

            print(f"  Duration: {duration:.0f}s — uploading to GitHub Releases...")
            try:
                mp3_url = github.upload_mp3(mp3_path, filename)
            except Exception as e:
                print(f"  Upload failed: {e}")
                continue

        feed.add_episode(
            guid=email["id"],
            title=subject,
            mp3_url=mp3_url,
            duration=duration,
            pub_date=email["date"],
            description=text[:300],
        )
        _mark_safe(gmail, email["id"])
        feed_updated = True
        print(f"  Done: {mp3_url}")

    if feed_updated:
        print("\nPushing updated podcast feed...")
        feed.save_and_push()
        print(f"Feed saved to {config.PODCAST_FEED_PATH} and pushed.")
    else:
        print("\nNo new episodes added.")

    # 3ヶ月超の音声ファイルを自動削除
    print("\nCleaning up old audio files...")
    cleanup_old_audio(keep_days=90)


if __name__ == "__main__":
    main()
