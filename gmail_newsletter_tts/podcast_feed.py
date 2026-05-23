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
    def __init__(self):
        self._feed_path = Path(config.PODCAST_FEED_PATH)
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
                self._episodes.append({"guid": item.findtext("guid") or ""})
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
    ):
        self._episodes.append(
            {
                "guid": guid,
                "title": title,
                "mp3_url": mp3_url,
                "duration": int(duration),
                "pub_date": _rfc2822(_parse_pub_date(pub_date)),
                "description": description[:500],
            }
        )

    def save_and_push(self):
        self._write_xml()
        self._git_push()

    def _write_xml(self):
        ET.register_namespace("itunes", _ITUNES_NS)
        root = ET.Element("rss", {"version": "2.0", "xmlns:itunes": _ITUNES_NS})
        channel = ET.SubElement(root, "channel")

        def ch(tag: str, text: str):
            el = ET.SubElement(channel, tag)
            el.text = text

        ch("title", config.PODCAST_TITLE)
        ch("description", config.PODCAST_DESCRIPTION)
        ch("language", "ja")
        ch("link", config.PODCAST_BASE_URL)
        ch(_itunes("author"), config.PODCAST_AUTHOR)
        ch(_itunes("explicit"), "no")

        img = ET.SubElement(channel, _itunes("image"))
        img.set("href", f"{config.PODCAST_BASE_URL}/podcast/cover.jpg")

        for ep in reversed(self._episodes):
            if "mp3_url" not in ep:
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

            enc = ET.SubElement(item, "enclosure")
            enc.set("url", ep["mp3_url"])
            enc.set("type", "audio/mpeg")
            enc.set("length", "0")

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
        subprocess.run(["git", "add", str(self._feed_path)], cwd=repo_root, check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo_root)
        if result.returncode == 0:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(
            ["git", "commit", "-m", f"chore: update podcast feed [{now}]"],
            cwd=repo_root,
            check=True,
        )
        subprocess.run(["git", "push", "-u", "origin", "HEAD:main"], cwd=repo_root, check=True)
