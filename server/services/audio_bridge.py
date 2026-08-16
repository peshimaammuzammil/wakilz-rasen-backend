"""
RasenAudioBridge — bidirectional PCM16 audio bridge between a WebRTC
peer connection (aiortc) and Rasen's media WebSocket.

Audio flow:
  Browser mic  →  aiortc track (Opus) →  decode  →  PCM16 bytes  →  Rasen WS
  Rasen WS     →  PCM16 bytes  →  encode  →  aiortc track (Opus)  →  Browser speaker

Rasen media spec (binary transport):
  - Each binary frame: raw PCM16 audio, no header/envelope
  - Little-endian signed 16-bit mono
  - 8000 Hz, 20 ms packets → 320 bytes per frame
  - Text frames carry JSON events: { "event": "clear" } for barge-in
"""

from __future__ import annotations

import asyncio
import fractions
import time
from typing import AsyncIterator

import av
import websockets
import websockets.exceptions
from aiortc import MediaStreamTrack
from aiortc.contrib.media import MediaBlackhole
from loguru import logger

# ── Constants ─────────────────────────────────────────────────────────────────
SAMPLE_RATE = 8000
CHANNELS = 1
FRAME_DURATION_MS = 20
SAMPLES_PER_FRAME = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # 160 samples
BYTES_PER_FRAME = SAMPLES_PER_FRAME * 2  # PCM16 = 2 bytes/sample → 320 bytes
AUDIO_CLOCK_RATE = SAMPLE_RATE
AUDIO_TIME_BASE = fractions.Fraction(1, AUDIO_CLOCK_RATE)


class RasenOutputTrack(MediaStreamTrack):
    """
    An aiortc AudioStreamTrack that reads PCM16 audio from the Rasen WebSocket
    and delivers it to the browser as Opus frames via WebRTC.

    One instance per call. The bridge feeds this track via an asyncio.Queue.
    """

    kind = "audio"

    def __init__(self):
        super().__init__()
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=50)
        self._pts = 0
        self._started = time.time()

    def push_pcm(self, data: bytes) -> None:
        """Called by the bridge when Rasen sends audio."""
        try:
            self._queue.put_nowait(data)
        except asyncio.QueueFull:
            # Drop oldest frame to keep latency low
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(data)
            except asyncio.QueueEmpty:
                pass

    def clear_buffer(self) -> None:
        """Called on Rasen 'clear' event (barge-in). Flush queued audio."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        logger.debug("audio_bridge=clear_buffer")

    async def recv(self) -> av.AudioFrame:
        """
        aiortc calls this repeatedly to get audio frames to send to the browser.
        Returns silence while waiting for Rasen audio.
        """
        try:
            pcm_bytes = await asyncio.wait_for(self._queue.get(), timeout=0.02)
        except asyncio.TimeoutError:
            # Silence frame while waiting
            pcm_bytes = b"\x00" * BYTES_PER_FRAME

        if pcm_bytes is None:
            # Poison pill — track ending
            pcm_bytes = b"\x00" * BYTES_PER_FRAME

        frame = av.AudioFrame(format="s16", layout="mono", samples=SAMPLES_PER_FRAME)
        frame.planes[0].update(pcm_bytes[:BYTES_PER_FRAME])
        frame.sample_rate = SAMPLE_RATE
        frame.pts = self._pts
        frame.time_base = AUDIO_TIME_BASE
        self._pts += SAMPLES_PER_FRAME
        return frame


class RasenAudioBridge:
    """
    Manages the WebSocket connection to Rasen and routes audio in both directions.

    Lifecycle:
      1. Call `await bridge.connect()` — opens the WS to Rasen
      2. Call `bridge.start_forwarding(browser_track)` — starts async tasks
      3. Call `await bridge.close()` — tears down everything on hangup
    """

    def __init__(self, websocket_url: str, call_id: str):
        self.websocket_url = websocket_url
        self.call_id = call_id
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._running = False
        self._output_track: RasenOutputTrack | None = None
        self._tasks: list[asyncio.Task] = []

    @property
    def output_track(self) -> RasenOutputTrack:
        if self._output_track is None:
            self._output_track = RasenOutputTrack()
        return self._output_track

    async def connect(self) -> None:
        """Open the Rasen media WebSocket."""
        logger.info(f"audio_bridge=connecting call_id={self.call_id}")
        self._ws = await websockets.connect(
            self.websocket_url,
            ping_interval=20,
            ping_timeout=10,
            max_size=1_048_576,  # 1 MB
        )
        self._running = True
        logger.info(f"audio_bridge=connected call_id={self.call_id}")

    def start_forwarding(self, browser_track: MediaStreamTrack) -> None:
        """
        Start two async tasks:
          1. Rasen → browser (reads from Rasen WS, pushes to output_track)
          2. Browser → Rasen (reads from browser_track, sends to Rasen WS)
        """
        loop = asyncio.get_event_loop()
        self._tasks = [
            loop.create_task(self._rasen_to_browser(), name=f"rasen_to_browser_{self.call_id}"),
            loop.create_task(self._browser_to_rasen(browser_track), name=f"browser_to_rasen_{self.call_id}"),
        ]

    async def _rasen_to_browser(self) -> None:
        """Read PCM16 frames from Rasen WS, push to output track for browser."""
        try:
            while self._running and self._ws:
                try:
                    msg = await asyncio.wait_for(self._ws.recv(), timeout=30.0)
                except asyncio.TimeoutError:
                    logger.warning(f"audio_bridge=rasen_recv_timeout call_id={self.call_id}")
                    continue

                if isinstance(msg, bytes):
                    # Raw PCM16 binary frame → push to browser output track
                    if self._output_track:
                        self._output_track.push_pcm(msg)
                elif isinstance(msg, str):
                    # JSON control event
                    import json
                    try:
                        event = json.loads(msg)
                        evt_type = event.get("event", "")
                        if evt_type == "clear":
                            # Barge-in: caller interrupted, flush queued audio
                            if self._output_track:
                                self._output_track.clear_buffer()
                        else:
                            logger.debug(f"audio_bridge=rasen_event event={evt_type} call_id={self.call_id}")
                    except Exception:
                        pass

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"audio_bridge=rasen_ws_closed call_id={self.call_id}")
        except Exception as e:
            logger.error(f"audio_bridge=rasen_to_browser_error error={e!r} call_id={self.call_id}")
        finally:
            self._running = False

    async def _browser_to_rasen(self, browser_track: MediaStreamTrack) -> None:
        """
        Read audio frames from the browser's WebRTC track (Opus decoded by aiortc),
        resample to 8kHz mono PCM16, and forward to Rasen WS as binary frames.
        """
        resampler = av.AudioResampler(
            format="s16",
            layout="mono",
            rate=SAMPLE_RATE,
        )
        try:
            while self._running:
                frame = await asyncio.wait_for(browser_track.recv(), timeout=5.0)

                # Resample to 8kHz mono PCM16
                resampled_frames = resampler.resample(frame)
                for rf in resampled_frames:
                    pcm_bytes = bytes(rf.planes[0])

                    # Send in 20ms chunks (320 bytes each)
                    for offset in range(0, len(pcm_bytes), BYTES_PER_FRAME):
                        chunk = pcm_bytes[offset : offset + BYTES_PER_FRAME]
                        if len(chunk) < BYTES_PER_FRAME:
                            # Pad last incomplete frame with silence
                            chunk = chunk + b"\x00" * (BYTES_PER_FRAME - len(chunk))
                        if self._ws and self._running:
                            await self._ws.send(chunk)

        except asyncio.TimeoutError:
            logger.warning(f"audio_bridge=browser_track_timeout call_id={self.call_id}")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"audio_bridge=rasen_closed_mid_call call_id={self.call_id}")
        except Exception as e:
            logger.error(f"audio_bridge=browser_to_rasen_error error={e!r} call_id={self.call_id}")
        finally:
            self._running = False

    async def close(self) -> None:
        """Tear down — stop tasks, close Rasen WS."""
        self._running = False

        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        # Poison pill to unblock output track's recv()
        if self._output_track:
            self._output_track.push_pcm(b"\x00" * BYTES_PER_FRAME)

        logger.info(f"audio_bridge=closed call_id={self.call_id}")
