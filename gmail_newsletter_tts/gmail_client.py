import base64
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config

_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def _build_service():
    creds = None
    if os.path.exists(config.TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(config.TOKEN_PATH, _SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(config.CREDENTIALS_PATH, _SCOPES)
            creds = flow.run_local_server(port=0)
        with open(config.TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _collect_parts(payload, html_parts, text_parts):
    mime = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")
    if body_data:
        decoded = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
        if mime == "text/html":
            html_parts.append(decoded)
        elif mime == "text/plain":
            text_parts.append(decoded)
    for part in payload.get("parts", []):
        _collect_parts(part, html_parts, text_parts)


def _parse_message(msg):
    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    html_parts, text_parts = [], []
    _collect_parts(msg["payload"], html_parts, text_parts)
    return {
        "id": msg["id"],
        "subject": headers.get("Subject", "(no subject)"),
        "date": headers.get("Date", ""),
        "html": "\n".join(html_parts),
        "text": "\n".join(text_parts),
    }


class GmailClient:
    def __init__(self):
        self._service = _build_service()
        self._label_cache: dict[str, str] = {}
        self._refresh_label_cache()
        self._ensure_processed_label()

    def _refresh_label_cache(self):
        labels = self._service.users().labels().list(userId="me").execute().get("labels", [])
        self._label_cache = {l["name"]: l["id"] for l in labels}

    def _ensure_processed_label(self):
        if config.PROCESSED_LABEL not in self._label_cache:
            created = self._service.users().labels().create(
                userId="me",
                body={
                    "name": config.PROCESSED_LABEL,
                    "labelListVisibility": "labelHide",
                    "messageListVisibility": "hide",
                },
            ).execute()
            self._label_cache[config.PROCESSED_LABEL] = created["id"]

    def _label_id(self, name: str) -> str:
        if name not in self._label_cache:
            self._refresh_label_cache()
        if name not in self._label_cache:
            raise ValueError(f"Gmail label not found: '{name}'. Please create it in Gmail first.")
        return self._label_cache[name]

    def fetch_unprocessed(self) -> list[dict]:
        newsletter_id = self._label_id(config.NEWSLETTER_LABEL)
        results = self._service.users().messages().list(
            userId="me",
            labelIds=[newsletter_id],
            q=f"-label:{config.PROCESSED_LABEL}",
        ).execute()
        emails = []
        for ref in results.get("messages", []):
            msg = self._service.users().messages().get(
                userId="me", id=ref["id"], format="full"
            ).execute()
            emails.append(_parse_message(msg))
        return emails

    def mark_processed(self, message_id: str):
        self._service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": [self._label_id(config.PROCESSED_LABEL)]},
        ).execute()
