"""
Kindle本 → ポッドキャスト変換パイプライン

Usage:
    python main.py \
        --url "https://read.amazon.co.jp/reader/..." \
        --title "インザメガチャーチ" \
        --max-pages 50 \
        [--no-push]
"""

import argparse
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# gmail_newsletter_tts の共通モジュールをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "gmail_newsletter_tts"))

import tts_client
import github_client as gc
import podcast_feed as pf

# kindle_book_tts ローカルの config/scraper
sys.path.insert(0, str(Path(__file__).parent))
import config
import kindle_scraper


# ── 章分割 ────────────────────────────────────────────────────────────────
_CHAPTER_RE = re.compile(
    r"(?m)^(?:"
    r"第[一二三四五六七八九十百\d]+[章節部編]"
    r"|Chapter\s*\d+"
    r"|CHAPTER\s*\d+"
    r"|第\d+話"
    r"|エピローグ|プロローグ|あとがき|まえがき"
    r")\s*[^\n]{0,50}$"
)


def _split_chapters(text: str, title: str) -> list[tuple[str, str]]:
    """
    テキストを章ごとに分割し、[(chapter_title, chapter_text), ...] を返す。
    章見出しが検出できない場合は全体を1エピソードとして返す。
    """
    matches = list(_CHAPTER_RE.finditer(text))
    if not matches:
        print("[main] 章見出しが検出できませんでした → 全体を1エピソードとして処理")
        return [(title, text)]

    chapters = []
    for i, m in enumerate(matches):
        ch_title = m.group().strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        ch_text = text[start:end].strip()
        if ch_text:
            chapters.append((ch_title, ch_text))

    print(f"[main] {len(chapters)} 章を検出")
    return chapters


# ── スクリプト変換（claude_newsletter_tts の script_converter を流用） ──
def _to_speech_script(text: str, chapter_title: str) -> str:
    """Claude API で口語スクリプトに変換。API Key がなければ素のテキストを返す。"""
    import anthropic

    if not config.ANTHROPIC_API_KEY:
        print("[main] ANTHROPIC_API_KEY 未設定 → スクリプト変換スキップ")
        return text

    _SYSTEM = """\
あなたは日本語ポッドキャストの優秀なナレーターです。
与えられた書籍のテキストを、内容を一切削らずに、プロのナレーターが自然に読み上げられるスクリプトに変換してください。

## 絶対に守るルール
- 元のコンテンツを削ったり要約したりしない
- 情報の追加もしない
- 変換するのは「表現の形式」だけ

## 読み上げの自然さ
- 文語体・箇条書きを口語の流れる文章に変換する
- 「〜である」「〜なのだ」→「〜です」「〜なんです」
- 見出しは「続いて〜についてです。」のように自然につなぐ
- 体言止めは文を補って完結させる

## 漢字の誤読防止（最重要）
- 文脈から正しい読みを判断し、誤読されやすい漢字はひらがなに置き換える
- 人名・地名はそのまま（TTSが対応）

## 数字・記号
- 「20倍」→「二十倍」
- 記号（■ // → 【】）は読まず、自然な文章として吸収する

## アルファベット・英語
- 一般的な略語はカタカナ読み（AI→エーアイ）
- 固有名詞はそのまま残す

## 出力
スクリプトのテキストのみ。説明・メタ情報・マークダウン記法は一切含めない。
"""

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=16000,
        system=_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"タイトル：{chapter_title}\n\n{text[:20000]}",
        }],
    )
    return response.content[0].text.strip()


# ── メイン処理 ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Kindle本をポッドキャストMP3に変換する")
    parser.add_argument("--url", required=True, help="Kindle Cloud Reader の URL")
    parser.add_argument("--title", required=True, help="本のタイトル")
    parser.add_argument("--max-pages", type=int, default=50, help="最大ページ数（デフォルト: 50）")
    parser.add_argument("--no-push", action="store_true", help="GitHub への push をスキップ")
    parser.add_argument("--skip-scrape", help="既存テキストファイルを使用（スクレイプをスキップ）")
    args = parser.parse_args()

    # ── Step 1: テキスト抽出 ──
    if args.skip_scrape:
        print(f"[main] スクレイプをスキップ: {args.skip_scrape}")
        with open(args.skip_scrape, encoding="utf-8") as f:
            raw_text = f.read()
    else:
        print(f"[main] Step 1: Kindle スクレイプ開始 (max_pages={args.max_pages})")
        raw_text = kindle_scraper.scrape(args.url, max_pages=args.max_pages)

        if not raw_text.strip():
            print("[main] ERROR: テキストが空でした。screenshots/ を確認してください。")
            sys.exit(1)

        # 生テキストを保存（再試行時に --skip-scrape で再利用できる）
        raw_path = Path(__file__).parent / f"raw_{args.title[:20].replace(' ', '_')}.txt"
        raw_path.write_text(raw_text, encoding="utf-8")
        print(f"[main] 生テキスト保存: {raw_path}")

    print(f"[main] 抽出テキスト: {len(raw_text)} 文字")

    # ── Step 2: 章分割 ──
    print("[main] Step 2: 章分割")
    chapters = _split_chapters(raw_text, args.title)

    # ── Step 3〜5: 章ごとに変換・TTS・アップロード ──
    github = gc.GitHubClient()
    feed = pf.PodcastFeed()

    for i, (ch_title, ch_text) in enumerate(chapters):
        ep_title = f"{args.title} - {ch_title}" if len(chapters) > 1 else args.title
        guid = f"kindle-{args.title}-{i+1}-{int(time.time())}"

        print(f"\n[main] Step 3: スクリプト変換 [{i+1}/{len(chapters)}] {ep_title}")
        script = _to_speech_script(ch_text, ep_title)

        print(f"[main] Step 4: TTS 変換 ({len(script)} 文字)")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        duration = tts_client.text_to_mp3(script, tmp_path)
        print(f"[main] MP3 生成完了: {duration:.1f} 秒")

        safe_title = re.sub(r'[^\w\-_]', '_', ep_title)[:60]
        filename = f"kindle_{safe_title}_{i+1:02d}.mp3"

        print(f"[main] Step 5: アップロード → {filename}")
        mp3_url, size = github.upload_mp3(tmp_path, filename)
        print(f"[main] URL: {mp3_url}")

        pub_date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
        feed.add_episode(
            guid=guid,
            title=ep_title,
            mp3_url=mp3_url,
            duration=duration,
            pub_date=pub_date,
            description=ch_text[:300],
            size=size,
        )

    # ── Step 6: feed.xml 更新・push ──
    if args.no_push:
        feed._write_xml()
        print("\n[main] --no-push: feed.xml を更新しましたが push はスキップしました")
    else:
        print("\n[main] Step 6: feed.xml 更新 & GitHub push")
        feed.save_and_push()
        print("[main] ✅ 完了！")

    print(f"\n[main] ポッドキャスト feed: {config.PODCAST_BASE_URL}/{config.PODCAST_FEED_PATH}")


if __name__ == "__main__":
    main()
