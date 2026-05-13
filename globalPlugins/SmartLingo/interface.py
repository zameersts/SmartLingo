# interface.py
# AI-focused Settings Panel for SmartLingo

import wx
import gui
import gui.guiHelper
import webbrowser
from gui.settingsDialogs import SettingsPanel
from .langslist import langslist
from . import langslist as lngModule
import addonHandler
from copy import deepcopy
from locale import strxfrm

addonHandler.initTranslation()

class SmartLingoSettingsPanel(SettingsPanel):
	title = _("SmartLingo Pro Settings")

	def makeSettings(self, sizer):
		helper = gui.guiHelper.BoxSizerHelper(self, sizer=sizer)
		
		# AI Model Selection
		helper.addItem(wx.StaticText(self, label=_("AI Configuration:")))
		self.modelChoice = helper.addLabeledControl(_("Select AI Model:"), wx.Choice, choices=["Groq", "Gemini"])
		model_val = self.addonConf.get("model", "groq").lower()
		selection_idx = 0
		if model_val == "gemini": selection_idx = 1
		self.modelChoice.SetSelection(selection_idx)
		
		# API Keys
		def makeLabeledControl(labelStr, valueStr, api_url=None):
			sizer = wx.BoxSizer(wx.HORIZONTAL)
			lbl = wx.StaticText(self, label=labelStr)
			ctrl = wx.TextCtrl(self, value=valueStr, style=wx.TE_PASSWORD)
			sizer.Add(lbl, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
			sizer.Add(ctrl, 1, wx.ALL, 5)
			
			btn = None
			if api_url:
				btn = wx.Button(self, label=_("Get API Key"))
				btn.Bind(wx.EVT_BUTTON, lambda e: webbrowser.open(api_url))
				sizer.Add(btn, 0, wx.ALL, 5)
				
			helper.addItem(sizer)
			return lbl, ctrl, btn
			
		self.groqLabel, self.apiKeyField, self.groqBtn = makeLabeledControl(_("Groq API Key:"), self.addonConf.get("apiKey", ""), "https://console.groq.com/keys")
		self.geminiLabel, self.geminiKeyField, self.geminiBtn = makeLabeledControl(_("Gemini API Key:"), self.addonConf.get("geminiApiKey", ""), "https://aistudio.google.com/app/apikey")
		
		self.modelChoice.Bind(wx.EVT_CHOICE, self.onModelSwitch)
		wx.CallAfter(self.onModelSwitch)

		# Standard Translation Settings
		helper.addItem(wx.StaticLine(self))
		helper.addItem(wx.StaticText(self, label=_("Language Settings:")))
		
		choices = self.prepareChoices()
		from_choices = deepcopy(choices)
		
		zh_tw_name = lngModule.g("zh-TW")
		if zh_tw_name in from_choices:
			from_choices.remove(zh_tw_name)
		
		self._fromChoice = helper.addLabeledControl(_("Source language:"), wx.Choice, choices=from_choices)
		
		into_choices = deepcopy(choices)
		auto_name = lngModule.g("auto")
		if auto_name in into_choices:
			into_choices.remove(auto_name)
		self._intoChoice = helper.addLabeledControl(_("Target language:"), wx.Choice, choices=into_choices)
		self._swapChoice = helper.addLabeledControl(_("Language for swapping (if Source is Auto):"), wx.Choice, choices=into_choices)
		self._dictationChoice = helper.addLabeledControl(_("Voice Dictation language:"), wx.Choice, choices=from_choices)
		
		# Toggles
		self.autoSwapChk = helper.addItem(wx.CheckBox(self, label=_("Activate auto-swap if recognized source is target")))
		self.autoSwapChk.SetValue(self.addonConf.get('autoswap', True))
		
		self.copyTranslationChk = helper.addItem(wx.CheckBox(self, label=_("Copy translation result to clipboard")))
		self.copyTranslationChk.SetValue(self.addonConf.get('copytranslatedtext', True))

		# Update Settings
		helper.addItem(wx.StaticLine(self))
		self.autoUpdateChk = helper.addItem(wx.CheckBox(self, label=_("Automatically check for updates on startup")))
		self.autoUpdateChk.SetValue(self.addonConf.get('autoupdate', True))
		
		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.checkUpdateBtn = wx.Button(self, label=_("Check for Updates now"))
		self.checkUpdateBtn.Bind(wx.EVT_BUTTON, self.onCheckUpdate)
		btnSizer.Add(self.checkUpdateBtn, 0, wx.ALL, 5)
		helper.addItem(btnSizer)

		# Set current selections
		self._fromChoice.SetStringSelection(self.getDisplayName(self.addonConf.get('from', 'auto')))
		self._intoChoice.SetStringSelection(self.getDisplayName(self.addonConf.get('into', 'en')))
		self._swapChoice.SetStringSelection(self.getDisplayName(self.addonConf.get('swap', 'ur_roman')))
		self._dictationChoice.SetStringSelection(self.getDisplayName(self.addonConf.get('dictationlang', 'en')))

	def prepareChoices(self):
		"""
		Returns sorted list of display names.
		langslist = {display_name: lang_code}
		"""
		all_names = list(langslist.keys())
		auto_name = lngModule.g("auto")
		if auto_name in all_names:
			all_names.remove(auto_name)
		all_names.sort(key=strxfrm)
		return [auto_name] + all_names

	def getDisplayName(self, lang_code):
		"""
		Returns the display name for a given language code using the g() function.
		Previously getDictKey() returned an incorrect fallback value.
		"""
		name = lngModule.g(lang_code)
		if name in langslist:
			return name
		return lngModule.g("en")

	def onModelSwitch(self, event=None):
		sel = self.modelChoice.GetStringSelection().lower()
		show_groq = (sel == "groq")
		show_gemini = (sel == "gemini")
		
		self.groqLabel.Show(show_groq)
		self.apiKeyField.Show(show_groq)
		self.groqBtn.Show(show_groq)
		
		self.geminiLabel.Show(show_gemini)
		self.geminiKeyField.Show(show_gemini)
		self.geminiBtn.Show(show_gemini)
		
		self.Layout()

	def onCheckUpdate(self, event):
		from .updater import check_for_update
		check_for_update(background=False)

	def onSave(self):
		self.addonConf['model'] = self.modelChoice.GetStringSelection().lower()
		self.addonConf['apiKey'] = self.apiKeyField.GetValue()
		self.addonConf['geminiApiKey'] = self.geminiKeyField.GetValue()
		# Map display name back to language code using .get() to avoid crashes on unknown names
		self.addonConf['from'] = langslist.get(self._fromChoice.GetStringSelection(), 'auto')
		self.addonConf['into'] = langslist.get(self._intoChoice.GetStringSelection(), 'en')
		self.addonConf['swap'] = langslist.get(self._swapChoice.GetStringSelection(), 'ur_roman')
		self.addonConf['dictationlang'] = langslist.get(self._dictationChoice.GetStringSelection(), 'en')
		self.addonConf['autoswap'] = self.autoSwapChk.GetValue()
		self.addonConf['copytranslatedtext'] = self.copyTranslationChk.GetValue()
		self.addonConf['autoupdate'] = self.autoUpdateChk.GetValue()
