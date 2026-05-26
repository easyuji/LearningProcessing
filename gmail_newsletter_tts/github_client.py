import os
import subprocess
import urllib.request
import urllib.error
import json
from pathlib import Path

import config

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _get_token() -> str:
    token = config.GITHUB_TOKEN
    if not token:
        raise RuntimeError("GITHUB_TOKEN が設定されていません")
    return token


class GitHubClient:
    """MP3 を GitHub Releases にアップロードして配信する。"""

    def __init__(self):
        self._token = _get_token()
        self._owner, self._repo = config.GITHUB_REPO.split("/")
        self._tag = config.GITHUB_RELEASE_TAG
        self._release_id: int | None = None

    def _get_or_create_release(self) -> int:
        """既存リリースを取得、なければ作成して release_id を返す。"""
        if self._release_id is not None:
            return self._release_id

        url = f"https://api.github.com/repos/{self._owner}/{self._repo}/releases/tags/{self._tag}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
                self._release_id = data["id"]
                return self._release_id
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise

        # 存在しない場合は作成
        payload = json.dumps({
            "tag_name": self._tag,
            "name": "Podcast MP3s",
            "body": "Gmail newsletter TTS audio files",
            "draft": False,
            "prerelease": False,
        }).encode()
        req = urllib.request.Request(
            f"https://api.github.com/repos/{self._owner}/{self._repo}/releases",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            self._release_id = data["id"]
            return self._release_id

    def _delete_existing_asset(self, release_id: int, filename: str):
        """同名アセットが既にあれば削除する（再アップロード時の重複防止）。"""
        url = f"https://api.github.com/repos/{self._owner}/{self._repo}/releases/{release_id}/assets"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req) as resp:
            assets = json.loads(resp.read())

        for asset in assets:
            if asset["name"] == filename:
                del_req = urllib.request.Request(
                    f"https://api.github.com/repos/{self._owner}/{self._repo}/releases/assets/{asset['id']}",
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Accept": "application/vnd.github+json",
                    },
                    method="DELETE",
                )
                urllib.request.urlopen(del_req).close()
                break

    def upload_mp3(self, file_path: str, filename: str) -> tuple[str, int]:
        """
        MP3 を GitHub Releases にアップロードし、(ダウンロード URL, ファイルサイズ) を返す。
        """
        release_id = self._get_or_create_release()
        self._delete_existing_asset(release_id, filename)

        size = os.path.getsize(file_path)
        upload_url = (
            f"https://uploads.github.com/repos/{self._owner}/{self._repo}"
            f"/releases/{release_id}/assets?name={filename}"
        )
        with open(file_path, "rb") as f:
            data = f.read()

        req = urllib.request.Request(
            upload_url,
            data=data,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "audio/mpeg",
                "Content-Length": str(size),
            },
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())

        download_url = (
            f"https://github.com/{self._owner}/{self._repo}"
            f"/releases/download/{self._tag}/{filename}"
        )
        return download_url, size
