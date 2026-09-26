#__init__.py
# SmartLingo addon for NVDA
# A professional AI-based translation plugin.

import addonHandler
import api
import config
import controlTypes
import globalPluginHandler
import gui
import scriptHandler
import threading
import ui
import wx
from logHandler import log
from .interface import SmartLingoSettingsPanel
from .langslist import g
from .speechOnDemand import getSpeechOnDemandParameter
from .translator import Translator
from .voiceInput import VoiceInputManager
from .chatWindow import show_chat_window, SmartLingoChatDialog

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
	"assistantsmodel": "string(default=groq)",
	"apiKey": "string(default=)",
	"geminiApiKey": "string(default=)",
	"autoupdate": "boolean(default=true)",
	"dictationlang": "string(default=en)",
	"speechlang": "string(default=auto)",
	"autotranslateclipboard": "boolean(default=false)",
}

speakOnDemand = getSpeechOnDemandParameter()

# Fix #11: Input character limit
_MAX_INPUT_CHARS = 5000

# A restart is not the only way a new release can appear, so the startup check
# is repeated on a timer. Six hours keeps a long session current without
# hammering the GitHub API.
_UPDATE_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000


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
		# Auto-translate clipboard watcher state.
		# _clipLastText: last text seen that we did NOT write ourselves.
		# _clipSelfWritten: text the addon has put on the clipboard itself.
		self._clipLastText = None
		self._clipSelfWritten = None

		SmartLingoSettingsPanel.addonConf = self.addonConf
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(SmartLingoSettingsPanel)

		self.settings_map = {
			"lang_from": "from", "lang_to": "into", "lang_swap": "swap",
			"copyTranslation": "copytranslatedtext", "autoSwap": "autoswap",
			"dictation_lang": "dictationlang", "speech_lang": "speechlang",
			"assistant_model": "assistantsmodel"
		}
		for prop, key in self.settings_map.items():
			setattr(self.__class__, prop, property(
				lambda self, k=key: self.addonConf[k],
				lambda self, v, k=key: self.addonConf.__setitem__(k, v)
			))

		self._voiceManager = VoiceInputManager(self._onVoiceText)
		self._dictation_control = None

		# Auto-translate clipboard watcher (only active when setting is enabled).
		self._clipboard_watch()

		if self.addonConf.get("autoupdate", True):
			try:
				from .updater import check_for_update
				check_for_update(background=True)
			except Exception as e:
				# Fix #8: Log instead of silent pass
				log.error(f"SmartLingo: Updater error: {e}")
			self._start_update_timer()

	def _start_update_timer(self):
		"""
		Re-runs the update check every _UPDATE_CHECK_INTERVAL_MS, so a release
		that comes out during a long NVDA session is still noticed. The timer
		itself is only created when the setting is on, and it stops again in
		terminate().
		"""
		self._update_timer = wx.Timer(gui.mainFrame)
		self._update_timer.Bind(wx.EVT_TIMER, self._onUpdateTimer)
		self._update_timer.Start(_UPDATE_CHECK_INTERVAL_MS)

	def _onUpdateTimer(self, event):
		if not self.addonConf.get("autoupdate", True):
			# The setting was switched off while the timer was running.
			return
		try:
			from .updater import check_for_update
			# background=True: stay silent unless a newer release exists, so a
			# timer tick never interrupts whatever the user is doing.
			check_for_update(background=True)
		except Exception as e:
			log.error(f"SmartLingo: Periodic update check error: {e}")

	def terminate(self):
		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(SmartLingoSettingsPanel)
		except Exception as e:
			log.error(f"SmartLingo: Error removing settings panel: {e}")
		if hasattr(self, "_cancel_event"):
			# Stop in-flight HTTP requests so nothing tries to talk to the UI
			# after the plugin is gone.
			self._cancel_event.set()
		if hasattr(self, "_voiceManager"):
			self._voiceManager.cleanup()
		self._clipboard_watch_stop = True
		if getattr(self, "_update_timer", None) is not None:
			try:
				if self._update_timer.IsRunning():
					self._update_timer.Stop()
			except Exception as e:
				log.warning(f"SmartLingo: Error stopping update timer: {e}")


	@scriptHandler.script(description=_("Translates clipboard text using AI."), **speakOnDemand)
	def script_translateClipboardText(self, gesture):
		if self._voiceManager.is_busy():
			ui.message(_("Voice input is in progress, please wait."))
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


	def _clipboard_watch(self):
		"""Start the clipboard watcher. It polls clipboard text periodically.

		Only when the auto-translate-clipboard setting is on does it translate a
		new/changed clipboard text. Text that the addon itself put on the
		clipboard (translation result copy, dictation paste) is always ignored,
		so the feature can never feed back into itself.
		"""
		self._clipboard_watch_stop = False

		try:
			self._clipLastText = api.getClipData()
		except Exception:
			self._clipLastText = None

		def _tick():
			if self._clipboard_watch_stop:
				return
			try:
				self._check_clipboard()
			except Exception as e:
				log.error(f"SmartLingo: clipboard watcher error: {e}")
			wx.CallLater(700, _tick)

		wx.CallLater(700, _tick)

	def _check_clipboard(self):
		if not self.addonConf.get("autotranslateclipboard", False):
			return
		if self._voiceManager.is_busy():
			return
		chat = SmartLingoChatDialog._instance
		if chat is not None and chat.IsShown():
			# A conversation is open. Copying something here used to start a
			# translation that spoke over the assistant and threw away the
			# conversation history, so the assistant then "forgot" everything.
			return
		try:
			text = api.getClipData()
		except Exception:
			return
		if not text or text.strip() == "":
			return
		if text == self._clipSelfWritten:
			# Text we wrote ourselves (result copy / dictation) — never re-translate.
			self._clipLastText = text
			return
		if text == self._clipLastText:
			# No change since last view — wait for something new.
			return
		self._clipLastText = text
		self.do_translate(text, auto_from_clip=True)


	def do_translate(self, text, is_follow_up=False, is_chat=False, auto_from_clip=False):
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
			args=(request_id, text, langFrom, langTo, langSwap, is_follow_up, is_chat, self._cancel_event, auto_from_clip),
			name=f"translation_{request_id}",
			daemon=True
		).start()

	def _assistant_model(self):
		"""
		The model the AI Assistant uses. It is chosen on its own and has no
		connection to the translation model, so switching one never affects the
		other. Google Translate and DeepL cannot chat, so they are not offered.
		"""
		return self.addonConf.get("assistantsmodel") or "groq"

	def _run_translation(self, request_id, text, langFrom, langTo, langSwap, is_follow_up, is_chat, cancel_event, auto_from_clip=False):
		use_chat = is_follow_up or is_chat

		# Fix #6: Thread-safe history copy
		with self._history_lock:
			history = list(self._chat_history) if use_chat else []

		try:
			# Fix #7: Direct .run() call — no nested thread start+join
			translator = Translator(
				langFrom, langTo, text, langSwap, conf=self.addonConf, history=history,
				is_chat=use_chat, cancel_event=cancel_event,
				model=self._assistant_model() if use_chat else None,
			)
			translator.run()
		except Exception as e:
			# Fix #8: Log exception
			log.error(f"SmartLingo: _run_translation exception: {e}")
			wx.CallAfter(ui.message, _("Translation failed: ") + str(e))
			return

		# Fix #2: Only process if still the latest request
		if request_id != self._last_request_id:
			return

		if translator.cancelled or cancel_event.is_set():
			return

		if translator.error:
			# In chat mode the reason has to reach the window, otherwise it is left
			# showing "SmartLingo is typing..." with no explanation anywhere.
			if use_chat:
				wx.CallAfter(show_chat_window, self.do_translate_followup, None, None, translator.error)
			else:
				# Fix #1: UI via main thread
				wx.CallAfter(ui.message, _("Translation failed: ") + translator.error)
			return

		if not translator.translation:
			if use_chat:
				wx.CallAfter(
					show_chat_window, self.do_translate_followup, None, None,
					_("The service returned an empty result.")
				)
			else:
				wx.CallAfter(ui.message, _("Translation failed: the service returned an empty result."))
			return

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
			if self.copyTranslation and not auto_from_clip:
				# Guard: remember what we wrote so the clipboard watcher skips it
				# (prevents the auto-translate feature from re-translating its
				# own output that gets copied back to the clipboard).
				self._clipSelfWritten = translator.translation
				wx.CallAfter(api.copyToClip, translator.translation)

	def do_translate_followup(self, text):
		"""Callback for the chat window to continue conversation."""
		self.do_translate(text, is_follow_up=True, is_chat=True)

	def _voice_api_keys(self):
		return {
			"groq": self.addonConf.get("apiKey"),
			"gemini": self.addonConf.get("geminiApiKey"),
		}

	@scriptHandler.script(description=_("Opens SmartLingo AI Chat Assistant."))
	def script_openChat(self, gesture):
		if self._voiceManager.is_busy():
			ui.message(_("Voice input is in progress, please wait."))
			return
		wx.CallAfter(show_chat_window, self.do_translate_followup)

	@scriptHandler.script(description=_("Swaps source and target languages."))
	def script_swapLanguages(self, gesture):
		if self._voiceManager.is_busy():
			ui.message(_("Voice input is in progress, please wait."))
			return
		if self.lang_from == "auto":
			ui.message(_("Cannot swap when source language is auto."))
			return
		self.lang_from, self.lang_to = self.lang_to, self.lang_from
		ui.message(_("Languages swapped: {f} to {t}").format(f=g(self.lang_from), t=g(self.lang_to)))

	@scriptHandler.script(description=_("Toggle voice input for AI translation."))
	def script_toggleVoiceInput(self, gesture):
		self._is_dictation_mode = False
		self._dictation_control = None
		# The translation source language is deliberately not used as the
		# speech hint: users code-switch, and a wrong forced hint makes Whisper
		# transliterate their English words into the wrong script.
		self._voiceManager.recognition_lang = self.speech_lang
		status = self._voiceManager.toggle(api_keys=self._voice_api_keys())
		if status == "started":
			ui.message(_("Recording started for translation..."))
		elif status == "stopping":
			# No message here: the manager announces "Transcribing..." once, after
			# the stop tone and the tail of the audio have been captured.
			pass
		elif status == "cancelling":
			ui.message(_("Cancelling transcription..."))
		else:
			ui.message(status)

	@scriptHandler.script(description=_("Toggle voice typing (dictation) to type directly into an edit box."))
	def script_toggleVoiceDictation(self, gesture):
		self._is_dictation_mode = True
		self._voiceManager.recognition_lang = self.speech_lang
		if not self._voiceManager.is_busy():
			# Only the starting focus is remembered here. The EDITABLE state is
			# deliberately not used to accept or reject dictation: modern Windows
			# apps such as Notepad, Edge and Office do not report it reliably, and
			# refusing to dictate because of that would be worse than trying.
			self._dictation_control = api.getFocusObject()
		status = self._voiceManager.toggle(api_keys=self._voice_api_keys())
		if status == "started":
			ui.message(_("Recording started for typing..."))
		elif status == "stopping":
			# Announced once by the manager, see script_toggleVoiceInput.
			pass
		elif status == "cancelling":
			ui.message(_("Cancelling transcription..."))
		else:
			ui.message(status)

	def _onVoiceText(self, text):
		if getattr(self, "_is_dictation_mode", False):
			dictation_lang = self.dictation_lang
			if "_roman" in dictation_lang:
				def _run_conversion():
					try:
						translator = Translator("auto", dictation_lang, text, conf=self.addonConf, is_dictation=True)
						translator.run()  # Fix #7: direct call
						if translator.cancelled:
							return
						# Fall back to the raw transcript when the conversion
						# failed, rather than typing an error message.
						converted = translator.translation if not translator.error else None
						if converted:
							wx.CallAfter(self._finish_dictation, converted)
						else:
							if translator.error:
								log.error(f"SmartLingo: Dictation conversion error: {translator.error}")
							wx.CallAfter(self._finish_dictation, text)
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
		if not text or not text.strip():
			return
		# Defensive: an API error string must never be typed into a document.
		if text.lstrip().lower().startswith(("error:", "translation failed")):
			ui.message(text)
			return
		ui.message(text)
		# Guard: this is text the addon put on the clipboard for pasting —
		# the auto-translate watcher must ignore it, otherwise voice dictation
		# output would get auto-translated too.
		self._clipSelfWritten = text
		api.copyToClip(text)
		self._schedule_dictation_paste()

	def _schedule_dictation_paste(self):
		wx.CallLater(300, self._paste_dictation)

	def _insert_into_focus(self, text):
		"""
		Inserts text through NVDA's own editable text interface.

		This is the official mechanism: no synthetic keystrokes, so it cannot
		steal focus, cannot leave a modifier key stuck down, and is not affected
		by which window happens to be foreground. Returns True when the text was
		handed to the control.
		"""
		insert = getattr(api.getFocusObject(), "insertText", None)
		if insert is None:
			return False
		try:
			insert(text)
		except Exception as e:
			# A control can expose the interface and still refuse the write, for
			# example a read-only field. The caller then falls back to the paste.
			log.debug(f"SmartLingo: insertText failed ({e}), falling back to paste")
			return False
		return True

	def _paste_dictation(self):
		"""
		Types the dictated text into whatever NVDA reports as focused, provided
		the user did not move focus somewhere that cannot accept text while the
		recognition was running.
		"""
		control = self._dictation_control
		self._dictation_control = None

		current = api.getFocusObject()
		if current is not None:
			still_editable = controlTypes.State.EDITABLE in current.states
			never_left = control is not None and current is control
			if not still_editable and not never_left:
				ui.message(
					_("Focus moved somewhere that cannot accept text, so it was copied but not pasted.")
				)
				return

		# The clipboard was filled in _finish_dictation and stays filled as a
		# safety net, so the text is still available to the user either way.
		if self._insert_into_focus(self._clipSelfWritten):
			return
		self._send_ctrl_v()

	def _send_ctrl_v(self):
		import ctypes
		KEYEVENTF_KEYUP = 0x0002
		SCAN_CTRL = 0x11D
		SCAN_V = 0x2F
		user32 = ctypes.windll.user32
		# No SetForegroundWindow here on purpose: NVDA's own focus already tracks
		# the right window, and a stale handle would pull focus somewhere else.
		try:
			user32.keybd_event(0x11, SCAN_CTRL, 0, 0)
			user32.keybd_event(0x56, SCAN_V, 0, 0)
			user32.keybd_event(0x56, SCAN_V, KEYEVENTF_KEYUP, 0)
		finally:
			# Always released, otherwise Ctrl stays stuck down for the user.
			user32.keybd_event(0x11, SCAN_CTRL, KEYEVENTF_KEYUP, 0)

	@scriptHandler.script(description=_("Cancel ongoing recording or translation."))
	def script_cancel(self, gesture):
		if self._voiceManager.is_recording():
			self._voiceManager.cancel()
			ui.message(_("Recording cancelled."))
		elif self._voiceManager.is_processing():
			self._voiceManager.cancel()
			ui.message(_("Transcription cancelled."))
		elif self._is_translating():
			# Also stop the HTTP request itself, not just its result handling.
			self._cancel_event.set()
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
		if self._voiceManager.is_busy():
			ui.message(_("Voice input is in progress, please wait."))
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
