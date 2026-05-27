import email
import imaplib
import re
from email.header import decode_header as _decode_raw

from bs4 import BeautifulSoup

import config


def _decode_header(value: str) -> str:
    parts = _decode_raw(value or "")
    decoded = ""
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded += part.decode(charset or "utf-8", errors="replace")
        else:
            decoded += part
    return decoded


def _extract_image_url(html: str) -> str:
    """メール HTML から最初の外部画像 URL を取得する。見つからなければ空文字。"""
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "lxml")
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if src.startswith("http") and not src.startswith("data:"):
                # 1px トラッキングピクセルを除外（width/height が 1 以下）
                w = img.get("width", "")
                h = img.get("height", "")
                if str(w) in ("1", "0") or str(h) in ("1", "0"):
                    continue
                return src
    except Exception:
        pass
    return ""


def _collect_parts(msg, html_parts: list, text_parts: list):
    for part in msg.walk():
        ctype = part.get_content_type()
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        charset = part.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace")
        if ctype == "text/html":
            html_parts.append(text)
        elif ctype == "text/plain":
            text_parts.append(text)


class GmailClient:
    def __init__(self):
        self._imap = imaplib.IMAP4_SSL("imap.gmail.com")
        self._imap.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        self._uid_map: dict[str, bytes] = {}  # msg_id -> imap uid

    def fetch_unprocessed(self) -> list[dict]:
        self._imap.select(f'"{config.NEWSLETTER_LABEL}"')
        _, data = self._imap.uid("SEARCH", None, "ALL")
        uids = data[0].split() if data[0] else []

        emails = []
        for uid in uids:
            _, label_data = self._imap.uid("FETCH", uid, "(X-GM-LABELS X-GM-MSGID)")
            if not label_data or not label_data[0]:
                continue
            raw = label_data[0].decode("utf-8", errors="replace")

            if config.PROCESSED_LABEL in raw:
                continue

            msgid_match = re.search(r"X-GM-MSGID (\d+)", raw)
            msg_id = msgid_match.group(1) if msgid_match else uid.decode()

            _, msg_data = self._imap.uid("FETCH", uid, "(RFC822)")
            if not msg_data or not msg_data[0]:
                continue
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = _decode_header(msg.get("Subject", "(no subject)"))
            date = msg.get("Date", "")

            html_parts, text_parts = [], []
            _collect_parts(msg, html_parts, text_parts)

            html_combined = "\n".join(html_parts)
            self._uid_map[msg_id] = uid
            emails.append({
                "id": msg_id,
                "subject": subject,
                "date": date,
                "from": msg.get("From", ""),
                "html": html_combined,
                "text": "\n".join(text_parts),
                "image_url": _extract_image_url(html_combined),
            })

        return emails

    def _ensure_connected(self):
        try:
            self._imap.noop()
        except Exception:
            self._imap = imaplib.IMAP4_SSL("imap.gmail.com")
            self._imap.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        self._imap.select(f'"{config.NEWSLETTER_LABEL}"')

    def mark_processed(self, message_id: str):
        uid = self._uid_map.get(message_id)
        if uid is None:
            return
        self._ensure_connected()
        self._imap.uid("STORE", uid, "+X-GM-LABELS", f'("{config.PROCESSED_LABEL}")')

    def __del__(self):
        try:
            self._imap.logout()
        except Exception:
            pass
