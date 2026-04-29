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
	"openaiApiKey": "string(default=)",
	"enablechat": "boolean(default=false)",
	"autoupdate": "boolean(default=true)",
}

speakOnDemand = getSpeechOnDemandParameter()

def finally_(func, final):
	"""Calls final after func, even if it fails."""
	@wraps(func)
	def new(*args, **kwargs):
		try:
			func(*args, **kwargs)
		finally:
			final()
	return new


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("SmartLingo Pro")

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		config.conf.spec[addonName] = confspec
		self.addonConf = config.conf[addonName]
		self.lastTranslation = None
		self._last_request_id = 0
		
		SmartLingoSettingsPanel.addonConf = self.addonConf
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(SmartLingoSettingsPanel)
		
		self.settings_map = {
			"lang_from": "from", "lang_to": "into", "lang_swap": "swap", 
			"copyTranslation": "copytranslatedtext", "autoSwap": "autoswap"
		}
		for prop, key in self.settings_map.items():
			setattr(self.__class__, prop, property(
				lambda self, k=key: self.addonConf[k],
				lambda self, v, k=key: self.addonConf.__setitem__(k, v)
			))

		self._voiceManager = VoiceInputManager(self._onVoiceText)
		
		if self.addonConf.get("autoupdate", True):
			from .updater import check_for_update
			check_for_update(background=True)

	def terminate(self):
		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(SmartLingoSettingsPanel)
		except: pass
		if hasattr(self, "_voiceManager"):
			self._voiceManager.cleanup()


	@scriptHandler.script(description=_("Translates clipboard text using AI."), **speakOnDemand)
	def script_translateClipboardText(self, gesture):
		if self._voiceManager.is_recording():
			ui.message(_("Recording in progress, please wait."))
			return
		text = api.getClipData()
		if not text: ui.message(_("Clipboard is empty"))
		else: self.do_translate(text)



	def do_translate(self, text):
		self._last_request_id += 1
		request_id = self._last_request_id
		
		langFrom = self.lang_from
		langTo = self.lang_to
		langSwap = self.lang_swap if (langFrom == "auto" and self.autoSwap) else None
		
		threading.Thread(target=self._run_translation, args=(request_id, text, langFrom, langTo, langSwap)).start()

	def _run_translation(self, request_id, text, langFrom, langTo, langSwap):
		translator = Translator(langFrom, langTo, text, langSwap)
		translator.start()
		translator.join()
		
		# Only show result if this is still the most recent request
		if request_id != self._last_request_id:
			return

		if translator.error:
			ui.message(_("Translation failed: ") + translator.error)
		else:
			import nvwave, os
			recv_snd = os.path.join(os.path.dirname(__file__), "sounds", "Received.wav")
			if os.path.exists(recv_snd): nvwave.playWaveFile(recv_snd)
			
			self.lastTranslation = translator.translation
			
			use_chat = self.addonConf.get("enablechat", False)
			if use_chat:
				import wx
				wx.CallAfter(show_chat_window, self.do_translate, text, translator.translation)
			else:
				ui.message(translator.translation)
				if self.copyTranslation:
					api.copyToClip(translator.translation)

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
		self._voiceManager.recognition_lang = self.lang_from
		if not self._voiceManager.is_recording():
			ui.message(_("Recording started..."))
			
		# Pass api keys to manager
		keys = {
			"groq": self.addonConf.get("apiKey"),
			"openai": self.addonConf.get("openaiApiKey"),
			"gemini": self.addonConf.get("geminiApiKey"),
		}
		self._voiceManager.toggle(api_keys=keys)

	def _onVoiceText(self, text):
		self.do_translate(text)




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
		"kb:NVDA+alt+s": "swapLanguages",
		"kb:NVDA+alt+l": "showSettings",
		"kb:NVDA+alt+a": "announceLanguages",
	}
