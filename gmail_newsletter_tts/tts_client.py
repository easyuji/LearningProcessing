import asyncio
import re

from mutagen.mp3 import MP3

import config

_OPENAI_MAX_CHARS = 4000  # OpenAI TTS の上限4096に対する安全マージン


def _chunk_text(text: str, max_chars: int) -> list[str]:
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
    return chunks or [text[:max_chars]]


def _openai_tts(text: str, output_path: str) -> float:
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    chunks = _chunk_text(text, _OPENAI_MAX_CHARS)

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


async def _edge_tts_async(text: str, output_path: str):
    import edge_tts
    communicate = edge_tts.Communicate(text=text, voice=config.TTS_VOICE_EDGE)
    await communicate.save(output_path)


def _edge_tts(text: str, output_path: str) -> float:
    asyncio.run(_edge_tts_async(text, output_path))
    return MP3(output_path).info.length


def text_to_mp3(text: str, output_path: str) -> float:
    if config.OPENAI_API_KEY:
        return _openai_tts(text, output_path)
    return _edge_tts(text, output_path)
