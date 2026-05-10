# chatWindow.py
# Chat window for SmartLingo Pro

import wx
import gui
import ui
import queueHandler
import addonHandler

class SmartLingoChatDialog(wx.Dialog):
	_instance = None

	def __new__(cls, *args, **kwargs):
		if SmartLingoChatDialog._instance is None:
			return super(SmartLingoChatDialog, cls).__new__(cls, *args, **kwargs)
		return SmartLingoChatDialog._instance

	def __init__(self, parent, translate_callback=None):
		if hasattr(self, "_initialized"):
			if translate_callback:
				self._translate_callback = translate_callback
			return
		super().__init__(parent, title=_("SmartLingo Chat"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._initialized = True
		SmartLingoChatDialog._instance = self
		self._translate_callback = translate_callback

		mainSizer = wx.BoxSizer(wx.VERTICAL)
		
		# History (read-only multiline)
		self.historyLabel = wx.StaticText(self, label=_("History"))
		mainSizer.Add(self.historyLabel, proportion=0, flag=wx.LEFT | wx.TOP, border=5)
		
		self.historyCtrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
		self.historyCtrl.SetDefaultStyle(wx.TextAttr(wx.BLACK))
		mainSizer.Add(self.historyCtrl, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

		# Input
		self.inputLabel = wx.StaticText(self, label=_("Message Input"))
		mainSizer.Add(self.inputLabel, proportion=0, flag=wx.LEFT | wx.TOP, border=5)
		
		self.inputCtrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER)
		self.inputCtrl.Bind(wx.EVT_TEXT_ENTER, self.onSend)
		# Enable ctrl+enter as multiline newline or just standard enter to send
		mainSizer.Add(self.inputCtrl, proportion=0, flag=wx.EXPAND | wx.ALL, border=5)

		# Buttons
		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.sendBtn = wx.Button(self, label=_("&Send"))
		self.sendBtn.Bind(wx.EVT_BUTTON, self.onSend)
		self.closeBtn = wx.Button(self, id=wx.ID_CANCEL, label=_("&Close"))
		self.closeBtn.Bind(wx.EVT_BUTTON, self.onClose)

		btnSizer.Add(self.sendBtn, flag=wx.RIGHT, border=5)
		btnSizer.Add(self.closeBtn, flag=wx.LEFT, border=5)

		mainSizer.Add(btnSizer, proportion=0, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

		self.SetSizer(mainSizer)
		self.SetMinSize((400, 500))
		self.Bind(wx.EVT_CLOSE, self.onClose)
		
		# Make Escape trigger close
		self.SetEscapeId(wx.ID_CANCEL)

	def appendMessage(self, sender, text):
		# Automatically append message. Must be called from main thread.
		self.historyCtrl.AppendText(f"{sender}: {text}\n")
		# Scroll to bottom
		self.historyCtrl.SetInsertionPointEnd()

	def onClose(self, evt):
		self.historyCtrl.SetValue("") # Clear history completely!
		self.Hide()

	def onSend(self, evt):
		text = self.inputCtrl.GetValue().strip()
		if text:
			self.inputCtrl.SetValue("")
			self.appendMessage(_("You"), text)
			self._last_sent = text
			if self._translate_callback:
				self._translate_callback(text)
			else:
				ui.message(_("Translation module not attached."))

def show_chat_window(translate_callback=None, initial_text=None, ai_response=None):
	""" Shows the chat window. Safe to call from any thread via CallAfter. """
	d = SmartLingoChatDialog(gui.mainFrame, translate_callback=translate_callback)
	
	if initial_text and getattr(d, '_last_sent', None) != initial_text:
		d.appendMessage(_("You"), initial_text)
		
	if ai_response:
		d.appendMessage(_("SmartLingo"), ai_response)
		# Read out the latest AI response directly when pushed to history
		ui.message(ai_response)
		
	d._last_sent = None # clear tracking
		
	d.Show()
	d.Raise()
	
	# Set focus to history so NVDA can read the newly arrived text
	d.historyCtrl.SetFocus()
