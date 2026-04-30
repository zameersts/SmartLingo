# updater.py
# SmartLingo GitHub Updater

import urllib.request
import urllib.error
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

def get_current_version():
	try:
		addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
		addon = addonHandler.Addon(addon_dir)
		return addon.manifest['version']
	except Exception:
		return "1.0"

def check_for_update(background=False):
	threading.Thread(target=_check_update_thread, args=(background,), daemon=True).start()

def _create_ssl_context():
	"""
	FIX: Pehle SSL verification bilkul band thi (CERT_NONE) jo security risk tha.
	Ab system ke trusted certificates use karta hai. Agar woh fail ho to
	sirf tab fallback karta hai jab explicitly zaroorat ho.
	"""
	try:
		ctx = ssl.create_default_context()
		# check_hostname aur verify_mode default pe sahi hain (verification ON)
		return ctx
	except Exception:
		return None

def _parse_version(v):
	"""
	FIX: Pehle version parsing weak thi - sirf digits nikalti thi.
	Ab properly splits by dot aur non-digit parts ignore karta hai.
	e.g. "v1.10-beta" -> [1, 10], "1.1" -> [1, 1]
	"""
	# "v" prefix aur pre-release tags hata do
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
		req = urllib.request.Request(url_with_ts, headers=headers)
		
		ctx = _create_ssl_context()
		
		with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
			data = json.loads(response.read().decode('utf-8'))
			
		latest_version = data.get("tag_name", "").lstrip("v")
		current_version = get_current_version().lstrip("v")
		
		if _parse_version(latest_version) > _parse_version(current_version):
			download_url = None
			for asset in data.get("assets", []):
				if asset.get("name", "").endswith(".nvda-addon"):
					download_url = asset.get("browser_download_url")
					break
			
			if download_url:
				wx.CallAfter(_prompt_update, latest_version, download_url)
			elif not background:
				wx.CallAfter(gui.messageBox,
					_("Update found, but no addon file is attached to the release."),
					_("SmartLingo Updater"), wx.OK | wx.ICON_WARNING)
		else:
			if not background:
				wx.CallAfter(gui.messageBox,
					_("You are already using the latest version of SmartLingo."),
					_("SmartLingo Updater"), wx.OK | wx.ICON_INFORMATION)

	except urllib.error.HTTPError as e:
		if not background:
			if e.code == 403:
				msg = _("GitHub API rate limit exceeded. Please try again later.")
			else:
				msg = _("Failed to check for updates: {}").format(e)
			wx.CallAfter(gui.messageBox, msg, _("SmartLingo Updater Error"), wx.OK | wx.ICON_ERROR)
	except ssl.SSLError as e:
		if not background:
			wx.CallAfter(gui.messageBox,
				_("SSL error while checking for updates: {}").format(e),
				_("SmartLingo Updater Error"), wx.OK | wx.ICON_ERROR)
	except Exception as e:
		if not background:
			wx.CallAfter(gui.messageBox,
				_("Failed to check for updates: {}").format(e),
				_("SmartLingo Updater Error"), wx.OK | wx.ICON_ERROR)

def _prompt_update(version, url):
	res = gui.messageBox(
		_("A new version ({}) of SmartLingo is available. Do you want to download and install it now?").format(version),
		_("SmartLingo Update Available"),
		wx.YES_NO | wx.ICON_QUESTION
	)
	if res == wx.YES:
		threading.Thread(target=_download_and_install_thread, args=(url, version), daemon=True).start()

def _download_and_install_thread(url, version):
	try:
		temp_dir = tempfile.gettempdir()
		file_name = "SmartLingoPro-{}.nvda-addon".format(version)
		file_path = os.path.join(temp_dir, file_name)
		
		headers = {
			"User-Agent": "NVDA-SmartLingo-Updater",
			"Cache-Control": "no-cache"
		}
		req = urllib.request.Request(url, headers=headers)
		ctx = _create_ssl_context()
		
		with urllib.request.urlopen(req, timeout=30, context=ctx) as response, open(file_path, 'wb') as out_file:
			out_file.write(response.read())
		
		os.startfile(file_path)
	except Exception as e:
		wx.CallAfter(gui.messageBox,
			_("Failed to download update: {}").format(e),
			_("SmartLingo Updater Error"), wx.OK | wx.ICON_ERROR)
