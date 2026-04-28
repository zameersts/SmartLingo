# interface.py
# AI-focused Settings Panel for SmartLingo

import wx
import gui
import gui.guiHelper
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
		self.modelChoice = helper.addLabeledControl(_("Select AI Model:"), wx.Choice, choices=["Groq", "Gemini", "OpenAI"])
		model_val = self.addonConf.get("model", "groq").lower()
		selection_idx = 0
		if model_val == "gemini": selection_idx = 1
		elif model_val == "openai": selection_idx = 2
		self.modelChoice.SetSelection(selection_idx)
		
		# API Keys
		def makeLabeledControl(labelStr, valueStr):
			sizer = wx.BoxSizer(wx.HORIZONTAL)
			lbl = wx.StaticText(self, label=labelStr)
			ctrl = wx.TextCtrl(self, value=valueStr, style=wx.TE_PASSWORD)
			sizer.Add(lbl, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
			sizer.Add(ctrl, 1, wx.ALL, 5)
			helper.addItem(sizer)
			return lbl, ctrl
			
		self.groqLabel, self.apiKeyField = makeLabeledControl(_("Groq API Key:"), self.addonConf.get("apiKey", ""))
		self.geminiLabel, self.geminiKeyField = makeLabeledControl(_("Gemini API Key:"), self.addonConf.get("geminiApiKey", ""))
		self.openaiLabel, self.openaiKeyField = makeLabeledControl(_("OpenAI API Key:"), self.addonConf.get("openaiApiKey", ""))
		
		self.modelChoice.Bind(wx.EVT_CHOICE, self.onModelSwitch)
		wx.CallAfter(self.onModelSwitch)


		# Standard Translation Settings
		helper.addItem(wx.StaticLine(self))
		helper.addItem(wx.StaticText(self, label=_("Language Settings:")))
		
		choices = self.prepareChoices()
		from_choices = deepcopy(choices)
		if lngModule.g("zh-TW") in from_choices:
			from_choices.remove(lngModule.g("zh-TW"))
		
		self._fromChoice = helper.addLabeledControl(_("Source language:"), wx.Choice, choices=from_choices)
		
		into_choices = deepcopy(choices)
		if lngModule.g("auto") in into_choices:
			into_choices.remove(lngModule.g("auto"))
		self._intoChoice = helper.addLabeledControl(_("Target language:"), wx.Choice, choices=into_choices)
		
		self._swapChoice = helper.addLabeledControl(_("Language for swapping (if Source is Auto):"), wx.Choice, choices=into_choices)
		
		# Toggles
		self.autoSwapChk = helper.addItem(wx.CheckBox(self, label=_("Activate auto-swap if recognized source is target")))
		self.autoSwapChk.SetValue(self.addonConf.get('autoswap', True))
		
		self.copyTranslationChk = helper.addItem(wx.CheckBox(self, label=_("Copy translation result to clipboard")))
		self.copyTranslationChk.SetValue(self.addonConf.get('copytranslatedtext', True))

		self.enableChatChk = helper.addItem(wx.CheckBox(self, label=_("Enable Chat Window for translations")))
		self.enableChatChk.SetValue(self.addonConf.get('enablechat', False))

		# Set current selections
		self._fromChoice.SetStringSelection(self.getDictKey(self.addonConf.get('from', 'auto')))
		self._intoChoice.SetStringSelection(self.getDictKey(self.addonConf.get('into', 'en')))
		self._swapChoice.SetStringSelection(self.getDictKey(self.addonConf.get('swap', 'en')))

	def prepareChoices(self):
		keys = list(langslist.keys())
		auto = lngModule.g("auto")
		if auto in keys: keys.remove(auto)
		keys.sort(key=strxfrm)
		return [auto] + keys

	def getDictKey(self, currentValue):
		for key, value in langslist.items():
			if value == currentValue:
				return key
		return lngModule.g("en")

	def onModelSwitch(self, event=None):
		sel = self.modelChoice.GetStringSelection().lower()
		
		groq_show = (sel == "groq")
		gemini_show = (sel == "gemini")
		openai_show = (sel == "openai")
		
		self.groqLabel.Show(groq_show)
		self.apiKeyField.Show(groq_show)
		self.geminiLabel.Show(gemini_show)
		self.geminiKeyField.Show(gemini_show)
		self.openaiLabel.Show(openai_show)
		self.openaiKeyField.Show(openai_show)
		
		self.Layout()

	def onSave(self):
		self.addonConf['model'] = self.modelChoice.GetStringSelection().lower()
		self.addonConf['apiKey'] = self.apiKeyField.GetValue()
		self.addonConf['geminiApiKey'] = self.geminiKeyField.GetValue()
		self.addonConf['openaiApiKey'] = self.openaiKeyField.GetValue()
		
		self.addonConf['from'] = langslist[self._fromChoice.GetStringSelection()]
		self.addonConf['into'] = langslist[self._intoChoice.GetStringSelection()]
		self.addonConf['swap'] = langslist[self._swapChoice.GetStringSelection()]
		self.addonConf['autoswap'] = self.autoSwapChk.GetValue()
		self.addonConf['copytranslatedtext'] = self.copyTranslationChk.GetValue()
		self.addonConf['enablechat'] = self.enableChatChk.GetValue()
