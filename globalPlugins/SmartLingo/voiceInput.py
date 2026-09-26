# voiceInput.py
# Voice input (translation + dictation) for SmartLingo.
# Security: audio is written to a temporary file, sent only to the provider the
# user configured with their own API key, and the file is deleted immediately.
# Nothing is stored permanently.

import os
import sys
import threading
import wave
from array import array

import requests
from requests.adapters import HTTPAdapter

import addonHandler
import queueHandler
import tones
import ui
from logHandler import log

addonHandler.initTranslation()

_session = requests.Session()
_session.trust_env = False
_session.mount("https://", HTTPAdapter(max_retries=1))

# Bundled PyAudio lives in the addon's own lib/ folder.
_addon_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_lib_dir = os.path.join(_addon_root, "lib")
if os.path.isdir(_lib_dir) and _lib_dir not in sys.path:
	sys.path.insert(0, _lib_dir)

try:
	import pyaudio

	_AUDIO_AVAILABLE = True
except Exception as e:
	# A missing or broken portaudio DLL raises OSError, not ImportError, and that
	# must not be allowed to take the whole addon down at import time.
	log.error(f"SmartLingo: PyAudio import failed ({e}). Voice input unavailable.")
	pyaudio = None
	_AUDIO_AVAILABLE = False

_SAMPLE_RATE = 16000
_CHANNELS = 1
_SAMPLE_WIDTH = 2
_CHUNK_SIZE = 1024
_BYTES_PER_SECOND = _SAMPLE_RATE * _CHANNELS * _SAMPLE_WIDTH

_MAX_RECORDING_SECONDS = 300
_MAX_AUDIO_BYTES = _BYTES_PER_SECOND * _MAX_RECORDING_SECONDS
_MIN_RECORDING_SECONDS = 0.4

_FRAME_MS = 30
_PAD_MS = 200
_MAX_ABS_SAMPLE = 32767
_TARGET_PEAK = 14000
_MAX_GAIN = 8.0
# Relative and absolute floors used to decide what counts as silence.
_SILENCE_RATIO = 0.06
_SILENCE_FLOOR = 350

# Languages Whisper can actually transcribe. Anything outside this set is sent
# without a language hint rather than risking an HTTP 400 from the API.
WHISPER_LANGUAGES = {
	"af": "Afrikaans", "am": "Amharic", "ar": "Arabic", "as": "Assamese",
	"az": "Azerbaijani", "ba": "Bashkir", "be": "Belarusian", "bg": "Bulgarian",
	"bn": "Bengali", "bo": "Tibetan", "br": "Breton", "bs": "Bosnian",
	"ca": "Catalan", "cs": "Czech", "cy": "Welsh", "da": "Danish",
	"de": "German", "el": "Greek", "en": "English", "es": "Spanish",
	"et": "Estonian", "eu": "Basque", "fa": "Persian", "fi": "Finnish",
	"fo": "Faroese", "fr": "French", "gl": "Galician", "gu": "Gujarati",
	"ha": "Hausa", "haw": "Hawaiian", "he": "Hebrew", "hi": "Hindi",
	"hr": "Croatian", "ht": "Haitian Creole", "hu": "Hungarian", "hy": "Armenian",
	"id": "Indonesian", "is": "Icelandic", "it": "Italian", "ja": "Japanese",
	"jw": "Javanese", "jv": "Javanese", "ka": "Georgian", "kk": "Kazakh",
	"km": "Khmer", "kn": "Kannada", "ko": "Korean", "la": "Latin",
	"lb": "Luxembourgish", "ln": "Lingala", "lo": "Lao", "lt": "Lithuanian",
	"lv": "Latvian", "mg": "Malagasy", "mi": "Maori", "mk": "Macedonian",
	"ml": "Malayalam", "mn": "Mongolian", "mr": "Marathi", "ms": "Malay",
	"mt": "Maltese", "my": "Burmese", "ne": "Nepali", "nl": "Dutch",
	"no": "Norwegian", "nn": "Nynorsk", "oc": "Occitan", "pa": "Punjabi",
	"pl": "Polish", "ps": "Pashto", "pt": "Portuguese", "ro": "Romanian",
	"ru": "Russian", "sa": "Sanskrit", "sd": "Sindhi", "si": "Sinhala",
	"sk": "Slovak", "sl": "Slovenian", "sn": "Shona", "so": "Somali",
	"su": "Sundanese", "sv": "Swedish", "sw": "Swahili", "ta": "Tamil",
	"te": "Telugu", "tg": "Tajik", "th": "Thai", "tk": "Turkmen",
	"tl": "Tagalog", "tr": "Turkish", "tt": "Tatar", "uk": "Ukrainian",
	"ur": "Urdu", "uz": "Uzbek", "vi": "Vietnamese", "yi": "Yiddish",
	"yo": "Yoruba", "yue": "Cantonese", "zh": "Chinese",
}

STT_MODEL = "whisper-large-v3"


class TranscriptionError(Exception):
	"""Carries a message that is safe to show to the user."""


def normalize_speech_lang(code):
	"""
	Turns an addon language code into a value usable as a Whisper `language`
	hint. Returns (iso_code_or_None, wants_roman_output).

	Roman variants collapse to their base language, because Whisper always
	returns the script of the language it was given, never a transliteration.
	"""
	if not code or code == "auto":
		return None, False
	wants_roman = "_roman" in code
	base = code.split("_")[0]
	base = base.split("-")[0]
	base = base.lower()
	return (base if base in WHISPER_LANGUAGES else None), wants_roman


def speech_lang_choices():
	"""Sorted (label, code) pairs for the speech language setting."""
	choices = [(_("Automatic detection"), "auto")]
	choices.extend(sorted((name, code) for code, name in WHISPER_LANGUAGES.items()))
	return choices


def _build_prompt(iso_lang, wants_roman):
	"""
	Whisper is much more accurate when it is told to transcribe verbatim and
	not to answer or translate. The wording is kept short on purpose: a long
	prompt makes the model substitute words it has seen in the prompt.
	"""
	parts = [
		"Transcribe the speech verbatim.",
		"Do not translate, do not answer, and do not add any commentary.",
	]
	if wants_roman:
		parts.append("Write the result in Latin (Roman) characters.")
	else:
		parts.append("Keep each word in the script it was most likely spoken in.")
	if iso_lang in ("ur", "hi", "bn", "pa", "ne", "si", "gu", "mr", "ta", "te", "ml", "kn"):
		parts.append(
			"Everyday speech mixes local words with English technical words; "
			"keep the English words in English rather than transliterating them."
		)
	return " ".join(parts)


def _to_samples(raw):
	"""Interprets 16-bit little-endian PCM as signed shorts."""
	usable = len(raw) - (len(raw) % _SAMPLE_WIDTH)
	if usable <= 0:
		return array("h")
	samples = array("h")
	samples.frombytes(raw[:usable])
	if sys.byteorder == "big":
		samples.byteswap()
	return samples


def _peak(chunk):
	return max(max(chunk), -min(chunk)) if len(chunk) else 0


class VoiceInputManager:
	def __init__(self, on_text_ready):
		self.on_text_ready = on_text_ready
		self.recognition_lang = "auto"
		self.api_keys = {}
		self._state = "idle"
		self._stop_event = threading.Event()
		self._cancel_event = threading.Event()
		self._thread = None

	def is_recording(self):
		return self._state == "capturing"

	def is_processing(self):
		return self._state == "processing"

	def is_busy(self):
		return self._state != "idle"

	def toggle(self, api_keys=None):
		"""
		Starts a recording, or stops the one in progress.
		Returns one of: started, stopping, cancelling, or a ready-to-speak
		error string when nothing could be started.
		"""
		if api_keys is not None:
			self.api_keys = api_keys

		if self._state == "capturing":
			self._stop_event.set()
			return "stopping"
		if self._state == "processing":
			self._cancel_event.set()
			return "cancelling"
		if not _AUDIO_AVAILABLE:
			return _("PyAudio is not available. Please reinstall the addon.")

		self._state = "capturing"
		self._stop_event.clear()
		self._cancel_event.clear()
		self._thread = threading.Thread(target=self._run, daemon=True)
		self._thread.start()
		return "started"

	def cancel(self):
		self._cancel_event.set()
		self._stop_event.set()

	def _run(self):
		try:
			frames = self._capture()

			if self._cancel_event.is_set():
				self._state = "idle"
				return

			import nvwave
			stop_snd = os.path.join(os.path.dirname(__file__), "sounds", "send.wav")
			if os.path.exists(stop_snd):
				nvwave.playWaveFile(stop_snd, asynchronous=True)
			else:
				tones.beep(440, 100)

			if not frames:
				self._state = "idle"
				return

			joined = b"".join(frames)
			if len(joined) < int(_MIN_RECORDING_SECONDS * _BYTES_PER_SECOND):
				self._state = "idle"
				queueHandler.queueFunction(
					queueHandler.eventQueue, ui.message, _("Recording was too short.")
				)
				return

			self._state = "processing"
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("Transcribing..."))
			self._process(joined)
		except Exception as e:
			log.error(f"SmartLingo: Voice input error: {e}")
			queueHandler.queueFunction(
				queueHandler.eventQueue, ui.message, _("Voice input error: {}").format(e)
			)
		finally:
			self._state = "idle"

	def _capture(self):
		if not _AUDIO_AVAILABLE:
			return []
		p = None
		stream = None
		frames = []
		try:
			p = pyaudio.PyAudio()
		except Exception as e:
			log.error(f"SmartLingo: Could not open audio device: {e}")
			queueHandler.queueFunction(
				queueHandler.eventQueue, ui.message, _("Could not open the microphone.")
			)
			return []

		total_bytes = 0
		truncated = False
		try:
			# Played synchronously on purpose: the mic is opened afterwards so the
			# tone is never captured at the start of the recording.
			import nvwave
			start_snd = os.path.join(os.path.dirname(__file__), "sounds", "Voice Start.wav")
			if os.path.exists(start_snd):
				nvwave.playWaveFile(start_snd)
			else:
				tones.beep(880, 100)

			stream = p.open(
				format=pyaudio.paInt16,
				channels=_CHANNELS,
				rate=_SAMPLE_RATE,
				input=True,
				frames_per_buffer=_CHUNK_SIZE,
			)

			while not self._stop_event.is_set():
				try:
					data = stream.read(_CHUNK_SIZE, exception_on_overflow=True)
				except OSError as e:
					# The buffer overflowed and this chunk is already lost. Padding
					# with silence keeps the timeline intact; dropping the chunk
					# instead would splice two halves of a word together.
					log.warning(f"SmartLingo: Audio buffer overflow, padding with silence: {e}")
					frames.append(b"\x00" * (_CHUNK_SIZE * _SAMPLE_WIDTH))
					continue
				except Exception as e:
					log.error(f"SmartLingo: Stream read error: {e}")
					break

				frames.append(data)
				total_bytes += len(data)
				if total_bytes > _MAX_AUDIO_BYTES:
					truncated = True
					break
		except Exception as e:
			log.error(f"SmartLingo: Microphone error: {e}")
			queueHandler.queueFunction(
				queueHandler.eventQueue, ui.message, _("Microphone error.")
			)
			frames = []
		finally:
			if stream is not None:
				try:
					stream.stop_stream()
					stream.close()
				except Exception as e:
					log.warning(f"SmartLingo: Error closing audio stream: {e}")
			try:
				p.terminate()
			except Exception as e:
				log.warning(f"SmartLingo: Error terminating PyAudio: {e}")

		if truncated:
			queueHandler.queueFunction(
				queueHandler.eventQueue,
				ui.message,
				_("Recording limit of {n} minutes reached. Stopping.").format(
					n=_MAX_RECORDING_SECONDS // 60
				),
			)
		return frames

	def _preprocess(self, raw):
		"""
		Trims leading/trailing silence and normalises quiet recordings.
		Uses only the standard library, because the audioop module was removed
		in Python 3.13. Returns (pcm_bytes, peak) and returns b"" when the whole
		recording is silence.
		"""
		try:
			samples = _to_samples(raw)
			if not len(samples):
				return b"", 0

			frame_len = int(_SAMPLE_RATE * (_FRAME_MS / 1000.0)) or 1
			peaks = [
				_peak(samples[i:i + frame_len])
				for i in range(0, len(samples), frame_len)
			]
			global_peak = max(peaks)

			threshold = max(int(global_peak * _SILENCE_RATIO), _SILENCE_FLOOR)
			first = 0
			while first < len(peaks) and peaks[first] < threshold:
				first += 1
			if first >= len(peaks):
				# Pure silence. Whisper invents text for silence, so refuse it here
				# instead of sending it and translating a hallucination.
				return b"", global_peak
			last = len(peaks) - 1
			while last > first and peaks[last] < threshold:
				last -= 1

			pad = int(_PAD_MS / _FRAME_MS) + 1
			start = max(0, first - pad) * frame_len
			end = min(len(samples), (last + 1 + pad) * frame_len)
			trimmed = samples[start:end]

			peak = _peak(trimmed)
			if 0 < peak < _TARGET_PEAK:
				gain = min(_TARGET_PEAK / peak, _MAX_GAIN)
				limit = _MAX_ABS_SAMPLE
				trimmed = array(
					"h", (max(-limit, min(limit, int(v * gain))) for v in trimmed)
				)
				if sys.byteorder == "big":
					trimmed.byteswap()
			return trimmed.tobytes(), peak
		except Exception as e:
			log.warning(f"SmartLingo: Audio preprocessing skipped: {e}")
			return raw, 0

	def _process(self, raw):
		import tempfile

		fd, path = tempfile.mkstemp(suffix=".wav")
		os.close(fd)
		try:
			audio, peak = self._preprocess(raw)
			if not audio:
				queueHandler.queueFunction(
					queueHandler.eventQueue,
					ui.message,
					_("No speech was detected. Please check your microphone."),
				)
				return

			with wave.open(path, "wb") as wf:
				wf.setnchannels(_CHANNELS)
				wf.setsampwidth(_SAMPLE_WIDTH)
				wf.setframerate(_SAMPLE_RATE)
				wf.writeframes(audio)

			if self._cancel_event.is_set():
				return

			try:
				text = self.transcribe(path, self.recognition_lang)
			except TranscriptionError as e:
				queueHandler.queueFunction(queueHandler.eventQueue, ui.message, str(e))
				return

			if self._cancel_event.is_set():
				return
			if text:
				queueHandler.queueFunction(queueHandler.eventQueue, self.on_text_ready, text)
			else:
				queueHandler.queueFunction(
					queueHandler.eventQueue, ui.message, _("Could not recognize speech.")
				)
		except Exception as e:
			log.error(f"SmartLingo: Audio processing error: {e}")
			queueHandler.queueFunction(
				queueHandler.eventQueue, ui.message, _("Audio processing error.")
			)
		finally:
			try:
				if os.path.exists(path):
					os.remove(path)
			except Exception as e:
				log.error(f"SmartLingo: Temp file cleanup error: {e}")

	def transcribe(self, path, lang):
		groq_key = self.api_keys.get("groq")
		if not groq_key:
			if self.api_keys.get("gemini"):
				raise TranscriptionError(
					_("Voice input needs a Groq API key. Gemini has no speech recognition.")
				)
			raise TranscriptionError(
				_("No API key found. Please add a Groq API key in SmartLingo settings.")
			)
		return self._transcribe_groq(path, lang, groq_key)

	def _transcribe_groq(self, path, lang, api_key):
		iso_lang, wants_roman = normalize_speech_lang(lang)

		data = {
			"model": STT_MODEL,
			"response_format": "json",
			# Sampling at 0 stops Whisper from looping or repeating itself.
			"temperature": 0,
			"prompt": _build_prompt(iso_lang, wants_roman),
		}
		if iso_lang:
			data["language"] = iso_lang

		url = "https://api.groq.com/openai/v1/audio/transcriptions"
		headers = {"Authorization": f"Bearer {api_key}"}

		try:
			with open(path, "rb") as f:
				files = {"file": (os.path.basename(path), f, "audio/wav")}
				resp = _session.post(
					url, headers=headers, files=files, data=data, timeout=90, verify=True
				)
		except requests.exceptions.Timeout:
			log.error("SmartLingo: Transcription request timed out.")
			raise TranscriptionError(
				_("Transcription timed out. Please record a shorter clip.")
			)
		except requests.exceptions.ConnectionError:
			log.error("SmartLingo: No internet connection during transcription.")
			raise TranscriptionError(_("No internet connection. Please check your network."))
		except Exception as e:
			log.error(f"SmartLingo: Transcription request failed: {e}")
			raise TranscriptionError(_("Could not reach the speech service: {}").format(e))

		if resp.status_code != 200:
			log.error(f"SmartLingo: Groq STT error {resp.status_code}: {resp.text[:300]}")
			raise TranscriptionError(self._describe_stt_error(resp))

		try:
			payload = resp.json()
		except ValueError:
			log.error(f"SmartLingo: Non-JSON STT response: {resp.text[:300]}")
			raise TranscriptionError(_("Unexpected response from the speech service."))

		if not isinstance(payload, dict):
			raise TranscriptionError(_("Unexpected response from the speech service."))
		return (payload.get("text") or "").strip()

	def _describe_stt_error(self, resp):
		status = resp.status_code
		if status in (400, 422):
			return _(
				"The speech service rejected the request. Please pick a different "
				"speech language in SmartLingo settings."
			)
		if status in (401, 403):
			return _("Invalid Groq API key. Please check it in SmartLingo settings.")
		if status == 413:
			return _("The recording is too large. Please record a shorter clip.")
		if status == 429:
			return _("Speech service rate limit reached. Please wait a moment and try again.")
		if status >= 500:
			return _("The speech service is temporarily unavailable. Please try again.")
		return _("Speech recognition failed (error {}).").format(status)

	def cleanup(self):
		self.cancel()
