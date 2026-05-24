import os
import re
import sys
import tempfile
from datetime import datetime

import config
from gmail_client import GmailClient
from github_client import GitHubClient
from notifier import send_notification
from podcast_feed import PodcastFeed
from text_extractor import extract_text
from tts_client import text_to_mp3


def _slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:50].strip("-").lower()


def _check_env():
    missing = [k for k in ("GITHUB_TOKEN", "GITHUB_REPO") if not os.getenv(k)]
    if missing:
        print(f"ERROR: Missing required env vars: {', '.join(missing)}")
        sys.exit(1)


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
    completed_episodes = []

    for email in emails:
        subject = email["subject"]
        print(f"\n--- {subject} ---")

        if feed.has_episode(email["id"]):
            print("  Already in feed, skipping.")
            gmail.mark_processed(email["id"])
            continue

        text = extract_text(email["html"], email["text"])
        if len(text) < 50:
            print(f"  Text too short ({len(text)} chars), skipping.")
            gmail.mark_processed(email["id"])
            continue

        print(f"  Text: {len(text)} chars")

        date_prefix = datetime.now().strftime("%Y%m%d")
        filename = f"{date_prefix}_{_slugify(subject)}.mp3"

        with tempfile.TemporaryDirectory() as tmpdir:
            mp3_path = os.path.join(tmpdir, filename)

            print("  Generating MP3 via Google Cloud TTS...")
            try:
                duration = text_to_mp3(text, mp3_path)
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
        gmail.mark_processed(email["id"])
        feed_updated = True
        completed_episodes.append({
            "title": subject,
            "mp3_url": mp3_url,
            "duration": int(duration),
        })
        print(f"  Done: {mp3_url}")

    if feed_updated:
        print("\nPushing updated podcast feed...")
        feed.save_and_push()
        print(f"Feed saved to {config.PODCAST_FEED_PATH} and pushed.")
        print("\nSending notification email...")
        send_notification(completed_episodes)
    else:
        print("\nNo new episodes added.")


if __name__ == "__main__":
    main()
