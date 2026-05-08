# updater.py
# SmartLingo GitHub Updater
# Security: All downloads validated against GitHub domain. No user data collected.

import requests
import json
import os
import tempfile
import threading
import wx
import gui
import addonHandler
import ssl
import time

GITHUB_REPO = "zameersts/SmartLingo"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# Security: Only these trusted domains are allowed for downloads
_ALLOWED_DOWNLOAD_HOSTS = (
	"objects.githubusercontent.com",
	"github.com",
	"releases.githubusercontent.com",
)
_MAX_DOWNLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB hard cap

def get_current_version():
	try:
		addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
		addon = addonHandler.Addon(addon_dir)
		return addon.manifest['version']
	except Exception:
		return "1.0"

def check_for_update(background=False):
	threading.Thread(target=_check_update_thread, args=(background,), daemon=True).start()



def _parse_version(v):
	"""
	Parses a version string into a list of integers for comparison.
	Handles prefixes like 'v' and pre-release tags like '-beta'.
	e.g. "v1.10-beta" -> [1, 10], "1.1" -> [1, 1]
	"""
	# Strip 'v' prefix and pre-release tags before parsing
	clean = v.lstrip("v").split("-")[0].split("+")[0]
	parts = []
	for part in clean.split("."):
		digits = ''.join(c for c in part if c.isdigit())
		if digits:
			parts.append(int(digits))
	return parts if parts else [0]

def _check_update_thread(background):
	try:
		url_with_ts = f"{LATEST_RELEASE_URL}?ts={int(time.time())}"
		headers = {
			"User-Agent": "NVDA-SmartLingo-Updater",
			"Cache-Control": "no-cache",
			"Pragma": "no-cache"
		}
		resp = requests.get(url_with_ts, headers=headers, timeout=10)
		resp.raise_for_status()
		data = resp.json()
			
		latest_version = data.get("tag_name", "").lstrip("v")
		current_version = get_current_version().lstrip("v")
		
		if _parse_version(latest_version) > _parse_version(current_version):
			download_url = None
			for asset in data.get("assets", []):
				if asset.get("name", "").endswith(".nvda-addon"):
					download_url = asset.get("browser_download_url")
					break

			# Get release notes from GitHub release body
			release_notes = _clean_release_notes(data.get("body", ""))

			if download_url:
				# SECURITY: Validate URL is from trusted GitHub domain before prompting
				if not _is_safe_download_url(download_url):
					if not background:
						wx.CallAfter(gui.messageBox,
							_("Update download URL is not from a trusted source. Aborting."),
							_("SmartLingo Security Warning"), wx.OK | wx.ICON_ERROR)
					return
				wx.CallAfter(_prompt_update, latest_version, download_url, release_notes)
			elif not background:
				wx.CallAfter(gui.messageBox,
					_("Update found, but no addon file is attached to the release."),
					_("SmartLingo Updater"), wx.OK | wx.ICON_WARNING)
		else:
			if not background:
				wx.CallAfter(gui.messageBox,
					_("You are already using the latest version of SmartLingo."),
					_("SmartLingo Updater"), wx.OK | wx.ICON_INFORMATION)

	except requests.exceptions.HTTPError as e:
		if not background:
			if e.response.status_code == 403:
				msg = _("GitHub API rate limit exceeded. Please try again later.")
			else:
				msg = _("Failed to check for updates: {}").format(e)
			wx.CallAfter(gui.messageBox, msg, _("SmartLingo Updater Error"), wx.OK | wx.ICON_ERROR)
	except requests.exceptions.RequestException as e:
		if not background:
			wx.CallAfter(gui.messageBox,
				_("Network error while checking for updates: {}").format(e),
				_("SmartLingo Updater Error"), wx.OK | wx.ICON_ERROR)
	except Exception as e:
		if not background:
			wx.CallAfter(gui.messageBox,
				_("Failed to check for updates: {}").format(e),
				_("SmartLingo Updater Error"), wx.OK | wx.ICON_ERROR)

def _clean_release_notes(body):
	"""Clean GitHub markdown into plain readable text for NVDA screen reader."""
	if not body:
		return _("No release notes provided.")
	import re

	# Normalize Windows line endings
	body = body.replace('\r\n', '\n').replace('\r', '\n')

	# Remove fenced code blocks entirely
	body = re.sub(r'```[^\n]*\n.*?```', '[code block]', body, flags=re.DOTALL)

	# Remove inline code backticks - keep text inside
	body = re.sub(r'`([^`]+)`', r'\1', body)

	# Convert [link text](url) - keep only link text
	body = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', body)

	# Remove image syntax ![alt](url) completely
	body = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', body)

	# Remove markdown headings - keep heading text
	body = re.sub(r'^#{1,6}\s*', '', body, flags=re.MULTILINE)

	# Remove bold/italic/strikethrough - keep inner text (triple first, then double, then single)
	body = re.sub(r'\*{3}(.+?)\*{3}', r'\1', body)
	body = re.sub(r'_{3}(.+?)_{3}', r'\1', body)
	body = re.sub(r'\*{2}(.+?)\*{2}', r'\1', body)
	body = re.sub(r'_{2}(.+?)_{2}', r'\1', body)
	body = re.sub(r'\*(.+?)\*', r'\1', body)
	body = re.sub(r'_(.+?)_', r'\1', body)
	body = re.sub(r'~~(.+?)~~', r'\1', body)

	# Remove horizontal rules
	body = re.sub(r'^\s*([-*_])\s*\1\s*\1[\s\1]*$', '', body, flags=re.MULTILINE)

	# Remove HTML tags
	body = re.sub(r'<[^>]+>', '', body)

	# Normalize bullet points to plain "- "
	body = re.sub(r'^\s*[-*+]\s+', '- ', body, flags=re.MULTILINE)

	# Collapse 3+ blank lines into max 2
	body = re.sub(r'\n{3,}', '\n\n', body)

	return body.strip()


def _prompt_update(version, url, release_notes=""):
	"""Show a proper update dialog with version info and What's New section."""
	dlg = _UpdateDialog(
		gui.mainFrame,
		version=version,
		release_notes=release_notes,
		download_url=url
	)
	dlg.ShowModal()
	dlg.Destroy()


class _UpdateDialog(wx.Dialog):
	"""Custom update dialog showing version number and release notes."""

	def __init__(self, parent, version, release_notes, download_url):
		super().__init__(parent, title=_("SmartLingo Update Available"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._download_url = download_url
		self._version = version

		mainSizer = wx.BoxSizer(wx.VERTICAL)

		# Header label
		header = wx.StaticText(self,
			label=_("SmartLingo version {} is available!").format(version))
		font = header.GetFont()
		font.SetWeight(wx.FONTWEIGHT_BOLD)
		font.SetPointSize(font.GetPointSize() + 1)
		header.SetFont(font)
		mainSizer.Add(header, flag=wx.ALL, border=10)

		# What's New label
		mainSizer.Add(
			wx.StaticText(self, label=_("What's new in this version:")),
			flag=wx.LEFT | wx.RIGHT, border=10
		)

		# Release notes text box (read-only, scrollable, screen-reader friendly)
		self._notesCtrl = wx.TextCtrl(
			self,
			value=release_notes if release_notes else _("No release notes available."),
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.HSCROLL
		)
		self._notesCtrl.SetMinSize((480, 220))
		mainSizer.Add(self._notesCtrl, proportion=1,
			flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

		# Separator
		mainSizer.Add(wx.StaticLine(self), flag=wx.EXPAND | wx.ALL, border=8)

		# Buttons
		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		yesBtn = wx.Button(self, label=_("&Download and Install"))
		noBtn = wx.Button(self, id=wx.ID_CANCEL, label=_("&Not Now"))
		yesBtn.Bind(wx.EVT_BUTTON, self._onInstall)
		noBtn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
		btnSizer.Add(yesBtn, flag=wx.RIGHT, border=8)
		btnSizer.Add(noBtn)
		mainSizer.Add(btnSizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)

		self.SetSizer(mainSizer)
		mainSizer.Fit(self)
		self.SetMinSize((500, 380))
		self.Centre()
		# Focus release notes so screen reader reads them immediately
		self._notesCtrl.SetFocus()

	def _onInstall(self, event):
		self.EndModal(wx.ID_OK)
		threading.Thread(
			target=_download_and_install_thread,
			args=(self._download_url, self._version),
			daemon=True
		).start()

def _is_safe_download_url(url):
	"""SECURITY: Ensure download URL is from a trusted GitHub domain only."""
	try:
		import urllib.parse
		parsed = urllib.parse.urlparse(url)
		if parsed.scheme != "https":
			return False
		host = parsed.netloc.lower()
		return any(host == allowed or host.endswith("." + allowed) for allowed in _ALLOWED_DOWNLOAD_HOSTS)
	except Exception:
		return False


def _download_and_install_thread(url, version):
	try:
		# SECURITY: Re-validate URL in download thread (defense in depth)
		if not _is_safe_download_url(url):
			raise ValueError("Download URL is not from a trusted source.")

		temp_dir = tempfile.gettempdir()
		# SECURITY: Sanitize version string — only allow alphanumeric, dots, hyphens
		import re
		safe_version = re.sub(r'[^a-zA-Z0-9._-]', '', version)
		file_name = "SmartLingoPro-{}.nvda-addon".format(safe_version)
		file_path = os.path.join(temp_dir, file_name)

		# SECURITY: Ensure output path stays within temp dir (path traversal guard)
		if not os.path.abspath(file_path).startswith(os.path.abspath(temp_dir)):
			raise ValueError("Path traversal detected in file path.")

		headers = {
			"User-Agent": "NVDA-SmartLingo-Updater",
			"Cache-Control": "no-cache"
		}
		resp = requests.get(url, headers=headers, timeout=30, stream=True)
		resp.raise_for_status()

		# SECURITY: Check Content-Length before downloading
		content_length = resp.headers.get("Content-Length")
		if content_length and int(content_length) > _MAX_DOWNLOAD_SIZE_BYTES:
			raise ValueError("Download file is too large (exceeds 50 MB limit).")

		# SECURITY: Read in chunks and enforce size cap
		data = b""
		for chunk in resp.iter_content(chunk_size=65536):
			if chunk:
				data += chunk
				if len(data) > _MAX_DOWNLOAD_SIZE_BYTES:
					raise ValueError("Download exceeded 50 MB limit. Aborting.")

		# SECURITY: Only write if extension is exactly .nvda-addon
		if not file_path.endswith(".nvda-addon"):
			raise ValueError("Downloaded file is not a valid .nvda-addon file.")

		with open(file_path, 'wb') as out_file:
			out_file.write(data)

		os.startfile(file_path)
	except Exception as e:
		wx.CallAfter(gui.messageBox,
			_("Failed to download update: {}").format(e),
			_("SmartLingo Updater Error"), wx.OK | wx.ICON_ERROR)
