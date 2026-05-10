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
		super().__init__(parent, title=_("SmartLingo AI Assistant"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._initialized = True
		SmartLingoChatDialog._instance = self
		self._translate_callback = translate_callback

		mainSizer = wx.BoxSizer(wx.VERTICAL)
		
		# History (read-only multiline)
		self.historyLabel = wx.StaticText(self, label=_("&Conversation History:"))
		mainSizer.Add(self.historyLabel, proportion=0, flag=wx.LEFT | wx.TOP, border=10)
		
		self.historyCtrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
		self.historyCtrl.SetDefaultStyle(wx.TextAttr(wx.BLACK))
		mainSizer.Add(self.historyCtrl, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

		# Status Label (e.g. "Thinking...")
		self.statusLabel = wx.StaticText(self, label="")
		mainSizer.Add(self.statusLabel, proportion=0, flag=wx.LEFT | wx.RIGHT, border=10)

		# Input
		self.inputLabel = wx.StaticText(self, label=_("&Your Message (Press Enter to Send, Shift+Enter for new line):"))
		mainSizer.Add(self.inputLabel, proportion=0, flag=wx.LEFT | wx.TOP, border=10)
		
		self.inputCtrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER)
		# Add specific binding for Enter vs Shift+Enter
		self.inputCtrl.Bind(wx.EVT_CHAR, self.onChar)
		mainSizer.Add(self.inputCtrl, proportion=0, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

		# Buttons
		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.sendBtn = wx.Button(self, label=_("&Send"))
		self.sendBtn.Bind(wx.EVT_BUTTON, self.onSend)
		self.closeBtn = wx.Button(self, id=wx.ID_CANCEL, label=_("&Close Assistant"))
		self.closeBtn.Bind(wx.EVT_BUTTON, self.onClose)

		btnSizer.Add(self.sendBtn, flag=wx.RIGHT, border=10)
		btnSizer.Add(self.closeBtn, flag=wx.LEFT, border=10)

		mainSizer.Add(btnSizer, proportion=0, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)

		self.SetSizer(mainSizer)
		self.SetMinSize((500, 600))
		self.Bind(wx.EVT_CLOSE, self.onClose)
		self.SetEscapeId(wx.ID_CANCEL)

	def onChar(self, event):
		keycode = event.GetKeyCode()
		if keycode == wx.WXK_RETURN and not event.ShiftDown():
			self.onSend(None)
		else:
			event.Skip()

	def appendMessage(self, sender, text):
		self.historyCtrl.AppendText(f"{sender}: {text}\n\n")
		self.historyCtrl.SetInsertionPointEnd()

	def setStatus(self, text):
		self.statusLabel.SetLabel(text)
		if text:
			# Use ui.message for NVDA to announce status (like "AI is thinking...")
			ui.message(text)

	def onClose(self, evt):
		self.historyCtrl.SetValue("")
		self.Hide()

	def onSend(self, evt):
		text = self.inputCtrl.GetValue().strip()
		if text:
			self.inputCtrl.SetValue("")
			self.appendMessage(_("You"), text)
			self._last_sent = text
			self.setStatus(_("SmartLingo is typing..."))
			if self._translate_callback:
				self._translate_callback(text)
			else:
				ui.message(_("Error: Assistant module not connected."))

def show_chat_window(translate_callback=None, initial_text=None, ai_response=None):
	d = SmartLingoChatDialog(gui.mainFrame, translate_callback=translate_callback)
	
	if initial_text and getattr(d, '_last_sent', None) != initial_text:
		d.appendMessage(_("You"), initial_text)
		
	if ai_response:
		d.setStatus("") # Clear thinking status
		d.appendMessage(_("SmartLingo"), ai_response)
		# NVDA will read the text when it's added to history if we set focus or use ui.message
		ui.message(ai_response)
		
	d._last_sent = None
	d.Show()
	d.Raise()
	
	# Focus the input field so user can type immediately
	d.inputCtrl.SetFocus()
