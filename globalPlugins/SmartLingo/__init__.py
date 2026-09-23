#__init__.py
# SmartLingo addon for NVDA
# A professional AI-based translation plugin.

import addonHandler
import api
import config
import globalPluginHandler
import gui
import scriptHandler
import threading
import ui
import wx
import tones
from functools import wraps
from logHandler import log
from .interface import SmartLingoSettingsPanel
from .langslist import g
from .speechOnDemand import getSpeechOnDemandParameter, executeWithSpeakOnDemand
from .translator import Translator
from .voiceInput import VoiceInputManager
from .chatWindow import show_chat_window

_curAddon = addonHandler.getCodeAddon()
addonName = _curAddon.name.lower()
addonHandler.initTranslation()

confspec = {
	"from": "string(default=auto)",
	"into": "string(default=en)",
	"swap": "string(default=ur_roman)",
	"copytranslatedtext": "boolean(default=true)",
	"autoswap": "boolean(default=true)",
	"model": "string(default=groq)",
	"apiKey": "string(default=)",
	"geminiApiKey": "string(default=)",
	"autoupdate": "boolean(default=true)",
	"dictationlang": "string(default=en)",
}

speakOnDemand = getSpeechOnDemandParameter()

# Fix #11: Input character limit
_MAX_INPUT_CHARS = 5000


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("SmartLingo Pro")

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		config.conf.spec[addonName] = confspec
		self.addonConf = config.conf[addonName]
		self.lastTranslation = None
		self._last_request_id = 0
		self._is_dictation_mode = False
		self._chat_history = []
		# Fix #6: Thread lock for chat history race condition
		self._history_lock = threading.Lock()
		# Fix #1: Active cancel event — set when user cancels or new request starts
		self._cancel_event = threading.Event()

		SmartLingoSettingsPanel.addonConf = self.addonConf
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(SmartLingoSettingsPanel)

		self.settings_map = {
			"lang_from": "from", "lang_to": "into", "lang_swap": "swap",
			"copyTranslation": "copytranslatedtext", "autoSwap": "autoswap",
			"dictation_lang": "dictationlang"
		}
		for prop, key in self.settings_map.items():
			setattr(self.__class__, prop, property(
				lambda self, k=key: self.addonConf[k],
				lambda self, v, k=key: self.addonConf.__setitem__(k, v)
			))

		self._voiceManager = VoiceInputManager(self._onVoiceText)

		if self.addonConf.get("autoupdate", True):
			try:
				from .updater import check_for_update
				check_for_update(background=True)
			except Exception as e:
				# Fix #8: Log instead of silent pass
				log.error(f"SmartLingo: Updater error: {e}")

	def terminate(self):
		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(SmartLingoSettingsPanel)
		except Exception as e:
			log.error(f"SmartLingo: Error removing settings panel: {e}")
		if hasattr(self, "_voiceManager"):
			self._voiceManager.cleanup()


	@scriptHandler.script(description=_("Translates clipboard text using AI."), **speakOnDemand)
	def script_translateClipboardText(self, gesture):
		if self._voiceManager.is_recording():
			ui.message(_("Recording in progress, please wait."))
			return
		text = api.getClipData()
		if not text:
			ui.message(_("Clipboard is empty"))
		else:
			# Fix #11: Input length protection
			if len(text) > _MAX_INPUT_CHARS:
				ui.message(_("Text too long. Only first {n} characters will be translated.").format(n=_MAX_INPUT_CHARS))
				text = text[:_MAX_INPUT_CHARS]
			self.do_translate(text)


	def do_translate(self, text, is_follow_up=False, is_chat=False):
		# Fix #11: Input length protection
		if len(text) > _MAX_INPUT_CHARS:
			text = text[:_MAX_INPUT_CHARS]

		# Fix #1: Cancel any in-flight HTTP request before starting new one
		self._cancel_event.set()
		self._cancel_event = threading.Event()
		self._last_request_id += 1
		request_id = self._last_request_id

		langFrom = self.lang_from
		langTo = self.lang_to
		langSwap = self.lang_swap if (langFrom == "auto" and self.autoSwap) else None

		# Reset history on fresh translation from outside the chat
		if not is_follow_up and not is_chat:
			with self._history_lock:
				self._chat_history = []

		# Fix #7: Thread just wraps _run_translation, no join
		threading.Thread(
			target=self._run_translation,
			args=(request_id, text, langFrom, langTo, langSwap, is_follow_up, is_chat, self._cancel_event),
			name=f"translation_{request_id}",
			daemon=True
		).start()

	def _run_translation(self, request_id, text, langFrom, langTo, langSwap, is_follow_up, is_chat, cancel_event):
		use_chat = is_follow_up or is_chat

		# Fix #6: Thread-safe history copy
		with self._history_lock:
			history = list(self._chat_history) if use_chat else []

		try:
			# Fix #7: Direct .run() call — no nested thread start+join
			translator = Translator(langFrom, langTo, text, langSwap, conf=self.addonConf, history=history, is_chat=is_chat or is_follow_up, cancel_event=cancel_event)
			translator.run()
		except Exception as e:
			# Fix #8: Log exception
			log.error(f"SmartLingo: _run_translation exception: {e}")
			wx.CallAfter(ui.message, _("Translation failed: ") + str(e))
			return

		# Fix #2: Only process if still the latest request
		if request_id != self._last_request_id:
			return

		if translator.error:
			# Fix #1: UI via main thread
			wx.CallAfter(ui.message, _("Translation failed: ") + translator.error)
		else:
			import nvwave, os
			recv_snd = os.path.join(os.path.dirname(__file__), "sounds", "Received.wav")
			if os.path.exists(recv_snd):
				nvwave.playWaveFile(recv_snd)

			self.lastTranslation = translator.translation

			if is_follow_up:
				# Fix #5 & #6: Limit + lock history
				with self._history_lock:
					self._chat_history.append({"role": "user", "content": text})
					self._chat_history.append({"role": "assistant", "content": translator.translation})
					if len(self._chat_history) > 20:
						self._chat_history = self._chat_history[-20:]

				# Fix #1: UI on main thread
				wx.CallAfter(show_chat_window, self.do_translate_followup, text, translator.translation)
			else:
				# Fix #1: UI on main thread
				wx.CallAfter(ui.message, translator.translation)
				if self.copyTranslation:
					wx.CallAfter(api.copyToClip, translator.translation)

	def do_translate_followup(self, text):
		"""Callback for the chat window to continue conversation."""
		self.do_translate(text, is_follow_up=True, is_chat=True)

	@scriptHandler.script(description=_("Opens SmartLingo AI Chat Assistant."))
	def script_openChat(self, gesture):
		if self._voiceManager.is_recording():
			ui.message(_("Cannot open chat while recording."))
			return
		wx.CallAfter(show_chat_window, self.do_translate_followup)

	@scriptHandler.script(description=_("Swaps source and target languages."))
	def script_swapLanguages(self, gesture):
		if self._voiceManager.is_recording():
			ui.message(_("Cannot swap languages while recording."))
			return
		if self.lang_from == "auto":
			ui.message(_("Cannot swap when source language is auto."))
			return
		self.lang_from, self.lang_to = self.lang_to, self.lang_from
		ui.message(_("Languages swapped: {f} to {t}").format(f=g(self.lang_from), t=g(self.lang_to)))

	@scriptHandler.script(description=_("Toggle voice input for AI translation."))
	def script_toggleVoiceInput(self, gesture):
		self._is_dictation_mode = False
		self._voiceManager.recognition_lang = self.lang_from
		if not self._voiceManager.is_recording():
			ui.message(_("Recording started for translation..."))
		keys = {
			"groq": self.addonConf.get("apiKey"),
			"gemini": self.addonConf.get("geminiApiKey"),
		}
		self._voiceManager.toggle(api_keys=keys)

	@scriptHandler.script(description=_("Toggle voice typing (dictation) to type directly into an edit box."))
	def script_toggleVoiceDictation(self, gesture):
		self._is_dictation_mode = True
		self._voiceManager.recognition_lang = self.dictation_lang if self.dictation_lang != "auto" else "en"
		if not self._voiceManager.is_recording():
			import controlTypes
			focus = api.getFocusObject()
			if focus and controlTypes.State.EDITABLE in focus.states:
				self._dictation_hwnd = getattr(focus, 'windowHandle', None)
			else:
				self._dictation_hwnd = None
			ui.message(_("Recording started for typing..."))
		keys = {
			"groq": self.addonConf.get("apiKey"),
			"gemini": self.addonConf.get("geminiApiKey"),
		}
		self._voiceManager.toggle(api_keys=keys)

	def _onVoiceText(self, text):
		if getattr(self, "_is_dictation_mode", False):
			dictation_lang = self.dictation_lang
			if "_roman" in dictation_lang:
				def _run_conversion():
					try:
						translator = Translator("auto", dictation_lang, text, conf=self.addonConf, is_dictation=True)
						translator.run()  # Fix #7: direct call
						if translator.error:
							log.error(f"SmartLingo: Dictation conversion error: {translator.error}")
							wx.CallAfter(self._finish_dictation, text)
						else:
							wx.CallAfter(self._finish_dictation, translator.translation)
					except Exception as e:
						log.error(f"SmartLingo: Dictation conversion exception: {e}")
						wx.CallAfter(self._finish_dictation, text)
				threading.Thread(target=_run_conversion, daemon=True).start()
			else:
				# Fix #1: ensure main thread for UI
				wx.CallAfter(self._finish_dictation, text)
		else:
			self.do_translate(text)

	def _finish_dictation(self, text):
		ui.message(text)
		api.copyToClip(text)
		hwnd = getattr(self, '_dictation_hwnd', None)

		def _paste():
			import ctypes
			KEYEVENTF_KEYUP = 0x0002
			if hwnd:
				ctypes.windll.user32.SetForegroundWindow(hwnd)
			ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)
			ctypes.windll.user32.keybd_event(0x56, 0, 0, 0)
			ctypes.windll.user32.keybd_event(0x56, 0, KEYEVENTF_KEYUP, 0)
			ctypes.windll.user32.keybd_event(0x11, 0, KEYEVENTF_KEYUP, 0)

		wx.CallLater(300, _paste)

	@scriptHandler.script(description=_("Cancel ongoing recording or translation."))
	def script_cancel(self, gesture):
		if self._voiceManager.is_recording():
			self._voiceManager.cancel()
			ui.message(_("Recording cancelled."))
		elif self._is_translating():
			self._last_request_id += 1
			ui.message(_("Translation cancelled."))
		else:
			ui.message(_("Nothing to cancel."))

	def _is_translating(self):
		"""Returns True if a translation request is currently running in the background."""
		for thread in threading.enumerate():
			if thread.name == f"translation_{self._last_request_id}" and thread.is_alive():
				return True
		return False


	@scriptHandler.script(description=_("Announces the current source and target languages."), **speakOnDemand)
	def script_announceLanguages(self, gesture):
		ui.message(_("Translate: from {f} to {t}").format(f=g(self.lang_from), t=g(self.lang_to)))


	@scriptHandler.script(description=_("Opens SmartLingo Pro settings."))
	def script_showSettings(self, gesture):
		if self._voiceManager.is_recording():
			ui.message(_("Cannot open settings while recording."))
			return
		wx.CallAfter(gui.mainFrame._popupSettingsDialog, gui.settingsDialogs.NVDASettingsDialog, SmartLingoSettingsPanel)

	__gestures = {
		"kb:NVDA+alt+t": "translateClipboardText",
		"kb:NVDA+alt+v": "toggleVoiceInput",
		"kb:NVDA+alt+d": "toggleVoiceDictation",
		"kb:NVDA+alt+c": "cancel",
		"kb:NVDA+alt+s": "swapLanguages",
		"kb:NVDA+alt+l": "showSettings",
		"kb:NVDA+alt+a": "announceLanguages",
		"kb:NVDA+alt+enter": "openChat",
	}
