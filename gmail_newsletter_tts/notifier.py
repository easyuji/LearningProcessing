"""処理完了時にGmailで自分宛てに通知メールを送る。"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config


def send_notification(episodes: list[dict]):
    """変換完了したエピソードリストをメールで通知する。

    episodes: [{"title": ..., "mp3_url": ..., "duration": ...}, ...]
    """
    if not episodes:
        return
    if not config.GMAIL_APP_PASSWORD:
        print("  通知スキップ（GMAIL_APP_PASSWORD未設定）")
        return

    subject = f"🎙️ ポッドキャスト更新：{len(episodes)}件の新着エピソード"

    lines = ["新しいメルマガが音声変換されてポッドキャストに追加されました。\n"]
    for ep in episodes:
        minutes = ep["duration"] // 60
        seconds = ep["duration"] % 60
        lines.append(f"📌 {ep['title']}")
        lines.append(f"   再生時間：{minutes}分{seconds:02d}秒")
        lines.append(f"   URL：{ep['mp3_url']}")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"フィード：{config.PODCAST_BASE_URL}/podcast/feed.xml")

    body = "\n".join(lines)

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = config.GMAIL_ADDRESS
    msg["To"] = config.GMAIL_ADDRESS
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print(f"  通知メール送信済み → {config.GMAIL_ADDRESS}")
    except Exception as e:
        print(f"  通知メール送信失敗（処理自体は完了）: {e}")
