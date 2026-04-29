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
	threading.Thread(target=_check_update_thread, args=(background,)).start()

def _create_ssl_context():
	try:
		ctx = ssl.create_default_context()
		ctx.check_hostname = False
		ctx.verify_mode = ssl.CERT_NONE
		return ctx
	except Exception:
		return None

def _check_update_thread(background):
	try:
		# Timestamp add kiya gaya taake cache ka issue na aye
		url_with_ts = f"{LATEST_RELEASE_URL}?ts={int(time.time())}"
		headers = {
			"User-Agent": "NVDA-SmartLingo-Updater",
			"Cache-Control": "no-cache",
			"Pragma": "no-cache"
		}
		req = urllib.request.Request(url_with_ts, headers=headers)
		
		# Unverified context use karein taake SSL certificate error na aye
		ctx = _create_ssl_context()
		
		with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
			data = json.loads(response.read().decode('utf-8'))
			
		latest_version = data.get("tag_name", "").lstrip("v")
		current_version = get_current_version().lstrip("v")
		
		# Simple version comparison
		def parse_version(v):
			# Extract digits and split by dot
			return [int(x) for x in ''.join(c if c.isdigit() or c == '.' else '' for c in v).split(".") if x.isdigit()]
			
		if parse_version(latest_version) > parse_version(current_version):
			download_url = None
			for asset in data.get("assets", []):
				if asset.get("name", "").endswith(".nvda-addon"):
					download_url = asset.get("browser_download_url")
					break
			
			if download_url:
				wx.CallAfter(_prompt_update, latest_version, download_url)
			elif not background:
				wx.CallAfter(gui.messageBox, _("Update found, but no addon file is attached to the release."), _("SmartLingo Updater"), wx.OK | wx.ICON_WARNING)
		else:
			if not background:
				wx.CallAfter(gui.messageBox, _("You are already using the latest version of SmartLingo."), _("SmartLingo Updater"), wx.OK | wx.ICON_INFORMATION)
	except urllib.error.HTTPError as e:
		if e.code == 403 and 'rate limit' in str(e.reason).lower():
			if not background:
				wx.CallAfter(gui.messageBox, _("GitHub API rate limit exceeded. Please try again later."), _("SmartLingo Updater Error"), wx.OK | wx.ICON_ERROR)
		else:
			if not background:
				wx.CallAfter(gui.messageBox, _("Failed to check for updates: {}").format(e), _("SmartLingo Updater Error"), wx.OK | wx.ICON_ERROR)
	except Exception as e:
		if not background:
			wx.CallAfter(gui.messageBox, _("Failed to check for updates: {}").format(e), _("SmartLingo Updater Error"), wx.OK | wx.ICON_ERROR)

def _prompt_update(version, url):
	res = gui.messageBox(
		_("A new version ({}) of SmartLingo is available. Do you want to download and install it now?").format(version),
		_("SmartLingo Update Available"),
		wx.YES_NO | wx.ICON_QUESTION
	)
	if res == wx.YES:
		threading.Thread(target=_download_and_install_thread, args=(url, version)).start()

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
		
		# Open the downloaded file to trigger NVDA's addon installation dialog
		os.startfile(file_path)
	except Exception as e:
		wx.CallAfter(gui.messageBox, _("Failed to download update: {}").format(e), _("SmartLingo Updater Error"), wx.OK | wx.ICON_ERROR)
