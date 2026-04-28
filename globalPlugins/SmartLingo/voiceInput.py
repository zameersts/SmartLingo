# voiceInput.py
# Clean voice input for SmartLingo

import os
import sys
import threading
import wave
import json
import ssl
import requests
import tempfile
import tones
import ui
import queueHandler
from logHandler import log

# Add lib/ to sys.path
_addon_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_lib_dir = os.path.join(_addon_root, "lib")
if os.path.isdir(_lib_dir) and _lib_dir not in sys.path:
	sys.path.insert(0, _lib_dir)

try:
	import pyaudio
	_AUDIO_AVAILABLE = True
except ImportError:
	_AUDIO_AVAILABLE = False

_SAMPLE_RATE = 16000
_CHANNELS = 1
_CHUNK_SIZE = 1024
_GOOGLE_STT_KEY = "AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"

class VoiceInputManager:
	def __init__(self, on_text_ready):
		self.on_text_ready = on_text_ready
		self.recognition_lang = "auto"
		self._stop_event = threading.Event()
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
				ui.message("PyAudio missing.")
				return
			self._stop_event.clear()
			self._thread = threading.Thread(target=self._run, daemon=True)
			self._thread.start()

	def _run(self):
		frames = self._capture()
		
		import nvwave
		stop_snd = os.path.join(os.path.dirname(__file__), "sounds", "send.wav")
		if os.path.exists(stop_snd):
			nvwave.playWaveFile(stop_snd, asynchronous=True)
		else:
			tones.beep(440, 100)
			
		if frames:
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("Transcribing..."))
			self._process(frames)
		else:
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("No audio captured."))

	def _capture(self):
		p = pyaudio.PyAudio()
		frames = []
		try:
			import nvwave
			start_snd = os.path.join(os.path.dirname(__file__), "sounds", "Voice Start.wav")
			if os.path.exists(start_snd):
				nvwave.playWaveFile(start_snd, asynchronous=True)
			else:
				tones.beep(880, 100)
				
			stream = p.open(format=pyaudio.paInt16, channels=_CHANNELS, rate=_SAMPLE_RATE, input=True, frames_per_buffer=_CHUNK_SIZE)

			while not self._stop_event.is_set():
				try:
					data = stream.read(_CHUNK_SIZE)
					frames.append(data)
				except Exception as e:
					log.error(f"Stream read error: {e}")
					break
			stream.stop_stream()
			stream.close()
		except Exception as e:
			log.error(f"Mic error: {e}")
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("Microphone error."))
		finally:
			p.terminate()
		return frames

	def _process(self, frames):
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
		finally:
			if os.path.exists(path): os.remove(path)

	def transcribe(self, path, lang):
		# Priority 1: Groq Whisper (Dedicated STT, very fast)
		groq_key = self.api_keys.get("groq")
		if groq_key:
			text = self._transcribe_groq(path, lang, groq_key)
			if text: return text

		# Priority 2: OpenAI Whisper
		openai_key = self.api_keys.get("openai")
		if openai_key:
			text = self._transcribe_openai(path, lang, openai_key)
			if text: return text

		# Fallback: Google STT legacy
		return self._transcribe_google(path, lang)

	def _transcribe_groq(self, path, lang, api_key):
		try:
			url = "https://api.groq.com/openai/v1/audio/transcriptions"
			headers = {"Authorization": f"Bearer {api_key}"}
			# Map lang to ISO code (e.g. ur_roman -> ur)
			iso_lang = lang.split("_")[0] if lang and lang != "auto" else None
			
			with open(path, "rb") as f:
				files = {"file": (os.path.basename(path), f, "audio/wav")}
				data = {"model": "whisper-large-v3"}
				if iso_lang: data["language"] = iso_lang
				
				resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)
				if resp.status_code == 200:
					return resp.json().get("text")
				log.error(f"Groq STT error {resp.status_code}: {resp.text}")
		except Exception as e:
			log.error(f"Groq STT exception: {e}")
		return None

	def _transcribe_openai(self, path, lang, api_key):
		try:
			url = "https://api.openai.com/v1/audio/transcriptions"
			headers = {"Authorization": f"Bearer {api_key}"}
			iso_lang = lang.split("_")[0] if lang and lang != "auto" else None
			
			with open(path, "rb") as f:
				files = {"file": (os.path.basename(path), f, "audio/wav")}
				data = {"model": "whisper-1"}
				if iso_lang: data["language"] = iso_lang
				
				resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)
				if resp.status_code == 200:
					return resp.json().get("text")
		except Exception as e:
			log.error(f"OpenAI STT exception: {e}")
		return None

	def _transcribe_google(self, path, lang):
		try:
			with wave.open(path, "rb") as wf:
				data = wf.readframes(wf.getnframes())
			
			locale = lang.replace("_", "-")
			if "auto" in locale:
				try:
					import languageHandler
					nvda_lang = getattr(languageHandler, 'curLang', None)
					locale = nvda_lang.replace("_", "-") if nvda_lang and nvda_lang.lower() != "windows" else "en-US"
				except: locale = "en-US"
			elif "_" in lang: # Fix for ur_roman, hi_roman etc
				locale = lang.split("_")[0]

			url = f"https://www.google.com/speech-api/v2/recognize?output=json&lang={locale}&key={_GOOGLE_STT_KEY}"
			headers = {"Content-Type": f"audio/l16;rate={_SAMPLE_RATE}", "User-Agent": "Mozilla/5.0"}
			ctx = ssl.create_default_context()
			ctx.check_hostname = False
			ctx.verify_mode = ssl.CERT_NONE
			
			req = urllib.request.Request(url, data=data, headers=headers)
			with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
				res = resp.read().decode("utf-8")
				for line in res.splitlines():
					if not line.strip(): continue
					try:
						obj = json.loads(line)
						if "result" in obj and len(obj["result"]) > 0:
							alternatives = obj["result"][0].get("alternative", [])
							if alternatives: return alternatives[0].get("transcript")
					except: continue
		except Exception as e:
			log.error(f"Google STT error: {e}")
		return None

	def cleanup(self):
		self._stop_event.set()

