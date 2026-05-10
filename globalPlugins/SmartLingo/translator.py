# translator.py
# AI backend for SmartLingo addon
# Security: User text is sent only to the user's chosen AI provider via their own API key.
# No data is logged, stored, or shared with any third party by this addon.

import requests
import threading
from logHandler import log
from .langslist import g

# Reuse connection and avoid proxy lookup overhead (massive speedup)
_session = requests.Session()
_session.trust_env = False

class Translator(threading.Thread):
	def __init__(self, lang_from, lang_to, text, lang_swap=None, conf=None, history=None):
		super().__init__()
		self.lang_from = lang_from
		self.lang_to = lang_to
		self.text = text
		self.lang_swap = lang_swap
		self.translation = None
		self.lang_detected = None
		self.error = None
		self.conf = conf or {}
		self.history = history or [] # List of {"role": "user/assistant", "content": "..."}

	def run(self):
		try:
			model_type = self.conf.get("model", "groq")
			
			is_roman_target = "_roman" in self.lang_to
			clean_target = self.lang_to.replace("_roman", "")
			is_roman_swap = "_roman" in self.lang_swap if self.lang_swap else False
			clean_swap = self.lang_swap.replace("_roman", "") if self.lang_swap else None
			
			system_prompt, user_text = self.prepare_prompt(self.text, self.lang_from, clean_target, is_roman_target, clean_swap, is_roman_swap)
			
			if model_type == "gemini":
				self.translation = self.send_gemini_request(system_prompt, user_text, self.conf.get("geminiApiKey", ""))
			elif model_type == "openai":
				self.translation = self.send_openai_request(system_prompt, user_text, self.conf.get("openaiApiKey", ""))
			else:
				self.translation = self.send_groq_request(system_prompt, user_text, self.conf.get("apiKey", ""))
				
		except Exception as e:
			self.error = str(e)
			log.error(f"SmartLingo: Translation error: {e}")

	def prepare_prompt(self, text, lang_from, lang_to, is_roman, swap_lang=None, is_roman_swap=False):
		# Get descriptive names (e.g. "Urdu", "Bengali")
		target_name = g(lang_to)
		swap_name = g(swap_lang) if swap_lang else ""
		
		target_script = "Roman script (Latin letters)" if is_roman else "original script"
		swap_script = "Roman script (Latin letters)" if is_roman_swap else "original script"
		
		is_chat = len(self.history) > 0
		
		system = "You are SmartLingo, a professional AI translator and linguistic assistant specializing in Pakistani Urdu and regional languages.\n\n"
		
		if is_chat:
			system += "CHAT MODE:\n"
			system += "- You are in a conversational mode. Maintain context from previous messages.\n"
			system += "- Help the user with translations, language questions, or general assistance.\n"
			system += f"- When translating, default to {target_name} ({target_script}) unless asked otherwise.\n"
		elif lang_from == "auto" and swap_lang:
			system += "AUTO-SWAP MODE:\n"
			system += f"- Your primary target is {target_name}. However, if the input is already in {target_name}, you MUST translate it into {swap_name} ({swap_script}) instead.\n"
			system += f"- If the input is in {swap_name} or ANY other language, translate it into {target_name} ({target_script}).\n"
			system += "- ALWAYS detect the language first and then choose the destination based on these two rules.\n"
		else:
			system += f"TASK: Translate the input text exclusively into {target_name} (using {target_script}).\n"

		system += "\nRULES:\n"
		if not is_chat:
			system += "- Return ONLY the translated text.\n"
			system += "- DO NOT include explanations, notes, or original text.\n"
		else:
			system += "- Be helpful, concise, and professional.\n"
			system += "- If the user asks for a translation, follow the linguistic quality rules below.\n"
		
		# Linguistic Quality Rules for Urdu/Hindi/Bengali
		combined_names = (target_name + " " + swap_name).lower()
		if any(word in combined_names for word in ["urdu", "hindi", "bengali"]):
			if "urdu" in combined_names:
				system += "- PAKISTANI URDU STANDARD: Use authentic Pakistani Urdu vocabulary (Perso-Arabic roots). Avoid Sanskritized Hindi words.\n"
				if is_roman or is_roman_swap:
					system += "- ROMAN URDU STYLE: Use standard Pakistani Romanization (e.g., 'hain' instead of 'h', 'hoon' instead of 'hu', 'kaise' instead of 'kese').\n"
		
		if not is_chat:
			# Examples for pure translation
			system += "\nEXAMPLES:\n"
			if "urdu" in combined_names:
				is_auto = lang_from == "auto"
				show_roman = is_roman or (is_auto and is_roman_swap)
				if show_roman:
					system += f"- Input: \"How are you?\" -> Output: \"Aap kaise hain?\"\n"
				else:
					system += f"- Input: \"How are you?\" -> Output: \"آپ کیسے ہیں؟\"\n"

		user_content = text
		return system, user_content

	def send_groq_request(self, system_prompt, user_text, api_key):
		if not api_key: return "Error: Groq API key missing."
		headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
		messages = [{"role": "system", "content": system_prompt}]
		messages.extend(self.history)
		messages.append({"role": "user", "content": user_text})
		
		data = {
			"model": "llama-3.3-70b-versatile",
			"messages": messages,
			"temperature": 0.3 if self.history else 0.1
		}
		resp = _session.post("https://api.groq.com/openai/v1/chat/completions", json=data, headers=headers, timeout=60, verify=True)
		if resp.status_code == 200:
			return resp.json()["choices"][0]["message"]["content"].strip()
		return f"Error {resp.status_code}: {resp.text}"

	def send_gemini_request(self, system_prompt, user_text, api_key):
		if not api_key: return "Error: Gemini API key missing."
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
		resp = _session.post(url, json=data, headers=headers, timeout=60, verify=True)
		if resp.status_code == 200:
			return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
		return f"Error {resp.status_code}: {resp.text}"

	def send_openai_request(self, system_prompt, user_text, api_key):
		if not api_key: return "Error: OpenAI API key missing."
		headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
		messages = [{"role": "system", "content": system_prompt}]
		messages.extend(self.history)
		messages.append({"role": "user", "content": user_text})
		
		data = {
			"model": "gpt-4o-mini",
			"messages": messages,
			"temperature": 0.3 if self.history else 0.1
		}
		resp = _session.post("https://api.openai.com/v1/chat/completions", json=data, headers=headers, timeout=60, verify=True)
		if resp.status_code == 200:
			return resp.json()["choices"][0]["message"]["content"].strip()
		return f"Error {resp.status_code}: {resp.text}"

