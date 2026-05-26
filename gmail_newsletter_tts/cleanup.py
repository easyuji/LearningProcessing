"""古い音声ファイルをリポジトリから削除するクリーンアップモジュール。
main.py から自動呼び出し、または単独で実行可能。
"""
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import config

_ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


def _file_date(mp3: Path) -> datetime:
    """ファイル名の先頭8文字（YYYYMMDD）から日付を取得。取れない場合は更新日時。"""
    try:
        return datetime.strptime(mp3.name[:8], "%Y%m%d")
    except ValueError:
        return datetime.fromtimestamp(mp3.stat().st_mtime)


def _remove_feed_entries(feed_path: Path, filenames: set[str]):
    """feed.xml から削除対象ファイルに対応するエピソードを除去する。"""
    if not feed_path.exists():
        return

    ET.register_namespace("itunes", _ITUNES_NS)
    tree = ET.parse(feed_path)
    channel = tree.getroot().find("channel")
    if channel is None:
        return

    to_remove = []
    for item in channel.findall("item"):
        enc = item.find("enclosure")
        if enc is not None:
            filename = enc.get("url", "").split("/")[-1]
            if filename in filenames:
                to_remove.append(item)

    for item in to_remove:
        channel.remove(item)
        print(f"  フィードから削除: {item.findtext('title', '')[:60]}")

    if to_remove:
        try:
            ET.indent(tree, space="  ")
        except AttributeError:
            pass
        with open(feed_path, "wb") as f:
            f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            tree.write(f, encoding="utf-8", xml_declaration=False)


def cleanup_old_audio(keep_days: int = 90) -> list[str]:
    """keep_days 日より古い音声ファイルをgitから削除してpushする。
    削除したファイル名のリストを返す。
    """
    repo_root = Path(__file__).resolve().parent.parent
    audio_dir = repo_root / "docs" / "audio"
    feed_path = repo_root / config.PODCAST_FEED_PATH

    if not audio_dir.exists():
        return []

    cutoff = datetime.now() - timedelta(days=keep_days)
    old_files = [f for f in sorted(audio_dir.glob("*.mp3")) if _file_date(f) < cutoff]

    if not old_files:
        print(f"削除対象なし（{keep_days}日以内のファイルのみ）。")
        return []

    print(f"\n{keep_days}日超の音声ファイル {len(old_files)} 件を削除します:")
    for f in old_files:
        print(f"  {f.name}  ({_file_date(f).strftime('%Y-%m-%d')})")

    # フィードから対応エピソードを削除
    _remove_feed_entries(feed_path, {f.name for f in old_files})

    # git rm
    for f in old_files:
        subprocess.run(["git", "rm", "-f", str(f)], cwd=repo_root, check=True)

    # feed.xml も git add
    subprocess.run(["git", "add", str(feed_path)], cwd=repo_root, check=True)

    # 差分があればコミット・push
    result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo_root)
    if result.returncode != 0:
        filelist = "\n".join(f.name for f in old_files)
        subprocess.run(
            ["git", "commit", "-m",
             f"chore: {keep_days}日超の音声ファイルを削除（{len(old_files)}件）\n\n{filelist}"],
            cwd=repo_root, check=True,
        )
        token = subprocess.run(
            ["security", "find-generic-password", "-a", "GITHUB_TOKEN",
             "-s", "gmail_newsletter_tts", "-w"],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        remote_url = f"https://{token}@github.com/{config.GITHUB_REPO}.git"
        subprocess.run(
            ["git", "push", "-u", remote_url, "HEAD:master"],
            cwd=repo_root, check=True
        )
        print(f"削除・push完了（{len(old_files)}件）。")

    return [f.name for f in old_files]


if __name__ == "__main__":
    cleanup_old_audio(keep_days=90)
