"""
全メール（処理済み含む）を取得してfeedを再構築するリカバリスクリプト
"""
import imaplib
import email
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config
from gmail_client import _decode_header, _collect_parts
from podcast_feed import PodcastFeed
from text_extractor import extract_text
from github import Github
import subprocess

BASE_URL = "https://easyuji.github.io/LearningProcessing/audio"

# 件名キーワード → (url, size, duration_sec)
ASSET_MAP = [
    ("第731号",     f"{BASE_URL}/20260523_.-.731.-.vs.mp3",                              22283136, 4779),
    ("第730号",     f"{BASE_URL}/20260523_.-.730.-.mp3",                                 26582256, 4779),
    ("AI-Native",  f"{BASE_URL}/20260523_.life-is-beautiful-.ai-native.mp3",             21185568, 4191),
    ("Claude Max", f"{BASE_URL}/20260523_.life-is-beautiful-.ai.claude-max.mp3",         37420704, 6237),
    ("５月１２日", f"{BASE_URL}/20260523_.life-is-beautiful-.ai.mp3",                   26313264, 4386),
    ("核兵器",      f"{BASE_URL}/20260525_ai-kakuheiki.mp3",                             17811648, 2969),
]


def find_asset(subject: str):
    for keyword, url, size, duration in ASSET_MAP:
        if keyword in subject:
            return url, size, duration
    return None, 0, 0


def fetch_all_newsletters():
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
    imap.select(f'"{config.NEWSLETTER_LABEL}"')
    _, data = imap.uid("SEARCH", None, "ALL")
    uids = data[0].split() if data[0] else []

    emails = []
    for uid in uids:
        _, label_data = imap.uid("FETCH", uid, "(X-GM-MSGID)")
        if not label_data or not label_data[0]:
            continue
        raw = label_data[0].decode("utf-8", errors="replace")
        msgid_match = re.search(r"X-GM-MSGID (\d+)", raw)
        msg_id = msgid_match.group(1) if msgid_match else uid.decode()

        _, msg_data = imap.uid("FETCH", uid, "(RFC822)")
        if not msg_data or not msg_data[0]:
            continue
        msg = email.message_from_bytes(msg_data[0][1])

        subject = _decode_header(msg.get("Subject", "(no subject)"))
        date = msg.get("Date", "")
        html_parts, text_parts = [], []
        _collect_parts(msg, html_parts, text_parts)

        emails.append({
            "id": msg_id,
            "subject": subject,
            "date": date,
            "html": "\n".join(html_parts),
            "text": "\n".join(text_parts),
        })
    imap.logout()
    return emails


def main():
    print("Fetching all newsletters from Gmail...")
    emails = fetch_all_newsletters()
    print(f"Found {len(emails)} emails\n")

    # feedをゼロから再構築
    feed = PodcastFeed()
    feed._episodes = []  # 既存エントリをクリア

    for em in sorted(emails, key=lambda x: x["date"]):
        subject = em["subject"]
        url, size, duration = find_asset(subject)

        if url is None:
            print(f"⚠ No match: {subject[:40]}")
            continue

        text = extract_text(em["html"], em["text"])
        feed.add_episode(
            guid=em["id"],
            title=subject,
            mp3_url=url,
            duration=duration,
            pub_date=em["date"],
            description=text[:300],
            size=size,
        )
        print(f"✓ {subject[:50]}")
        print(f"  {url}")

    print(f"\n{len(feed._episodes)} episodes → saving and pushing...")
    feed.save_and_push()
    print("Done!")


if __name__ == "__main__":
    main()
