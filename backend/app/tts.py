import os
import re
from functools import lru_cache
from typing import AsyncGenerator, AsyncIterable, Optional

from fish_audio_sdk import AsyncWebSocketSession, TTSRequest

from .logger import logger


class TTSClient:
    """Wrapper around Fish Audio SDK for TTS streaming."""

    def __init__(self, api_key: str, reference_id: Optional[str] = None):
        logger.info("[TTS] Initializing TTSClient")
        self._api_key = api_key
        self._reference_id = reference_id

    async def stream_audio(
        self, text_stream: AsyncIterable[str]
    ) -> AsyncGenerator[bytes, None]:
        """Convert text stream to audio bytes."""
        request = TTSRequest(
            text="",
            format="mp3",
            mp3_bitrate=128,
            reference_id=self._reference_id,
            latency="balanced",
        )

        async with AsyncWebSocketSession(self._api_key) as session:
            async for audio_chunk in session.tts(request, text_stream):
                yield audio_chunk


class TextBuffer:
    """Buffers text and yields complete sentences."""

    SENTENCE_END = re.compile(r"[.!?\n](?:\s|$)")

    def __init__(self):
        self._buffer = ""

    def add(self, text: str) -> list[str]:
        """Add text, return complete sentences."""
        self._buffer += text
        sentences = []

        while True:
            match = self.SENTENCE_END.search(self._buffer)
            if not match:
                break
            end_pos = match.end()
            sentence = self._buffer[:end_pos].strip()
            self._buffer = self._buffer[end_pos:]
            if sentence:
                sentences.append(sentence)

        return sentences

    def flush(self) -> Optional[str]:
        """Return remaining buffered text."""
        remaining = self._buffer.strip()
        self._buffer = ""
        return remaining if remaining else None


@lru_cache()
def get_tts_client() -> Optional[TTSClient]:
    """Get singleton TTSClient."""
    api_key = os.getenv("FISH_API_KEY")
    if not api_key:
        logger.warning("[TTS] FISH_API_KEY not set, TTS disabled")
        return None

    return TTSClient(
        api_key=api_key,
        reference_id=os.getenv("FISH_AUDIO_REFERENCE_ID"),
    )
