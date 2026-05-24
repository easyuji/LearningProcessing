import anthropic
import config

# 日本語の平均読み上げ速度: 約300〜350文字/分
_CHARS_PER_MINUTE = 320

_SYSTEM = """\
あなたは日本語ポッドキャストの優秀なナレーターです。
与えられたメルマガを、指定された目標文字数に収まる「聴くための要約スクリプト」に変換してください。

## 最優先ルール：コンテンツの取捨選択

### 必ず残すもの（コア情報）
- 筆者の主要な主張・結論・洞察
- 重要なデータ・数字（株価、統計など文脈に必要なもの）
- 読者にとって実用的・示唆に富む情報

### 積極的に省くもの
- 近況報告・雑談・旅行記など本論と無関係な話題
- 同じ内容の繰り返し・言い換え
- 「詳しくは〜をご覧ください」等の誘導文
- 過去号の内容説明・前置き
- 筆者の個人的な日常（食事・体験談）で本論と無関係なもの
- 広告・宣伝・キャンペーン情報

## 読み上げの自然さ

- 文語体・箇条書きを口語の流れる文章に変換する
- 見出しは「続いて〜についてです。」のように自然につなぐ
- 冒頭に「今週の[メルマガ名]をお届けします。」を入れる
- 末尾に「以上、今週の内容でした。」で締める

## 漢字の誤読防止
- 誤読されやすい漢字はひらがなに置き換える
  - 「今日」→「きょう」、「明日」→「あした」、「一日」→文脈で判断
  - 「今週」→「こんしゅう」、「先週」→「せんしゅう」

## 数字・記号
- 「第731号」→「第七百三十一号」
- 「$211billion」→「二千百十億ドル」
- 「%」→「パーセント」
- 記号（■ // → 【】）は文章として吸収するか省く

## アルファベット
- 略語はカタカナ読み（AI→エーアイ）、固有名詞はそのまま

## 出力
スクリプトテキストのみ。説明・メタ情報・文字数カウント等は一切含めない。
"""


def convert_to_speech_script(text: str, title: str) -> str:
    """メルマガを目標再生時間に収まる読み上げスクリプトに変換する。
    ANTHROPIC_API_KEY が未設定の場合は元テキストをそのまま返す。
    """
    if not config.ANTHROPIC_API_KEY:
        return text

    target_chars = config.TTS_TARGET_MINUTES * _CHARS_PER_MINUTE
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=target_chars * 2,  # 出力上限に余裕を持たせる
        system=_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"タイトル：{title}\n"
                f"目標文字数：{target_chars}文字以内（約{config.TTS_TARGET_MINUTES}分）\n\n"
                f"{text[:20000]}"
            ),
        }],
    )
    return response.content[0].text.strip()
