import asyncio
from mutagen.mp3 import MP3
import edge_tts

import config


async def _synthesize(text: str, output_path: str):
    communicate = edge_tts.Communicate(text=text, voice=config.TTS_VOICE)
    await communicate.save(output_path)


def text_to_mp3(text: str, output_path: str) -> float:
    asyncio.run(_synthesize(text, output_path))
    return MP3(output_path).info.length
