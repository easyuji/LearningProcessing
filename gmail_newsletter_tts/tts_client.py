import os
import re
import subprocess
import tempfile

from google.cloud import texttospeech

import config

_MAX_BYTES = 4500


def _chunk_text(text: str) -> list[str]:
    sentences = re.split(r"(?<=[。！？\n])\s*", text)
    chunks, current = [], ""
    for sentence in sentences:
        candidate = current + sentence
        if len(candidate.encode("utf-8")) > _MAX_BYTES:
            if current:
                chunks.append(current.strip())
            current = sentence
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text[:1000]]


def _synthesize(client, text: str, voice, audio_config) -> bytes:
    response = client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=text),
        voice=voice,
        audio_config=audio_config,
    )
    return response.audio_content


def _concat_mp3s(files: list[str], output: str):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for path in files:
            f.write(f"file '{path}'\n")
        list_file = f.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", output],
            check=True,
            capture_output=True,
        )
    finally:
        os.unlink(list_file)


def _get_duration(mp3_path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            mp3_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def text_to_mp3(text: str, output_path: str) -> float:
    client = texttospeech.TextToSpeechClient()
    voice = texttospeech.VoiceSelectionParams(
        language_code=config.TTS_LANGUAGE,
        name=config.TTS_VOICE,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    chunks = _chunk_text(text)

    if len(chunks) == 1:
        audio = _synthesize(client, chunks[0], voice, audio_config)
        with open(output_path, "wb") as f:
            f.write(audio)
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            chunk_files = []
            for i, chunk in enumerate(chunks):
                audio = _synthesize(client, chunk, voice, audio_config)
                path = os.path.join(tmpdir, f"chunk_{i:03d}.mp3")
                with open(path, "wb") as f:
                    f.write(audio)
                chunk_files.append(path)
            _concat_mp3s(chunk_files, output_path)

    return _get_duration(output_path)
