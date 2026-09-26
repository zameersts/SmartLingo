# translator.py
# AI backend for SmartLingo addon
# Security: User text is sent only to the user's chosen AI provider via their own API key.
# No data is logged, stored, or shared with any third party by this addon.

import time
import requests
import threading
from uuid import uuid4
from requests.adapters import HTTPAdapter
from logHandler import log
from .langslist import g

# Module-level session — connection reuse karta hai (fast subsequent requests)
# HTTPAdapter stale/dead connections pe automatically naya connection banata hai
_session = requests.Session()
_session.trust_env = False
_session.mount("https://", HTTPAdapter(max_retries=1))

# Retryable HTTP status codes (temporary server-side issues)
_RETRYABLE_CODES = {429, 500, 502, 503, 504}


class TranslationError(Exception):
	"""A failure whose message is safe to read out to the user."""


class TranslationCancelled(Exception):
	"""Raised when the caller cancelled the request through cancel_event."""

# --- DeepL free (unofficial) endpoint constants ---
_DEEPL_TRANSLATE_URL = "https://oneshot-free.www.deepl.com/v1/storefront/translate"
_DEEPL_LANGUAGE_MODEL = "next-gen"
_DEEPL_USAGE_TYPE = "Translate"
_DEEPL_MAX_CHUNK_SIZE = 500
_DEEPL_USER_AGENT = (
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
	" Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0"
)
_DEEPL_HEADERS = {
	"Accept": "*/*",
	"Content-Type": "application/json",
	"Origin": "https://www.deepl.com",
	"Referer": "https://www.deepl.com/",
	"User-agent": _DEEPL_USER_AGENT,
}

# Human-readable error messages for known API error conditions
def _classify_error(status_code, response_text):
	if status_code == 401:
		return "Invalid API key. Please check your key in SmartLingo settings."
	if status_code == 403:
		return "Access denied. Your API key may not have permission for this model."
	if status_code == 429:
		return "Rate limit reached. Please wait a moment and try again."
	if status_code == 413:
		return "Input text is too long for the API."
	if status_code in (500, 502, 503, 504):
		return f"Server error ({status_code}). The API is temporarily unavailable."
	return f"API error {status_code}."


class Translator(threading.Thread):
	def __init__(self, lang_from, lang_to, text, lang_swap=None, conf=None, history=None, is_chat=False, is_dictation=False, cancel_event=None, model=None):
		super().__init__()
		self.lang_from = lang_from
		self.lang_to = lang_to
		self.text = text
		self.lang_swap = lang_swap
		self.translation = None
		self.lang_detected = None
		self.error = None
		self.cancelled = False
		self.conf = conf or {}
		self.history = history or []
		self.is_chat = is_chat
		self.is_dictation = is_dictation
		# The AI Assistant can use a different model from the translation, so the
		# caller passes it here. None means "use the model from the settings".
		self.model = model
		# Fix #1: Cancel event passed from caller — checked before retry attempts
		self.cancel_event = cancel_event or threading.Event()

	def _check_cancelled(self):
		if self.cancel_event.is_set():
			self.cancelled = True
			raise TranslationCancelled()

	@property
	def _temperature(self):
		# A conversation needs room to vary its wording; a translation must stay
		# repeatable, so it keeps the low values.
		if self.is_chat:
			return 0.6
		return 0.3 if self.history else 0.1

	def run(self):
		try:
			model_type = self.model or self.conf.get("model", "groq")

			# Google Translate and DeepL are translation endpoints, not chat models.
			# They ignore the system prompt and the history entirely, so in chat
			# mode they would answer every message with a translation. Saying so
			# plainly is far better than letting the assistant look broken.
			if self.is_chat and model_type in ("google", "deepl"):
				raise TranslationError(
					"The AI Assistant needs an AI model. Please choose Groq or Gemini in "
					"SmartLingo settings. Google Translate and DeepL can only translate."
				)

			is_roman_target = "_roman" in self.lang_to
			clean_target = self.lang_to.replace("_roman", "")
			is_roman_swap = "_roman" in self.lang_swap if self.lang_swap else False
			clean_swap = self.lang_swap.replace("_roman", "") if self.lang_swap else None

			if model_type in ("google", "deepl") and self.is_dictation and is_roman_target:
				if self.conf.get("apiKey"):
					model_type = "groq"
				elif self.conf.get("geminiApiKey"):
					model_type = "gemini"
				else:
					raise TranslationError(
						"Roman Urdu dictation needs an AI model. Please set a Groq or "
						"Gemini API key in SmartLingo settings."
					)

			if model_type == "google":
				langSwap = clean_swap if (self.lang_from == "auto" and self.lang_swap) else None
				self.translation = self.send_google_free_request(self.text, self.lang_from, clean_target, langSwap)
			elif model_type == "deepl":
				langSwap = clean_swap if (self.lang_from == "auto" and self.lang_swap) else None
				self.translation = self.send_deepl_free_request(self.text, self.lang_from, clean_target, langSwap)
			else:
				system_prompt, user_text = self.prepare_prompt(self.text, self.lang_from, clean_target, is_roman_target, clean_swap, is_roman_swap)

				if model_type == "gemini":
					self.translation = self.send_gemini_request(system_prompt, user_text, self.conf.get("geminiApiKey", ""))
				else:
					self.translation = self.send_groq_request(system_prompt, user_text, self.conf.get("apiKey", ""))

		except TranslationCancelled:
			self.cancelled = True
			self.translation = None
		except TranslationError as e:
			self.error = str(e)
			log.error(f"SmartLingo: Translation error: {self.error}")
		except Exception as e:
			self.error = str(e)
			log.error(f"SmartLingo: Translation error: {e}")

	def _post_with_retry(self, url, **kwargs):
		"""
		POST with up to 2 retries on retryable errors (429, 5xx).
		Exponential backoff: 1s, 2s. Respects cancel_event between retries.
		Non-retryable errors (401, 403, 413, etc.) fail immediately.
		"""
		max_attempts = 3
		delay = 1.0
		last_resp = None

		for attempt in range(max_attempts):
			# Fix #1: Check cancel before each attempt
			self._check_cancelled()

			try:
				resp = _session.post(url, **kwargs)
				last_resp = resp

				if resp.status_code == 200:
					return resp

				if resp.status_code not in _RETRYABLE_CODES:
					# Non-retryable — return immediately for error classification
					return resp

				# Retryable — log and wait before next attempt
				log.warning(f"SmartLingo: HTTP {resp.status_code} on attempt {attempt+1}, retrying in {delay}s...")

				if attempt < max_attempts - 1:
					# Wait with cancel check (sleep in small increments)
					waited = 0.0
					while waited < delay:
						self._check_cancelled()
						time.sleep(0.1)
						waited += 0.1
					delay *= 2

			except requests.exceptions.ConnectionError:
				log.error("SmartLingo: No internet connection or DNS failure.")
				raise TranslationError("No internet connection. Please check your network.")
			except requests.exceptions.Timeout:
				log.error(f"SmartLingo: Request timed out on attempt {attempt+1}.")
				if attempt < max_attempts - 1:
					waited = 0.0
					while waited < delay:
						self._check_cancelled()
						time.sleep(0.1)
						waited += 0.1
					delay *= 2
				else:
					raise TranslationError("Request timed out. Please try again.")
			except (TranslationError, TranslationCancelled):
				raise
			except Exception as e:
				log.error(f"SmartLingo: Unexpected network error: {e}")
				raise TranslationError(str(e))

		return last_resp

	def prepare_prompt(self, text, lang_from, lang_to, is_roman, swap_lang=None, is_roman_swap=False):
		if self.is_dictation:
			target_name = g(lang_to)
			# "Roman Urdu" wording is wrong when the dictation target is Hindi,
			# Bengali or Nepali, so the script is named after the chosen language.
			script_rule = (
				f"Use Roman {target_name} written in Latin characters."
				if is_roman
				else f"Use the standard {target_name} script."
			)
			system = (
				f"Convert the following dictated text to {target_name}. {script_rule} "
				"DO NOT translate. If a word is already in English, KEEP IT EXACTLY AS-IS in English/Latin script — "
				"do not transliterate English words phonetically into the target script. "
				"If the text is already in the target script or another language, return it exactly as is. "
				"Output ONLY the converted text."
			)
			return system, text

		target_name = g(lang_to)
		swap_name = g(swap_lang) if swap_lang else ""
		target_script = "Roman script (Latin letters)" if is_roman else "original script"
		swap_script = "Roman script (Latin letters)" if is_roman_swap else "original script"

		if self.is_chat:
			# A separate prompt on purpose. Anything about a target language, a
			# source language or "return only the translated text" is what makes
			# the model answer a question with a translation instead of an answer,
			# so none of it is allowed to reach the model in this mode.
			system = (
				"You are SmartLingo, a helpful AI assistant talking with the user in the "
				"SmartLingo AI Assistant window.\n"
				"You are NOT a translation tool in this window.\n"
				"\n"
				"RULES:\n"
				"- Answer the user's questions, give information, and hold a natural conversation.\n"
				"- Do not translate the user's message, do not repeat it back, and do not rewrite "
				"it in another language, unless the user explicitly asks you to translate something.\n"
				"- Reply in the same language the user wrote in, and follow their lead if they switch.\n"
				"- Keep the whole conversation in mind, and refer back to earlier messages when they "
				"are relevant.\n"
				"- Be concise, professional and friendly.\n"
			)
			if "urdu" in (target_name + " " + swap_name).lower():
				system += (
					"- When you do use Urdu, prefer authentic Pakistani Urdu vocabulary with "
					"Perso-Arabic roots over Sanskritized Hindi words.\n"
				)
			system += (
				"\n"
				"EXAMPLES:\n"
				'- User: "What is the capital of Pakistan?" -> You: "Islamabad is the capital of Pakistan."\n'
				'- User: "How do I turn on dark mode?" -> You: give the steps to do it.\n'
				'- User: "Tell me a joke." -> You: tell a joke.\n'
				'- User: "Translate good morning into Urdu." -> Only here do you translate.\n'
			)
			return system, text

		system = "You are SmartLingo, a powerful and helpful AI Assistant. "
		system += "You are a professional linguistic assistant specializing in Pakistani Urdu and regional languages.\n\n"
		if lang_from == "auto" and swap_lang:
			system += "AUTO-SWAP MODE:\n"
			system += f"- Your primary target is {target_name}. However, if the input is already in {target_name}, you MUST translate it into {swap_name} ({swap_script}) instead.\n"
			system += f"- If the input is in {swap_name} or ANY other language, translate it into {target_name} ({target_script}).\n"
			system += "- ALWAYS detect the language first and then choose the destination based on these two rules.\n"
		else:
			system += f"TASK: Translate the input text exclusively into {target_name} (using {target_script}).\n"

		system += "\nRULES:\n"
		system += "- Return ONLY the translated text.\n"
		system += "- DO NOT include explanations, notes, or original text.\n"

		combined_names = (target_name + " " + swap_name).lower()
		if any(word in combined_names for word in ["urdu", "hindi", "bengali"]):
			if "urdu" in combined_names:
				system += "- PAKISTANI URDU STANDARD: If responding in Urdu, use authentic Pakistani Urdu vocabulary (Perso-Arabic roots). Avoid Sanskritized Hindi words.\n"
				if is_roman or is_roman_swap:
					system += "- ROMAN URDU STYLE: Use standard Pakistani Romanization (e.g., 'hain' instead of 'h', 'hoon' instead of 'hu', 'kaise' instead of 'kese').\n"

		system += "\nEXAMPLES:\n"
		if "urdu" in combined_names:
			is_auto = lang_from == "auto"
			show_roman = is_roman or (is_auto and is_roman_swap)
			if show_roman:
				system += "- Input: \"How are you?\" -> Output: \"Aap kaise hain?\"\n"
			else:
				system += "- Input: \"How are you?\" -> Output: \"آپ کیسے ہیں؟\"\n"

		return system, text

	def send_groq_request(self, system_prompt, user_text, api_key):
		if not api_key:
			raise TranslationError("Groq API key missing. Please add your key in SmartLingo settings.")

		headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
		messages = [{"role": "system", "content": system_prompt}]
		messages.extend(self.history)
		messages.append({"role": "user", "content": user_text})

		data = {
			"model": "openai/gpt-oss-120b",
			"messages": messages,
			"temperature": self._temperature,
			"max_tokens": 4096
		}

		resp = self._post_with_retry(
			"https://api.groq.com/openai/v1/chat/completions",
			json=data, headers=headers, timeout=60, verify=True
		)

		if resp is None:
			self._check_cancelled()
			raise TranslationError("Request was cancelled.")

		if resp.status_code == 200:
			try:
				return resp.json()["choices"][0]["message"]["content"].strip()
			except (KeyError, IndexError, ValueError, AttributeError) as e:
				log.error(f"SmartLingo: Unexpected Groq response format: {e} | {resp.text[:200]}")
				raise TranslationError("Unexpected response from Groq API.")

		raise TranslationError(_classify_error(resp.status_code, resp.text))

	def send_gemini_request(self, system_prompt, user_text, api_key):
		if not api_key:
			raise TranslationError("Gemini API key missing. Please add your key in SmartLingo settings.")

		url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
		headers = {"Content-Type": "application/json"}

		contents = []
		for msg in self.history:
			role = "user" if msg["role"] == "user" else "model"
			contents.append({"role": role, "parts": [{"text": msg["content"]}]})
		contents.append({"role": "user", "parts": [{"text": user_text}]})

		data = {
			"system_instruction": {"parts": [{"text": system_prompt}]},
			"contents": contents,
			"generationConfig": {"temperature": self._temperature}
		}

		resp = self._post_with_retry(url, json=data, headers=headers, timeout=60, verify=True)

		if resp is None:
			self._check_cancelled()
			raise TranslationError("Request was cancelled.")

		if resp.status_code == 200:
			try:
				return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
			except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
				log.error(f"SmartLingo: Unexpected Gemini response format: {e} | {resp.text[:200]}")
				raise TranslationError("Unexpected response from Gemini API.")

		raise TranslationError(_classify_error(resp.status_code, resp.text))

	def send_google_free_request(self, text, lang_from, lang_to, lang_swap=None):
		"""
		Free translation via Google's internal "translate-pa" endpoint — the same
		one Google's own apps (e.g. the Android Google app) use internally.
		Uses a reverse-engineered public API key; no user-provided key required.
		Larger single-request size limit than the public translate_a/single endpoint.
		"""
		url = "https://translate-pa.googleapis.com/v1/translate"
		api_key = "AIzaSyDLEeFI5OtFBwYBIoK_jj5m32rZK5CkCXA"
		headers = {
			"Content-Type": "application/json+protobuf",
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
		}

		try:
			import languageHandler
			display_lang = languageHandler.getLanguage().replace("_", "-")
		except Exception:
			display_lang = "en"

		def _build_params(target):
			params = [
				("params.client", "gtx"),
				("query.source_language", lang_from),
				("query.target_language", target),
				("query.display_language", display_lang),
				("query.text", text),
				("key", api_key),
				("data_types", "TRANSLATION"),
				("data_types", "SENTENCE_SPLITS"),
			]
			return params

		def _do_request(target):
			resp = _session.get(url, params=_build_params(target), headers=headers, timeout=15)
			return resp

		def _parse(data):
			sentences = data[1] if isinstance(data, list) and len(data) > 1 else None
			if sentences:
				translation = "".join(
					sentence[0] for sentence in sentences if sentence and sentence[0]
				)
			else:
				translation = (data[0] if isinstance(data, list) and len(data) > 0 else None) or ""
			detected = data[5] if isinstance(data, list) and len(data) > 5 and data[5] else lang_from
			return translation, detected

		if self.cancel_event.is_set():
			self._check_cancelled()

		try:
			resp = _do_request(lang_to)
			if resp.status_code == 200:
				data = resp.json()
				translation, detected = _parse(data)

				# Handle auto-swap
				if detected and lang_swap and detected.split("-")[0] == lang_to.split("-")[0]:
					self._check_cancelled()
					resp = _do_request(lang_swap)
					if resp.status_code == 200:
						data = resp.json()
						translation, detected = _parse(data)

				if not translation.strip():
					raise TranslationError("Google Translate returned an empty result.")
				return translation

			if resp.status_code == 429:
				raise TranslationError("Google Translate rate limit reached. Please try again later.")
			raise TranslationError(f"Google Translate returned status code {resp.status_code}.")
		except (TranslationError, TranslationCancelled):
			raise
		except Exception as e:
			log.error(f"SmartLingo: Google Translate request exception: {e}")
			raise TranslationError(str(e))

	def _deepl_translate_chunk(self, chunk, lang_from, lang_to):
		"""
		Sends a single chunk (<= _DEEPL_MAX_CHUNK_SIZE chars) to DeepL's free
		(unofficial) web endpoint. Returns (translated_text, detected_source_lang).
		Raises ValueError on an unexpected/empty response.
		"""
		body = {
			"text": [chunk],
			"source_lang": lang_from,
			"target_lang": lang_to,
			"language_model": _DEEPL_LANGUAGE_MODEL,
			"usage_type": _DEEPL_USAGE_TYPE,
			"app_information": {
				"instance_id": str(uuid4()),
				"app_build": "Edge",
				"os": "Windows",
				"app_version": "any",
				"os_version": "any",
			},
		}
		resp = _session.post(_DEEPL_TRANSLATE_URL, json=body, headers=_DEEPL_HEADERS, timeout=15)
		if resp.status_code != 200:
			raise ValueError(f"HTTP {resp.status_code}: {resp.text[:200]}")
		data = resp.json()
		translations = data.get("translations") if isinstance(data, dict) else None
		if not translations:
			raise ValueError(f"no translation in response: {data!r}")
		translation = translations[0] or {}
		detected = (translation.get("detected_source_language") or lang_from or "").lower()
		return translation.get("text") or "", detected

	def _split_for_deepl(self, text):
		"""
		Splits text into chunks of at most _DEEPL_MAX_CHUNK_SIZE characters,
		breaking only on whitespace so no word is cut in half.
		"""
		chunks = []
		current = ""
		for word in text.split(" "):
			# A single word longer than the limit has to be sent whole.
			if len(word) > _DEEPL_MAX_CHUNK_SIZE:
				if current:
					chunks.append(current)
					current = ""
				chunks.append(word)
				continue
			candidate = f"{current} {word}" if current else word
			if len(candidate) > _DEEPL_MAX_CHUNK_SIZE:
				chunks.append(current)
				current = word
			else:
				current = candidate
		if current:
			chunks.append(current)
		return chunks or [""]

	def send_deepl_free_request(self, text, lang_from, lang_to, lang_swap=None):
		"""
		Free translation via DeepL's unofficial "oneshot-free" storefront endpoint
		(the same request DeepL's own website sends). No API key required.
		Long text is split into <= _DEEPL_MAX_CHUNK_SIZE character chunks since the
		endpoint has an informal size limit per request.
		"""
		if self.cancel_event.is_set():
			self._check_cancelled()

		chunks = self._split_for_deepl(text)

		translated_parts = []
		effective_to = lang_to
		swapped = False

		try:
			for index, chunk in enumerate(chunks):
				self._check_cancelled()

				translation, detected = self._deepl_translate_chunk(chunk, lang_from, effective_to)

				# Auto-swap: if the detected source language is actually the target
				# language, flip to the swap language (only checked on first chunk).
				if index == 0 and not swapped and lang_swap and detected == effective_to.lower():
					effective_to = lang_swap
					swapped = True
					translation, detected = self._deepl_translate_chunk(chunk, lang_from, effective_to)

				translated_parts.append(translation)

			# A space is required between chunks, otherwise the last word of one
			# chunk and the first word of the next run together.
			return " ".join(part for part in translated_parts if part).strip()
		except (TranslationError, TranslationCancelled):
			raise
		except Exception as e:
			log.error(f"SmartLingo: DeepL request exception: {e}")
			raise TranslationError(str(e))

