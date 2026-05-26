import os
import re
import sys
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path

import config
from cleanup import cleanup_old_audio
from gmail_client import GmailClient
from github_client import GitHubClient
from notifier import send_notification
from podcast_feed import PodcastFeed
from script_converter import convert_to_speech_script
from text_normalizer import normalize as normalize_text
from text_extractor import extract_text
from tts_client import text_to_mp3


_REPO_ROOT = Path(__file__).resolve().parent.parent
_IMAGES_DIR = _REPO_ROOT / "docs" / "podcast" / "images"


def _prepare_episode_image(raw_url: str, slug: str, github: "GitHubClient") -> str:
    """
    メールから取得した画像URLを正方形 JPEG に変換して GitHub Releases にアップロード。
    Apple Podcasts 要件: 正方形・JPEG/PNG・1400〜3000px。
    アップロード後の Releases ダウンロード URL を返す。失敗時は空文字。
    """
    if not raw_url:
        return ""
    try:
        from PIL import Image
        import io
        import tempfile
        filename = f"ep_{slug}.jpg"

        req = urllib.request.Request(raw_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()

        img = Image.open(io.BytesIO(data)).convert("RGB")
        w, h = img.size
        side = min(w, h)
        img = img.crop(((w - side) // 2, (h - side) // 2,
                         (w + side) // 2, (h + side) // 2))
        size = min(max(side, 1400), 3000)
        img = img.resize((size, size), Image.LANCZOS)

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            img.save(tmp, "JPEG", quality=90, optimize=True)
            tmp_path = tmp.name

        # GitHub Releases にアップロード
        image_url, _ = github.upload_image(tmp_path, filename)
        os.unlink(tmp_path)
        return image_url
    except Exception as e:
        print(f"  画像変換スキップ: {e}")
        return ""


def _slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text)  # ASCII \w のみ（日本語除外）
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
    completed_episodes = []

    for email in emails:
        subject = email["subject"]
        print(f"\n--- {subject} ---")

        if feed.has_episode(email["id"]):
            print("  Already in feed, skipping.")
            _mark_safe(gmail, email["id"])
            continue

        text = extract_text(email["html"], email["text"])
        text = normalize_text(text)   # ルールベース正規化（APIキー不要）
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
        slug = _slugify(subject)
        filename = f"{date_prefix}_{slug}.mp3"

        # 画像を正方形 JPEG に変換して GitHub Releases にアップロード（Apple Podcasts 要件対応）
        image_url = _prepare_episode_image(email.get("image_url", ""), f"{date_prefix}_{slug[:30]}", github)
        if image_url:
            print(f"  エピソード画像: {image_url}")

        with tempfile.TemporaryDirectory() as tmpdir:
            mp3_path = os.path.join(tmpdir, filename)

            tts_engine = "OpenAI TTS" if config.OPENAI_API_KEY else "Edge TTS"
            print(f"  Generating MP3 via {tts_engine}...")
            try:
                duration = text_to_mp3(script, mp3_path)
            except Exception as e:
                print(f"  TTS failed: {e}")
                continue

            print(f"  Duration: {duration:.0f}s — saving to docs/audio/...")
            try:
                mp3_url, mp3_size = github.upload_mp3(mp3_path, filename)
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
            size=mp3_size,
            image_url=image_url,
        )
        _mark_safe(gmail, email["id"])
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

    # 3ヶ月超の音声ファイルを自動削除
    print("\nCleaning up old audio files...")
    cleanup_old_audio(keep_days=90)


if __name__ == "__main__":
    main()
