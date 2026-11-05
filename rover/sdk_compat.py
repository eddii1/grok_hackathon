"""Use native Apple Silicon PyAV instead of DJI's old Intel-only libmedia_codec binary.

Load before importing robomaster. Control/telemetry remain the official SDK; audio is unsupported.
"""

import platform
import logging
import sys
import threading
import types


def install():
    if not hasattr(threading.Thread, "isAlive"):
        threading.Thread.isAlive = threading.Thread.is_alive
    if platform.machine() not in ("arm64", "aarch64"):
        try:
            import libmedia_codec  # noqa: F401
            return
        except ImportError:
            pass
    try:
        import av
    except ImportError as exc:
        raise RuntimeError("Missing native video decoder. Run: bash rover/setup_mac.sh") from exc

    class H264Decoder:
        def __init__(self):
            self.codec = av.CodecContext.create("h264", "r")
            self.bytes_in = 0
            self.frames_decoded = 0
            self.last_error = ""
            self.errors = 0

        def failed(self, exc):
            self.last_error = str(exc)
            self.errors += 1
            if self.errors == 1 or self.errors % 50 == 0:
                logging.getLogger("RoverDecoder").warning("H264 decoder: %s", exc)

        def decode(self, data):
            frames = []
            self.bytes_in += len(data)
            try:
                packets = self.codec.parse(bytes(data))
            except Exception as exc:
                self.failed(exc)
                return frames
            for packet in packets:
                try:
                    decoded = self.codec.decode(packet)
                except Exception as exc:
                    self.failed(exc)
                    continue  # join a live stream mid-GOP: wait for the next decodable keyframe
                for frame in decoded:
                    rgb = frame.to_ndarray(format="rgb24")
                    frames.append((rgb.tobytes(), frame.width, frame.height, frame.width * 3))
                    self.frames_decoded += 1
                    self.last_error = ""
            return frames

    class OpusDecoder:
        def decode(self, data):
            raise NotImplementedError("Audio is not supported by the Apple Silicon compatibility layer")

    module = types.ModuleType("libmedia_codec")
    module.H264Decoder = H264Decoder
    module.OpusDecoder = OpusDecoder
    sys.modules["libmedia_codec"] = module


def patch_video():
    """Replace the SDK's obsolete binary numpy.fromstring conversion; keep decoder errors observable."""
    import numpy as np
    from robomaster import media

    def decode_frames(self, data):
        try:
            output = []
            for raw, width, height, stride in self._video_decoder.decode(data):
                if not raw:
                    continue
                image = np.frombuffer(raw, dtype=np.uint8).reshape(height, stride)
                output.append(image[:, :width * 3].reshape(height, width, 3).copy())
            self._decode_error = ""
            return output
        except Exception as exc:
            self._decode_error = str(exc)
            logging.getLogger("RoverDecoder").exception("SDK video frame conversion failed")
            return []

    media.LiveView._h264_decode = decode_frames
    _patch_stream_recv()


def _patch_stream_recv():
    """DJI's TCP receive loop never checks EOF: a closed video socket spins forever queueing b''.

    Stop on EOF, count real bytes, and record when/why the stream ended so the caller can reconnect.
    """
    import socket
    import time
    from robomaster import conn

    log = logging.getLogger("RoverStream")

    def recv_task(self):
        self._receiving = True
        self.bytes_total = 0
        self.eof = False
        self.end_reason = ""
        self.started_at = time.time()
        self.last_data_at = 0.0
        tcp = self._sock is not None and self._sock.type == socket.SOCK_STREAM
        while self._receiving:
            try:
                if self._sock is None:
                    break
                data = self._sock.recv(65536) if tcp else self._sock.recvfrom(65536)[0]
                if not self._receiving:
                    break
                if not data:
                    self.eof = True
                    self.end_reason = "rover closed video socket after %d bytes, %.1fs" % (
                        self.bytes_total, time.time() - self.started_at)
                    log.warning(self.end_reason)
                    break
                self._recv_count += 1
                self.bytes_total += len(data)
                self.last_data_at = time.time()
                if self._sock_queue.full():
                    self._sock_queue.get_nowait()
                self._sock_queue.put(data)
            except socket.timeout:
                # The rover can stop sending without closing the socket: treat 5 s of silence as a dead stream.
                if time.time() - (self.last_data_at or self.started_at) > 5:
                    self.eof = True
                    self.end_reason = "video stalled: no data for 5 s after %d bytes" % self.bytes_total
                    log.warning(self.end_reason)
                    break
                continue
            except Exception as exc:
                if self._receiving:
                    self.eof = True
                    self.end_reason = "video socket error: %s" % exc
                    log.warning(self.end_reason)
                break
        self._receiving = False
        try:
            self._sock_queue.put_nowait(None)  # wake the decoder's read_buf
        except Exception:
            pass

    conn.StreamConnection._recv_task = recv_task
