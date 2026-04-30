Changelog - SmartLingo Pro
==========================

All notable changes to SmartLingo Pro are documented here.


Version 1.2 - 2026-04-30
-------------------------

Bug Fixes:

- Fixed: Language dropdown in settings was not showing correct language names due to a bug in prepareChoices() function
- Fixed: Settings panel now correctly saves and restores selected languages using proper display name to language code mapping
- Fixed: SSL certificate verification was disabled in the updater (security risk) — now uses system trusted certificates
- Fixed: Version comparison in updater now correctly handles formats like "v1.10-beta" and multi-part version numbers
- Fixed: Voice input now shows a clear error message when only a Gemini API key is provided, since Gemini does not support speech recognition (STT requires Groq or OpenAI)
- Fixed: PyAudio stream overflow no longer causes a crash during voice recording
- Fixed: Update checker and downloader threads are now properly daemonized so they don't block NVDA on exit
- Fixed: Misleading error message "Gemini transcription" removed from readme (Gemini does not support STT)
- Fixed: NVDA+Alt+C (Cancel) was working even when nothing was recording or translating — now correctly says "Nothing to cancel" if idle


Version 1.1 - 2026-04-29
-------------------------

- Added Cancel Feature: Cancel ongoing voice recordings or translations (NVDA + Alt + C)


Version 1.0 - 2026-04-28
-------------------------

Initial Release

- Clipboard Translation: Translate any copied text using AI (NVDA + Alt + T)
- Multi-Provider Support: Groq (llama-3.3-70b), Gemini (2.0 Flash), OpenAI (gpt-4o-mini)
- Auto Language Detection: Detects source language automatically
- Language Swap: Switch source and target languages (NVDA + Alt + S)
- Auto-Swap: Automatically swaps when detected language matches target
- Voice Input: Record and translate speech using microphone (NVDA + Alt + V)
  - Supports Groq Whisper and OpenAI Whisper for speech recognition
- Chat Window Mode: Conversational translation interface
- Auto-Copy: Translation result copied to clipboard automatically
- NVDA Settings Panel: Fully integrated settings (NVDA + Alt + L)
- Language Announcement: Announce current language pair (NVDA + Alt + A)
- Automatic Updater: Check for new releases directly from GitHub on startup or manually from settings


SmartLingo Pro - Idea and Testing by Zameer | Code written with AI assistance
