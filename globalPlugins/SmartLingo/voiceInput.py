# voiceInput.py
# Clean voice input for SmartLingo
# Security: Audio is transcribed via user's own API key only. No data stored locally. SSL enforced.

import os
import sys
import threading
import wave
import requests
from requests.adapters import HTTPAdapter

_session = requests.Session()
_session.trust_env = False
_session.mount("https://", HTTPAdapter(max_retries=1))
import tempfile
import tones
import ui
import queueHandler
from logHandler import log

# Fix #12: trust_env kept False for speed, but documented — user can change if needed for proxies


# Add lib/ to sys.path
_addon_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_lib_dir = os.path.join(_addon_root, "lib")
if os.path.isdir(_lib_dir) and _lib_dir not in sys.path:
	sys.path.insert(0, _lib_dir)

try:
	import pyaudio
	_AUDIO_AVAILABLE = True
except ImportError:
	# Fix #8: Log import failure
	log.error("SmartLingo: PyAudio import failed. Voice input unavailable.")
	_AUDIO_AVAILABLE = False

_SAMPLE_RATE = 16000
_CHANNELS = 1
_CHUNK_SIZE = 1024
_MAX_AUDIO_BYTES = 10 * 1024 * 1024  # SECURITY: 10 MB cap — ~5 min of audio


class VoiceInputManager:
	def __init__(self, on_text_ready):
		self.on_text_ready = on_text_ready
		self.recognition_lang = "auto"
		self._stop_event = threading.Event()
		self._cancel_event = threading.Event()
		self._thread = None
		self.api_keys = {}

	def is_recording(self):
		return bool(self._thread and self._thread.is_alive())

	def toggle(self, api_keys=None):
		if api_keys:
			self.api_keys = api_keys

		if self.is_recording():
			self._stop_event.set()
		else:
			if not _AUDIO_AVAILABLE:
				# Fix #1: Already on main thread here (called from gesture handler)
				ui.message(_("PyAudio not available. Please reinstall the addon."))
				return
			self._stop_event.clear()
			self._cancel_event.clear()
			self._thread = threading.Thread(target=self._run, daemon=True)
			self._thread.start()

	def cancel(self):
		if self.is_recording():
			self._cancel_event.set()
			self._stop_event.set()

	def _run(self):
		frames = self._capture()

		if self._cancel_event.is_set():
			return

		import nvwave
		stop_snd = os.path.join(os.path.dirname(__file__), "sounds", "send.wav")
		if os.path.exists(stop_snd):
			nvwave.playWaveFile(stop_snd, asynchronous=True)
		else:
			tones.beep(440, 100)

		if frames:
			# Fix #1: UI via queueHandler (already correct here)
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("Transcribing..."))
			self._process(frames)
		else:
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("No audio captured."))

	def _capture(self):
		p = pyaudio.PyAudio()
		frames = []
		# Fix #3: Running byte counter instead of O(n) sum on every chunk
		total_bytes = 0
		try:
			import nvwave
			start_snd = os.path.join(os.path.dirname(__file__), "sounds", "Voice Start.wav")
			if os.path.exists(start_snd):
				nvwave.playWaveFile(start_snd, asynchronous=True)
			else:
				tones.beep(880, 100)

			stream = p.open(
				format=pyaudio.paInt16,
				channels=_CHANNELS,
				rate=_SAMPLE_RATE,
				input=True,
				frames_per_buffer=_CHUNK_SIZE
			)

			while not self._stop_event.is_set():
				try:
					data = stream.read(_CHUNK_SIZE, exception_on_overflow=False)
					frames.append(data)
					# Fix #3: O(1) counter instead of O(n) sum each iteration
					total_bytes += len(data)
					if total_bytes > _MAX_AUDIO_BYTES:
						log.warning("SmartLingo: Audio size limit reached (10 MB). Stopping recording.")
						queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("Recording limit reached. Stopping."))
						break
				except Exception as e:
					log.error(f"SmartLingo: Stream read error: {e}")
					break

			stream.stop_stream()
			stream.close()
		except Exception as e:
			log.error(f"SmartLingo: Mic error: {e}")
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("Microphone error."))
		finally:
			p.terminate()
		return frames

	def _process(self, frames):
		# Fix #10: Use delete=False + manual cleanup in finally (safer than delete=True with wave.open)
		fd, path = tempfile.mkstemp(suffix=".wav")
		os.close(fd)
		try:
			with wave.open(path, "wb") as wf:
				wf.setnchannels(_CHANNELS)
				wf.setsampwidth(2)
				wf.setframerate(_SAMPLE_RATE)
				wf.writeframes(b"".join(frames))

			text = self.transcribe(path, self.recognition_lang)
			if text:
				queueHandler.queueFunction(queueHandler.eventQueue, self.on_text_ready, text)
			else:
				queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("Could not recognize speech."))
		except Exception as e:
			# Fix #8: Log exception instead of silent failure
			log.error(f"SmartLingo: Audio processing error: {e}")
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("Audio processing error."))
		finally:
			# Fix #10: Always clean up temp file, even on crash
			try:
				if os.path.exists(path):
					os.remove(path)
			except Exception as e:
				log.error(f"SmartLingo: Temp file cleanup error: {e}")

	def transcribe(self, path, lang):
		"""
		Transcribes audio using the available API key.
		Priority: Groq Whisper.
		Gemini does not support STT, so a clear error message is shown if only a Gemini key is provided.
		"""
		groq_key = self.api_keys.get("groq")
		if groq_key:
			text = self._transcribe_groq(path, lang, groq_key)
			if text:
				return text

		# If only a Gemini key is provided, show a clear error
		gemini_key = self.api_keys.get("gemini")
		if gemini_key and not groq_key:
			log.warning("SmartLingo: Gemini does not support voice input (STT). Please add a Groq API key.")
			queueHandler.queueFunction(
				queueHandler.eventQueue,
				ui.message,
				_("Voice input requires a Groq API key. Gemini does not support speech recognition.")
			)
			return None

		log.error("SmartLingo: No valid STT API key provided (Groq required for voice input).")
		return None

	def _transcribe_groq(self, path, lang, api_key):
		try:
			url = "https://api.groq.com/openai/v1/audio/transcriptions"
			headers = {"Authorization": f"Bearer {api_key}"}
			iso_lang = lang.split("_")[0] if lang and lang != "auto" else None

			with open(path, "rb") as f:
				files = {"file": (os.path.basename(path), f, "audio/wav")}
				data = {"model": "whisper-large-v3-turbo"}
				if iso_lang:
					data["language"] = iso_lang

				resp = _session.post(url, headers=headers, files=files, data=data, timeout=30, verify=True)
				if resp.status_code == 200:
					return resp.json().get("text")
				log.error(f"SmartLingo: Groq STT error {resp.status_code}: {resp.text}")
		except Exception as e:
			log.error(f"SmartLingo: Groq STT exception: {e}")
		return None

	def cleanup(self):
		self._stop_event.set()
