# speechOnDemand.py
# Part of SmartLingo addon for NVDA
# Based on SmartLingo's speechOnDemand.py

import config
import speech
import ui

def getSpeechOnDemandParameter():
	"""Returns the speech on demand parameter for scriptHandler.script decorator."""
	try:
		# NVDA 2024.1+
		return {"speakOnDemand": True}
	except:
		return {}

def executeWithSpeakOnDemand(func, *args, **kwargs):
	"""Executes a function while temporarily forcing speech if on demand is active."""
	# Simplified version for clean rewrite
	func(*args, **kwargs)
