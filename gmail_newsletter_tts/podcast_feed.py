import subprocess
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import config

_ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


def _parse_pub_date(date_str: str) -> datetime:
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return datetime.now(timezone.utc)


def _rfc2822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def _itunes(tag: str) -> str:
    return f"{{{_ITUNES_NS}}}{tag}"


class PodcastFeed:
    def __init__(self, route=None):
        """
        route: config.FEED_ROUTES の要素。None の場合はレガシー単一フィード設定を使用。
        """
        repo_root = Path(__file__).resolve().parent.parent
        self._route = route or {
            "title": config.PODCAST_TITLE,
            "description": config.PODCAST_DESCRIPTION,
            "cover_url": f"{config.PODCAST_BASE_URL}/podcast/cover.jpg",
            "feed_path": config.PODCAST_FEED_PATH,
        }
        self._feed_path = repo_root / self._route["feed_path"]
        self._feed_path.parent.mkdir(parents=True, exist_ok=True)
        self._episodes: list[dict] = []
        self._load_existing()

    def _load_existing(self):
        if not self._feed_path.exists():
            return
        try:
            ET.register_namespace("itunes", _ITUNES_NS)
            tree = ET.parse(self._feed_path)
            channel = tree.getroot().find("channel")
            if channel is None:
                return
            for item in channel.findall("item"):
                enc = item.find("enclosure")
                dur = item.find(_itunes("duration"))
                img = item.find(_itunes("image"))
                self._episodes.append({
                    "guid": item.findtext("guid") or "",
                    "title": item.findtext("title") or "",
                    "mp3_url": enc.get("url") if enc is not None else "",
                    "size": int(enc.get("length", 0)) if enc is not None else 0,
                    "duration": int(dur.text) if dur is not None and dur.text else 0,
                    "pub_date": item.findtext("pubDate") or "",
                    "description": item.findtext("description") or "",
                    "image_url": img.get("href", "") if img is not None else "",
                })
        except Exception:
            pass

    def has_episode(self, guid: str) -> bool:
        return any(e["guid"] == guid for e in self._episodes)

    def add_episode(
        self,
        guid: str,
        title: str,
        mp3_url: str,
        duration: float,
        pub_date: str,
        description: str,
        size: int = 0,
        image_url: str = "",
    ):
        self._episodes.append(
            {
                "guid": guid,
                "title": title,
                "mp3_url": mp3_url,
                "duration": int(duration),
                "pub_date": _rfc2822(_parse_pub_date(pub_date)),
                "description": description[:500],
                "size": size,
                "image_url": image_url,
            }
        )

    def save_and_push(self):
        self._write_xml()
        self._git_push()

    def _write_xml(self):
        ET.register_namespace("itunes", _ITUNES_NS)
        root = ET.Element("rss", {"version": "2.0"})
        channel = ET.SubElement(root, "channel")

        def ch(tag: str, text: str):
            el = ET.SubElement(channel, tag)
            el.text = text

        ch("title", self._route["title"])
        ch("description", self._route["description"])
        ch("language", "ja")
        ch("link", config.PODCAST_BASE_URL)
        ch(_itunes("author"), config.PODCAST_AUTHOR)
        ch(_itunes("explicit"), "no")

        # カテゴリ（Apple Podcasts 登録に必須）
        cat = ET.SubElement(channel, _itunes("category"))
        cat.set("text", "Technology")

        # チャンネルカバー画像
        img = ET.SubElement(channel, _itunes("image"))
        img.set("href", self._route["cover_url"])

        for ep in reversed(self._episodes):
            if not ep.get("mp3_url"):
                continue
            item = ET.SubElement(channel, "item")

            def it(tag: str, text: str):
                el = ET.SubElement(item, tag)
                el.text = str(text)

            it("title", ep["title"])
            it("description", ep["description"])
            it("pubDate", ep["pub_date"])
            it("guid", ep["guid"])
            it(_itunes("duration"), str(ep["duration"]))

            # エピソードごとのアートワーク（Apple Podcasts対応）
            if ep.get("image_url"):
                ep_img = ET.SubElement(item, _itunes("image"))
                ep_img.set("href", ep["image_url"])

            enc = ET.SubElement(item, "enclosure")
            enc.set("url", ep["mp3_url"])
            enc.set("type", "audio/mpeg")
            enc.set("length", str(ep.get("size", 0)))

        tree = ET.ElementTree(root)
        try:
            ET.indent(tree, space="  ")
        except AttributeError:
            pass

        with open(self._feed_path, "wb") as f:
            f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            tree.write(f, encoding="utf-8", xml_declaration=False)

    def _git_push(self):
        repo_root = Path(__file__).resolve().parent.parent
        audio_dir = repo_root / "docs" / "audio"
        images_dir = repo_root / "docs" / "podcast" / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        # 全フィードファイルを git add（他ルートのフィードも存在すれば含める）
        feed_files = list((repo_root / "docs" / "podcast").glob("feed*.xml"))
        subprocess.run(
            ["git", "add", *[str(f) for f in feed_files], str(audio_dir), str(images_dir)],
            cwd=repo_root, check=True
        )
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo_root)
        if result.returncode == 0:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(
            ["git", "commit", "-m", f"chore: update podcast feed [{now}]"],
            cwd=repo_root,
            check=True,
        )
        token = subprocess.run(
            ["security", "find-generic-password", "-a", "GITHUB_TOKEN", "-s", "gmail_newsletter_tts", "-w"],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        repo = config.GITHUB_REPO
        remote_url = f"https://{token}@github.com/{repo}.git"
        subprocess.run(["git", "push", "-u", remote_url, "HEAD:master"], cwd=repo_root, check=True)
