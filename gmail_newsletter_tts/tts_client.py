import asyncio
import re
import tempfile
from pathlib import Path

from mutagen.mp3 import MP3

import config

_OPENAI_MAX_CHARS = 4000  # OpenAI TTS の上限4096に対する安全マージン

# [EN]...[/EN] で囲まれた英語セクションを分割するパターン
_LANG_SPLIT_RE = re.compile(r"(\[EN\].*?\[/EN\])", re.DOTALL)


# ── 言語セグメント分割 ───────────────────────────────────────────
def _split_lang_segments(text: str) -> list[tuple[str, str]]:
    """
    [EN]...[/EN] タグで囲まれた箇所を英語セグメントとして分割する。
    Returns: [(lang, text), ...]  lang は "ja" or "en"
    """
    parts = _LANG_SPLIT_RE.split(text)
    segments = []
    for part in parts:
        if not part.strip():
            continue
        if part.startswith("[EN]") and part.endswith("[/EN]"):
            inner = part[4:-5].strip()
            if inner:
                segments.append(("en", inner))
        else:
            cleaned = re.sub(r"\[/?EN\]", "", part).strip()
            if cleaned:
                segments.append(("ja", cleaned))
    return segments or [("ja", text)]


# ── MP3 結合（ffmpeg 不要） ─────────────────────────────────────
def _strip_id3v2(data: bytes) -> bytes:
    """ID3v2 ヘッダーを除去して生 MPEG フレームを返す。"""
    if data[:3] != b"ID3":
        return data
    # syncsafe integer でサイズを計算
    size = (
        (data[6] & 0x7F) << 21
        | (data[7] & 0x7F) << 14
        | (data[8] & 0x7F) << 7
        | (data[9] & 0x7F)
    )
    return data[10 + size:]


def _concat_mp3s(files: list[str], output: str) -> float:
    """複数の MP3 ファイルを結合して output に書き出す。再生時間(秒)を返す。"""
    with open(output, "wb") as out:
        for i, f in enumerate(files):
            data = Path(f).read_bytes()
            if i > 0:
                data = _strip_id3v2(data)
            out.write(data)
    return MP3(output).info.length


# ── テキスト分割（長文対応） ────────────────────────────────────
def _chunk_text(text: str, max_chars: int) -> list[str]:
    sentences = re.split(r"(?<=[。！？\n.!?])", text)
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
    return chunks or [text[:max_chars]]


# ── OpenAI TTS ──────────────────────────────────────────────────
def _openai_tts(text: str, output_path: str, lang: str = "ja") -> float:
    from openai import OpenAI
    # OpenAI TTS は多言語対応なので lang に関わらずそのまま渡す
    # [EN][/EN] タグを除去
    clean_text = re.sub(r"\[/?EN\]", "", text)
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    chunks = _chunk_text(clean_text, _OPENAI_MAX_CHARS)

    audio_bytes = b""
    for chunk in chunks:
        response = client.audio.speech.create(
            model="tts-1-hd",
            voice=config.TTS_VOICE_OPENAI,
            input=chunk,
            response_format="mp3",
        )
        audio_bytes += response.read()

    with open(output_path, "wb") as f:
        f.write(audio_bytes)
    return MP3(output_path).info.length


# ── Edge TTS ────────────────────────────────────────────────────
async def _edge_tts_segment_async(text: str, voice: str, output_path: str):
    import edge_tts
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(output_path)


async def _edge_tts_async(text: str, output_path: str):
    """
    [EN]...[/EN] タグを解析し、英語は en-US-AriaNeural、
    日本語は ja-JP-NanamiNeural で読み上げて結合する。
    """
    segments = _split_lang_segments(text)

    if len(segments) == 1 and segments[0][0] == "ja":
        # 英語セグメントなし → 従来通り
        import edge_tts
        communicate = edge_tts.Communicate(text=segments[0][1], voice=config.TTS_VOICE_EDGE)
        await communicate.save(output_path)
        return

    # 複数セグメント → 個別生成して結合
    tmp_files = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, (lang, seg_text) in enumerate(segments):
            voice = config.TTS_VOICE_EN if lang == "en" else config.TTS_VOICE_EDGE
            seg_path = str(Path(tmpdir) / f"seg_{i:03d}.mp3")
            await _edge_tts_segment_async(seg_text, voice, seg_path)
            tmp_files.append(seg_path)

        _concat_mp3s(tmp_files, output_path)


def _edge_tts(text: str, output_path: str) -> float:
    asyncio.run(_edge_tts_async(text, output_path))
    return MP3(output_path).info.length


# ── 公開インターフェース ─────────────────────────────────────────
def text_to_mp3(text: str, output_path: str) -> float:
    if config.OPENAI_API_KEY:
        return _openai_tts(text, output_path)
    return _edge_tts(text, output_path)
