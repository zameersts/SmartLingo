# translator.py
# AI backend for SmartLingo addon

import requests
import threading
import config
from logHandler import log
from .langslist import g

class Translator(threading.Thread):
	def __init__(self, lang_from, lang_to, text, lang_swap=None, use_mirror=False):
		super().__init__()
		self.lang_from = lang_from
		self.lang_to = lang_to
		self.text = text
		self.lang_swap = lang_swap
		self.translation = None
		self.lang_detected = None
		self.error = None

	def run(self):
		try:
			import addonHandler
			addon_name = addonHandler.getCodeAddon().name.lower()
			conf = config.conf[addon_name]
			model_type = conf.get("model", "groq")
			
			is_roman_target = "_roman" in self.lang_to
			clean_target = self.lang_to.replace("_roman", "")
			is_roman_swap = "_roman" in self.lang_swap if self.lang_swap else False
			clean_swap = self.lang_swap.replace("_roman", "") if self.lang_swap else None
			
			system_prompt, user_text = self.prepare_prompt(self.text, self.lang_from, clean_target, is_roman_target, clean_swap, is_roman_swap)
			
			if model_type == "gemini":
				self.translation = self.send_gemini_request(system_prompt, user_text, conf.get("geminiApiKey", ""))
			elif model_type == "openai":
				self.translation = self.send_openai_request(system_prompt, user_text, conf.get("openaiApiKey", ""))
			else:
				self.translation = self.send_groq_request(system_prompt, user_text, conf.get("apiKey", ""))
				
		except Exception as e:
			self.error = str(e)
			log.error(f"SmartLingo: Translation error: {e}")

	def prepare_prompt(self, text, lang_from, lang_to, is_roman, swap_lang=None, is_roman_swap=False):
		# Get descriptive names (e.g. "Urdu", "Bengali")
		target_name = g(lang_to)
		swap_name = g(swap_lang) if swap_lang else ""
		
		target_script = "Roman script (Latin letters)" if is_roman else "original script"
		swap_script = "Roman script (Latin letters)" if is_roman_swap else "original script"
		
		system = "You are a professional universal translator.\n\n"
		
		if lang_from == "auto" and swap_lang:
			system += "DECISION LOGIC:\n"
			system += f"1. Detect the language of the source text.\n"
			system += f"2. If the detected language is {target_name}, translate the text into {swap_name} (using {swap_script}).\n"
			system += f"3. For ANY other language (including Urdu, English, Hindi, etc.), translate the text into {target_name} (using {target_script}).\n"
			system += f"The priority is always {target_name} unless the input is already {target_name}.\n"
		else:
			system += f"TASK: Translate the input text exclusively into {target_name} (using {target_script}).\n"

		system += "\nRULES:\n"
		system += "- Return ONLY the translated text.\n"
		system += "- DO NOT include explanations, notes, or original text.\n"
		
		# Linguistic Quality Rules for Urdu/Hindi/Bengali
		if any(word in (target_name + swap_name) for word in ["Urdu", "Hindi", "Bengali"]):
			if "Urdu" in (target_name + swap_name):
				system += "- URDU VOCABULARY: Use authentic Urdu vocabulary from Perso-Arabic roots. Avoid Sanskritized Hindi words (e.g., use 'shukriya' not 'dhanyavad').\n"
		
		user_content = f"Text to translate:\n{text}"
		return system, user_content




	def send_groq_request(self, system_prompt, user_text, api_key):
		if not api_key: return "Error: Groq API key missing."
		headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
		data = {
			"model": "llama-3.3-70b-versatile",
			"messages": [
				{"role": "system", "content": system_prompt},
				{"role": "user", "content": user_text}
			],
			"temperature": 0.1
		}
		resp = requests.post("https://api.groq.com/openai/v1/chat/completions", json=data, headers=headers, timeout=60)
		if resp.status_code == 200:
			return resp.json()["choices"][0]["message"]["content"].strip()
		return f"Error {resp.status_code}: {resp.text}"

	def send_gemini_request(self, system_prompt, user_text, api_key):
		if not api_key: return "Error: Gemini API key missing."
		# Using Gemini 2.0 Flash for better system instruction support
		url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
		headers = {"Content-Type": "application/json"}
		data = {
			"system_instruction": {"parts": [{"text": system_prompt}]},
			"contents": [{"parts": [{"text": user_text}]}],
			"generationConfig": {"temperature": 0.1}
		}
		resp = requests.post(url, json=data, headers=headers, timeout=60)
		if resp.status_code == 200:
			return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
		return f"Error {resp.status_code}: {resp.text}"

	def send_openai_request(self, system_prompt, user_text, api_key):
		if not api_key: return "Error: OpenAI API key missing."
		headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
		data = {
			"model": "gpt-4o-mini",
			"messages": [
				{"role": "system", "content": system_prompt},
				{"role": "user", "content": user_text}
			],
			"temperature": 0.1
		}
		resp = requests.post("https://api.openai.com/v1/chat/completions", json=data, headers=headers, timeout=60)
		if resp.status_code == 200:
			return resp.json()["choices"][0]["message"]["content"].strip()
		return f"Error {resp.status_code}: {resp.text}"

