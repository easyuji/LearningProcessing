"""
Kindle本 → ポッドキャスト変換ツール

使い方:
  python main.py --url "https://read.amazon.co.jp/reader/..." --title "本のタイトル"
  python main.py --text-file extracted.txt --title "本のタイトル"  # 抽出済みテキストから再実行
"""

import argparse
import os
import re
import sys
import tempfile
from datetime import datetime
from email.utils import formatdate
from pathlib import Path

# gmail_newsletter_tts の共有モジュールをインポート
_SHARED = Path(__file__).parent.parent / "gmail_newsletter_tts"
sys.path.insert(0, str(_SHARED))

import config
from github_client import GitHubClient
from podcast_feed import PodcastFeed
from script_converter import convert_to_speech_script
from tts_client import text_to_mp3

from kindle_scraper import scrape_kindle_book


# ─────────────────────────────────────────
# テキスト処理ユーティリティ
# ─────────────────────────────────────────

def _slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:50].strip("-").lower()


def _split_chapters(text: str, chunk_size: int = 15000) -> list[dict]:
    """
    テキストを章ごとに分割する。
    章見出しを検出できない場合は chunk_size 文字ごとに均等分割する。
    """
    # ページ区切りマーカーを段落区切りに変換
    text = text.replace("\n\n---PAGE---\n\n", "\n\n")

    lines = text.split("\n")
    chapters: list[dict] = []
    current_title = "序文"
    current_lines: list[str] = []
    chapter_count = 0

    for line in lines:
        s = line.strip()

        # 章見出しパターン（日本語・英語両対応）
        is_heading = bool(
            re.match(r"^第[０-９0-9一二三四五六七八九十百千]+[章節話部]", s) or
            re.match(r"^Chapter\s+\d+", s, re.IGNORECASE) or
            re.match(r"^CHAPTER\s*\d+", s) or
            # 単独の数字（1〜999）または漢数字
            (re.match(r"^[0-9０-９]+$", s) and 1 <= len(s) <= 3) or
            re.match(r"^[一二三四五六七八九十百千]+$", s) or
            re.match(r"^第[一二三四五六七八九十百千]+$", s)
        )

        accumulated = "\n".join(current_lines).strip()
        if is_heading and len(accumulated) > 100:
            chapters.append({"title": current_title, "text": accumulated})
            chapter_count += 1
            current_title = s if s else f"章 {chapter_count}"
            current_lines = []
        else:
            current_lines.append(line)

    # 末尾を追加
    tail = "\n".join(current_lines).strip()
    if tail:
        chapters.append({"title": current_title, "text": tail})

    # 章が検出できなかった場合 → chunk_size 文字で均等分割
    if len(chapters) <= 1 and len(text) > chunk_size:
        print(f"  章の区切りを検出できませんでした。{chunk_size:,}文字ごとに分割します。")
        chapters = []
        parts: list[str] = []
        current = ""
        for sentence in re.split(r"(?<=[。！？\n])", text):
            if len(current) + len(sentence) > chunk_size and current:
                parts.append(current.strip())
                current = sentence
            else:
                current += sentence
        if current.strip():
            parts.append(current.strip())
        chapters = [{"title": f"パート{i}", "text": t} for i, t in enumerate(parts, 1)]

    return chapters


# ─────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kindle Cloud Reader の本をポッドキャストに変換します",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  # スクレイピングから実行
  python main.py \\
      --url "https://read.amazon.co.jp/reader/..." \\
      --title "インザメガチャーチ"

  # 抽出済みテキストから再実行（TTS設定変更時など）
  python main.py \\
      --text-file in-the-megachurch_extracted.txt \\
      --title "インザメガチャーチ"
""",
    )
    parser.add_argument("--url", help="Kindle Cloud Reader の URL")
    parser.add_argument("--title", required=True, help="本のタイトル")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=100,
        metavar="N",
        help="最大取得ページ数（デフォルト: 100）",
    )
    parser.add_argument(
        "--navigate",
        default="ArrowLeft",
        choices=["ArrowLeft", "ArrowRight"],
        help="ページ送りキー（日本語書籍=ArrowLeft, 英語書籍=ArrowRight）",
    )
    parser.add_argument(
        "--text-file",
        metavar="FILE",
        help="抽出済みテキストファイルを使用（スクレイピングをスキップ）",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=15000,
        metavar="N",
        help="章検出失敗時の分割文字数（デフォルト: 15000）",
    )

    args = parser.parse_args()

    if not args.text_file and not args.url:
        parser.error("--url か --text-file のどちらかが必要です")

    # ─── ステップ1: テキスト取得 ───
    if args.text_file:
        print(f"テキストファイルを読み込み中: {args.text_file}")
        full_text = Path(args.text_file).read_text(encoding="utf-8")
    else:
        print(f"本: 『{args.title}』")
        print(f"URL: {args.url}")
        full_text = scrape_kindle_book(
            url=args.url,
            max_pages=args.max_pages,
            navigate_key=args.navigate,
        )
        # 抽出テキストを保存（デバッグ・再実行用）
        text_save_path = Path(f"{_slugify(args.title)}_extracted.txt")
        text_save_path.write_text(full_text, encoding="utf-8")
        print(f"\n抽出テキストを保存しました: {text_save_path}")

    print(f"テキスト総量: {len(full_text):,} 文字")

    if len(full_text) < 100:
        print("ERROR: テキストが短すぎます。スクレイピングが正しく動作しなかった可能性があります。")
        print("  → ブラウザで本が開いているか確認し、--navigate ArrowRight もお試しください。")
        sys.exit(1)

    # ─── ステップ2: 章に分割 ───
    print("\n章を検出・分割中...")
    chapters = _split_chapters(full_text, chunk_size=args.chunk_size)
    print(f"検出した章数: {len(chapters)}")
    for i, ch in enumerate(chapters, 1):
        print(f"  {i:2d}. {ch['title']} ({len(ch['text']):,} 文字)")

    # ─── ステップ3: TTS → MP3 → ポッドキャスト ───
    github = GitHubClient()
    feed = PodcastFeed()
    pub_date = formatdate(usegmt=True)

    processed = 0
    for i, chapter in enumerate(chapters, 1):
        episode_title = f"{args.title}｜{chapter['title']}"
        episode_id = f"kindle-{_slugify(args.title)}-ch{i:03d}"

        if feed.has_episode(episode_id):
            print(f"\n章 {i} はフィードにあります（スキップ）")
            continue

        print(f"\n─── 章 {i}/{len(chapters)}: {chapter['title']} ({len(chapter['text']):,} 文字) ───")

        # Claude でスクリプト変換（読み上げ最適化）
        if config.ANTHROPIC_API_KEY:
            print("  Claude でスクリプト変換中...")
            try:
                script = convert_to_speech_script(chapter["text"], episode_title)
                print(f"  スクリプト: {len(script):,} 文字")
            except Exception as e:
                print(f"  スクリプト変換失敗（生テキストを使用）: {e}")
                script = chapter["text"]
        else:
            script = chapter["text"]

        # MP3 生成
        date_prefix = datetime.now().strftime("%Y%m%d")
        filename = f"{date_prefix}_{_slugify(episode_title)}.mp3"

        with tempfile.TemporaryDirectory() as tmpdir:
            mp3_path = os.path.join(tmpdir, filename)

            print("  MP3 生成中（Edge TTS / OpenAI TTS）...")
            try:
                duration = text_to_mp3(script, mp3_path)
            except Exception as e:
                print(f"  TTS 失敗: {e}")
                continue

            print(f"  長さ: {duration:.0f}秒 → GitHub にアップロード中...")
            try:
                mp3_url = github.upload_mp3(mp3_path, filename)
            except Exception as e:
                print(f"  アップロード失敗: {e}")
                continue

        feed.add_episode(
            guid=episode_id,
            title=episode_title,
            mp3_url=mp3_url,
            duration=duration,
            pub_date=pub_date,
            description=chapter["text"][:500],
        )
        processed += 1
        print(f"  完了: {mp3_url}")

    if processed > 0:
        print(f"\nポッドキャストフィードを更新中... ({processed} エピソード追加)")
        feed.save_and_push()
        print("完了！ポッドキャストアプリで確認してください。")
    else:
        print("\n新しいエピソードはありませんでした。")


if __name__ == "__main__":
    main()
