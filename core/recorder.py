import io
import wave
import threading
import numpy as np
import sounddevice as sd
from core.logger import get_logger


class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self._sample_rate = sample_rate
        self._channels = channels
        self._recording = False
        self._frames: list = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._log = get_logger()

    def _callback(self, indata, frames, time_info, status):
        if status:
            self._log.warning(f"Recorder: 音频回调状态异常: {status}")
            return
        with self._lock:
            if self._recording:
                self._frames.append(indata.copy())

    def start(self):
        with self._lock:
            if self._recording:
                self._log.debug("Recorder: 已在录音中，忽略重复启动")
                return
            self._recording = True
            self._frames.clear()

        try:
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="int16",
                callback=self._callback,
            )
            self._stream.start()
            self._log.debug(f"Recorder: 录音开始, rate={self._sample_rate}Hz, channels={self._channels}")
        except Exception as e:
            self._log.error(f"Recorder: 启动录音失败: {e}")
            self._recording = False
            raise

    def stop(self) -> io.BytesIO:
        with self._lock:
            was_recording = self._recording
            self._recording = False

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            if not self._frames:
                self._log.debug("Recorder: 无音频帧数据")
                return io.BytesIO()
            audio_data = np.concatenate(self._frames, axis=0)

        duration = len(audio_data) / self._sample_rate
        self._log.debug(
            f"Recorder: 录音结束, "
            f"samples={len(audio_data)}, "
            f"duration={duration:.2f}s"
        )

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(self._channels)
            wf.setsampwidth(2)
            wf.setframerate(self._sample_rate)
            wf.writeframes(audio_data.tobytes())
        buffer.seek(0)
        return buffer

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording
