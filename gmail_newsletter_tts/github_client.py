import shutil
from pathlib import Path

import config

_REPO_ROOT = Path(__file__).resolve().parent.parent
_AUDIO_DIR = _REPO_ROOT / "docs" / "audio"


class GitHubClient:
    """MP3 を docs/audio/ に保存して GitHub Pages で配信する。"""

    def __init__(self):
        _AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    def upload_mp3(self, file_path: str, filename: str) -> tuple[str, int]:
        """
        MP3 を docs/audio/ にコピーし、(GitHub Pages URL, ファイルサイズ) を返す。
        git add / push は podcast_feed.py._git_push() が担当。
        """
        dest = _AUDIO_DIR / filename
        shutil.copy2(file_path, dest)
        size = dest.stat().st_size
        owner, repo = config.GITHUB_REPO.split("/")
        url = f"https://{owner}.github.io/{repo}/audio/{filename}"
        return url, size
