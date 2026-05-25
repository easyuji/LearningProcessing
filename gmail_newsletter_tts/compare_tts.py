"""
TTS品質比較スクリプト
4パターンの音声を生成してローカルで聴き比べる

使い方:
  python3 compare_tts.py                      # デフォルトのサンプルテキストで比較
  python3 compare_tts.py --text "任意のテキスト"
  python3 compare_tts.py --file input.txt

生成ファイル:
  compare_out/A_edge_raw.mp3         Edge TTS（生テキスト）
  compare_out/B_edge_claude.mp3      Edge TTS + Claude口語変換
  compare_out/C_openai_raw.mp3       OpenAI TTS（生テキスト）
  compare_out/D_openai_claude.mp3    OpenAI TTS + Claude口語変換

注意:
  - Edge TTSはAPIキー不要（無料）
  - OpenAI TTSはOPENAI_API_KEY必要
  - Claude変換はANTHROPIC_API_KEY必要
  - APIキー未設定のパターンはスキップされます
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

# ─── サンプルテキスト（メルマガ風） ───────────────────────────────────────────
SAMPLE_TEXT = """\
■ 今日のトピック：AIと経済の未来

第731号をお届けします。

本日は、AIが労働市場に与える影響について考えます。
McKinseyの最新レポートによると、2030年までに全職種の約30%がAIで自動化される可能性があります。
一方で、新たな職種も$211billionの市場規模で誕生するとされています。

重要なポイントは3つです。
1. ホワイトカラー職でも影響が大きい
2. 創造性・共感力が求められる職は残る
3. 「AIを使いこなす人」と「使えない人」の格差が拡大

今週の明日、経済産業省が新しいAI戦略を発表する予定です。
大人も子供も、AI時代のスキルを今から準備することが重要です。

詳しくは以下のリンクからご確認ください。
https://example.com/ai-report-2026

以上、今日もお読みいただきありがとうございました。
"""


# ─── Edge TTS ────────────────────────────────────────────────────────────────
async def _edge_tts_async(text: str, output_path: str, voice: str):
    import edge_tts
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(output_path)


def run_edge_tts(text: str, output_path: str, voice: str = "ja-JP-NanamiNeural"):
    asyncio.run(_edge_tts_async(text, output_path, voice))


# ─── OpenAI TTS ──────────────────────────────────────────────────────────────
def run_openai_tts(text: str, output_path: str, api_key: str, voice: str = "nova"):
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    # 4000文字でチャンク分割
    import re
    max_chars = 4000
    sentences = re.split(r"(?<=[。！？\n])", text)
    chunks, current = [], ""
    for s in sentences:
        if len(current) + len(s) > max_chars:
            if current:
                chunks.append(current.strip())
            current = s
        else:
            current += s
    if current.strip():
        chunks.append(current.strip())
    chunks = chunks or [text[:max_chars]]

    audio_bytes = b""
    for chunk in chunks:
        response = client.audio.speech.create(
            model="tts-1-hd",
            voice=voice,
            input=chunk,
            response_format="mp3",
        )
        audio_bytes += response.read()

    with open(output_path, "wb") as f:
        f.write(audio_bytes)


# ─── Claude 口語変換 ──────────────────────────────────────────────────────────
_SYSTEM = """\
あなたは日本語ポッドキャストの優秀なナレーターです。
与えられたメルマガのテキストを、内容を一切削らずに、プロのナレーターが自然に読み上げられるスクリプトに変換してください。

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
- 「今日」→ 日付文脈なら「きょう」、挨拶文脈なら「こんにち」
- 「明日」→「あした」（「みょうにち」ではなく）
- 「一日」→ 日付なら「ついたち」、期間なら「いちにち」
- 「大人」→「おとな」
- 「今週」→「こんしゅう」、「先週」→「せんしゅう」、「今月」→「こんげつ」

## 数字・記号
- 「第731号」→「第七百三十一号」
- 「$211billion」→「二千百十億ドル」
- 「20倍」→「二十倍」、「2〜3日」→「二、三日」
- 「%」→「パーセント」
- 記号（■ // → 【】）は読まず、自然な文章として吸収する

## アルファベット・英語
- 一般的な略語はカタカナ読み（AI→エーアイ、GDP→ジーディーピー）
- 固有名詞（ChatGPT、Claude等）はそのまま残す

## 出力
スクリプトのテキストのみ。説明・メタ情報・マークダウン記法は一切含めない。
"""


def run_claude_convert(text: str, api_key: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=16000,
        system=_SYSTEM,
        messages=[{"role": "user", "content": f"タイトル：比較サンプル\n\n{text}"}],
    )
    return response.content[0].text.strip()


# ─── メイン ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="TTS品質比較（4パターン生成）")
    parser.add_argument("--text", help="比較するテキスト（省略時はサンプル使用）")
    parser.add_argument("--file", help="テキストファイルパス")
    parser.add_argument("--edge-voice", default="ja-JP-NanamiNeural",
                        help="Edge TTSの声（デフォルト: ja-JP-NanamiNeural）\n"
                             "他の選択肢: ja-JP-KeitaNeural（男性）")
    parser.add_argument("--openai-voice", default="nova",
                        help="OpenAI TTSの声（デフォルト: nova）\n"
                             "他の選択肢: alloy/echo/fable/onyx/shimmer")
    args = parser.parse_args()

    # テキスト決定
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.text:
        text = args.text
    else:
        text = SAMPLE_TEXT

    # APIキー取得
    openai_key = os.getenv("OPENAI_API_KEY", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    # macOSキーチェーンからも試みる
    def _keychain(account: str) -> str:
        import subprocess
        try:
            r = subprocess.run(
                ["security", "find-generic-password", "-a", account,
                 "-s", "gmail_newsletter_tts", "-w"],
                capture_output=True, text=True, check=True
            )
            return r.stdout.strip()
        except Exception:
            return ""

    if not openai_key:
        openai_key = _keychain("OPENAI_API_KEY")
    if not anthropic_key:
        anthropic_key = _keychain("ANTHROPIC_API_KEY")

    # 出力ディレクトリ
    out_dir = Path("compare_out")
    out_dir.mkdir(exist_ok=True)

    print(f"\n{'='*55}")
    print(f"  TTS 品質比較スクリプト")
    print(f"{'='*55}")
    print(f"  テキスト長 : {len(text)} 文字")
    print(f"  Edge voice : {args.edge_voice}")
    print(f"  OpenAI voice: {args.openai_voice}")
    print(f"  OpenAI API : {'✅ あり' if openai_key else '❌ なし（スキップ）'}")
    print(f"  Claude API : {'✅ あり' if anthropic_key else '❌ なし（変換スキップ）'}")
    print(f"{'='*55}\n")

    # Claude口語変換（一度だけ実行）
    converted_text = None
    if anthropic_key:
        print("🤖 [Claude] 口語変換中...")
        t0 = time.time()
        converted_text = run_claude_convert(text, anthropic_key)
        print(f"   完了 ({time.time()-t0:.1f}秒)\n")
        print("--- 変換後テキスト（先頭200文字）---")
        print(converted_text[:200], "...")
        print("------------------------------------\n")
    else:
        print("⚠️  ANTHROPIC_API_KEY なし → BパターンとDパターンは生テキストで生成\n")

    results = []

    # A: Edge TTS + 生テキスト
    path_a = str(out_dir / "A_edge_raw.mp3")
    print("🔊 [A] Edge TTS（生テキスト）...")
    t0 = time.time()
    try:
        run_edge_tts(text, path_a, args.edge_voice)
        elapsed = time.time() - t0
        size = os.path.getsize(path_a) // 1024
        print(f"   ✅ 完了 ({elapsed:.1f}秒, {size}KB) → {path_a}")
        results.append(("A", "Edge TTS + 生テキスト", path_a))
    except Exception as e:
        print(f"   ❌ エラー: {e}")

    # B: Edge TTS + Claude変換
    path_b = str(out_dir / "B_edge_claude.mp3")
    b_text = converted_text if converted_text else text
    label_b = "Edge TTS + Claude変換" if converted_text else "Edge TTS + 生テキスト（Claude未設定）"
    print(f"\n🔊 [B] {label_b}...")
    t0 = time.time()
    try:
        run_edge_tts(b_text, path_b, args.edge_voice)
        elapsed = time.time() - t0
        size = os.path.getsize(path_b) // 1024
        print(f"   ✅ 完了 ({elapsed:.1f}秒, {size}KB) → {path_b}")
        results.append(("B", label_b, path_b))
    except Exception as e:
        print(f"   ❌ エラー: {e}")

    # C: OpenAI TTS + 生テキスト
    if openai_key:
        path_c = str(out_dir / "C_openai_raw.mp3")
        print(f"\n🔊 [C] OpenAI TTS（生テキスト）...")
        t0 = time.time()
        try:
            run_openai_tts(text, path_c, openai_key, args.openai_voice)
            elapsed = time.time() - t0
            size = os.path.getsize(path_c) // 1024
            print(f"   ✅ 完了 ({elapsed:.1f}秒, {size}KB) → {path_c}")
            results.append(("C", "OpenAI TTS + 生テキスト", path_c))
        except Exception as e:
            print(f"   ❌ エラー: {e}")

        # D: OpenAI TTS + Claude変換
        path_d = str(out_dir / "D_openai_claude.mp3")
        d_text = converted_text if converted_text else text
        label_d = "OpenAI TTS + Claude変換" if converted_text else "OpenAI TTS + 生テキスト（Claude未設定）"
        print(f"\n🔊 [D] {label_d}...")
        t0 = time.time()
        try:
            run_openai_tts(d_text, path_d, openai_key, args.openai_voice)
            elapsed = time.time() - t0
            size = os.path.getsize(path_d) // 1024
            print(f"   ✅ 完了 ({elapsed:.1f}秒, {size}KB) → {path_d}")
            results.append(("D", label_d, path_d))
        except Exception as e:
            print(f"   ❌ エラー: {e}")
    else:
        print("\n⏭️  [C][D] OpenAI TTS → スキップ（OPENAI_API_KEY なし）")

    # 結果サマリー
    print(f"\n{'='*55}")
    print("  生成完了！以下のファイルを聴き比べてください：")
    print(f"{'='*55}")
    for pat, label, path in results:
        print(f"  [{pat}] {label}")
        print(f"       → {path}")
    print()

    # macOSなら自動でFinderを開く
    if sys.platform == "darwin" and results:
        import subprocess
        subprocess.run(["open", str(out_dir)])
        print("  📂 Finderで compare_out/ を開きました\n")


if __name__ == "__main__":
    main()
