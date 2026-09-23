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
	def __init__(self, lang_from, lang_to, text, lang_swap=None, conf=None, history=None, is_chat=False, is_dictation=False, cancel_event=None):
		super().__init__()
		self.lang_from = lang_from
		self.lang_to = lang_to
		self.text = text
		self.lang_swap = lang_swap
		self.translation = None
		self.lang_detected = None
		self.error = None
		self.conf = conf or {}
		self.history = history or []
		self.is_chat = is_chat
		self.is_dictation = is_dictation
		# Fix #1: Cancel event passed from caller — checked before retry attempts
		self.cancel_event = cancel_event or threading.Event()

	def run(self):
		try:
			model_type = self.conf.get("model", "groq")

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
					model_type = "groq"

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
			if self.cancel_event.is_set():
				return None

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
						if self.cancel_event.is_set():
							return None
						time.sleep(0.1)
						waited += 0.1
					delay *= 2

			except requests.exceptions.ConnectionError:
				log.error("SmartLingo: No internet connection or DNS failure.")
				self.error = "No internet connection. Please check your network."
				return None
			except requests.exceptions.Timeout:
				log.error(f"SmartLingo: Request timed out on attempt {attempt+1}.")
				if attempt < max_attempts - 1:
					waited = 0.0
					while waited < delay:
						if self.cancel_event.is_set():
							return None
						time.sleep(0.1)
						waited += 0.1
					delay *= 2
				else:
					self.error = "Request timed out. Please try again."
					return None
			except Exception as e:
				log.error(f"SmartLingo: Unexpected network error: {e}")
				self.error = str(e)
				return None

		return last_resp

	def prepare_prompt(self, text, lang_from, lang_to, is_roman, swap_lang=None, is_roman_swap=False):
		if self.is_dictation:
			target_name = g(lang_to)
			system = (
				f"Convert the following text to {target_name} script. If it's Urdu, use Roman Urdu (Latin script). "
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

		system = "You are SmartLingo, a powerful and helpful AI Assistant. "

		if self.is_chat:
			system += "You are in CHAT MODE. Your goal is to be a standalone AI assistant for the user.\n"
			system += "- Maintain context from previous messages.\n"
			system += "- Answer questions, provide information, and hold a natural conversation.\n"
			system += "- Only translate if the user explicitly asks for a translation.\n"
			system += "- Be concise, professional, and friendly.\n"
		else:
			system += "You are a professional linguistic assistant specializing in Pakistani Urdu and regional languages.\n\n"
			if lang_from == "auto" and swap_lang:
				system += "AUTO-SWAP MODE:\n"
				system += f"- Your primary target is {target_name}. However, if the input is already in {target_name}, you MUST translate it into {swap_name} ({swap_script}) instead.\n"
				system += f"- If the input is in {swap_name} or ANY other language, translate it into {target_name} ({target_script}).\n"
				system += "- ALWAYS detect the language first and then choose the destination based on these two rules.\n"
			else:
				system += f"TASK: Translate the input text exclusively into {target_name} (using {target_script}).\n"

		system += "\nRULES:\n"
		if not self.is_chat:
			system += "- Return ONLY the translated text.\n"
			system += "- DO NOT include explanations, notes, or original text.\n"
		else:
			system += "- Answer the user directly.\n"

		combined_names = (target_name + " " + swap_name).lower()
		if any(word in combined_names for word in ["urdu", "hindi", "bengali"]):
			if "urdu" in combined_names:
				system += "- PAKISTANI URDU STANDARD: If responding in Urdu, use authentic Pakistani Urdu vocabulary (Perso-Arabic roots). Avoid Sanskritized Hindi words.\n"
				if is_roman or is_roman_swap:
					system += "- ROMAN URDU STYLE: Use standard Pakistani Romanization (e.g., 'hain' instead of 'h', 'hoon' instead of 'hu', 'kaise' instead of 'kese').\n"

		if not self.is_chat:
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
			return "Error: Groq API key missing. Please add your key in SmartLingo settings."

		headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
		messages = [{"role": "system", "content": system_prompt}]
		messages.extend(self.history)
		messages.append({"role": "user", "content": user_text})

		data = {
			"model": "openai/gpt-oss-120b",
			"messages": messages,
			"temperature": 0.3 if self.history else 0.1,
			"max_tokens": 1024
		}

		resp = self._post_with_retry(
			"https://api.groq.com/openai/v1/chat/completions",
			json=data, headers=headers, timeout=60, verify=True
		)

		if resp is None:
			return self.error or "Request was cancelled."

		if resp.status_code == 200:
			try:
				return resp.json()["choices"][0]["message"]["content"].strip()
			except (KeyError, IndexError, ValueError) as e:
				log.error(f"SmartLingo: Unexpected Groq response format: {e} | {resp.text[:200]}")
				return "Error: Unexpected response from Groq API."

		return _classify_error(resp.status_code, resp.text)

	def send_gemini_request(self, system_prompt, user_text, api_key):
		if not api_key:
			return "Error: Gemini API key missing. Please add your key in SmartLingo settings."

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
			"generationConfig": {"temperature": 0.3 if self.history else 0.1}
		}

		resp = self._post_with_retry(url, json=data, headers=headers, timeout=60, verify=True)

		if resp is None:
			return self.error or "Request was cancelled."

		if resp.status_code == 200:
			try:
				return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
			except (KeyError, IndexError, ValueError) as e:
				log.error(f"SmartLingo: Unexpected Gemini response format: {e} | {resp.text[:200]}")
				return "Error: Unexpected response from Gemini API."

		return _classify_error(resp.status_code, resp.text)

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
			return "Request was cancelled."

		try:
			resp = _do_request(lang_to)
			if resp.status_code == 200:
				data = resp.json()
				translation, detected = _parse(data)

				# Handle auto-swap
				if detected and lang_swap and detected.split("-")[0] == lang_to.split("-")[0]:
					if self.cancel_event.is_set():
						return "Request was cancelled."
					resp = _do_request(lang_swap)
					if resp.status_code == 200:
						data = resp.json()
						translation, detected = _parse(data)

				return translation

			if resp.status_code == 429:
				return "Error: Google Translate rate limit reached. Please try again later."
			return f"Error: Google Translate API returned status code {resp.status_code}."
		except Exception as e:
			log.error(f"SmartLingo: Google Translate request exception: {e}")
			return f"Error: {str(e)}"

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

	def send_deepl_free_request(self, text, lang_from, lang_to, lang_swap=None):
		"""
		Free translation via DeepL's unofficial "oneshot-free" storefront endpoint
		(the same request DeepL's own website sends). No API key required.
		Long text is split into <= _DEEPL_MAX_CHUNK_SIZE character chunks since the
		endpoint has an informal size limit per request.
		"""
		if self.cancel_event.is_set():
			return "Request was cancelled."

		# Split into chunks the same way DeepL's site itself does (fixed char size).
		chunks = [
			text[i:i + _DEEPL_MAX_CHUNK_SIZE]
			for i in range(0, len(text), _DEEPL_MAX_CHUNK_SIZE)
		] or [""]

		translated_parts = []
		effective_to = lang_to
		swapped = False

		try:
			for index, chunk in enumerate(chunks):
				if self.cancel_event.is_set():
					return "Request was cancelled."

				translation, detected = self._deepl_translate_chunk(chunk, lang_from, effective_to)

				# Auto-swap: if the detected source language is actually the target
				# language, flip to the swap language (only checked on first chunk).
				if index == 0 and not swapped and lang_swap and detected == effective_to.lower():
					effective_to = lang_swap
					swapped = True
					translation, detected = self._deepl_translate_chunk(chunk, lang_from, effective_to)

				translated_parts.append(translation)

			return "".join(translated_parts)
		except Exception as e:
			log.error(f"SmartLingo: DeepL request exception: {e}")
			return f"Error: {str(e)}"

