# chatWindow.py
# Chat window for SmartLingo Pro

import wx
import gui
import ui

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

		# Status Label
		self.statusLabel = wx.StaticText(self, label="")
		mainSizer.Add(self.statusLabel, proportion=0, flag=wx.LEFT | wx.RIGHT, border=10)

		# Input
		self.inputLabel = wx.StaticText(self, label=_("&Your Message (Press Enter to Send, Shift+Enter for new line):"))
		mainSizer.Add(self.inputLabel, proportion=0, flag=wx.LEFT | wx.TOP, border=10)

		self.inputCtrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER)
		# Fix #14: Use EVT_TEXT_ENTER instead of EVT_CHAR to avoid IME/layout conflicts
		self.inputCtrl.Bind(wx.EVT_TEXT_ENTER, self.onSend)
		# Keep Shift+Enter as newline via EVT_CHAR only for that specific case
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
		# Fix #14: Only intercept plain Enter; let Shift+Enter pass through naturally
		if keycode == wx.WXK_RETURN and not event.ShiftDown():
			self.onSend(None)
		else:
			event.Skip()

	def appendMessage(self, sender, text):
		self.historyCtrl.AppendText(f"{sender}: {text}\n")
		self.historyCtrl.SetInsertionPointEnd()

	def setStatus(self, text):
		self.statusLabel.SetLabel(text)
		# Fix #13: Speech flood — only speak short status messages, not AI responses
		# AI response text is long; speak only brief status like "Thinking..." or ""
		if text:
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


def show_chat_window(translate_callback=None, initial_text=None, ai_response=None, error=None):
	d = SmartLingoChatDialog(gui.mainFrame, translate_callback=translate_callback)

	if initial_text and getattr(d, '_last_sent', None) != initial_text:
		d.appendMessage(_("You"), initial_text)

	if error:
		# Without this the window would stay stuck on "SmartLingo is typing..."
		# and the reason would only be spoken, never shown where the user reads.
		d.setStatus("")
		d.appendMessage(_("SmartLingo"), error)
		ui.message(_("Assistant error: ") + error)
	elif ai_response:
		d.setStatus("")  # Clear "thinking..." status
		d.appendMessage(_("SmartLingo"), ai_response)
		# Fix #13: Speech flood fix — speak short notification instead of full response
		# Full response is already visible in historyCtrl for NVDA to read on focus
		ui.message(_("Response received."))

	d._last_sent = None
	# The window is only raised when the user opened it. A reply arriving while
	# they are doing something else must not steal focus or pop the dialog up.
	if not d.IsShown():
		d.Show()
		d.Raise()
		d.inputCtrl.SetFocus()
