Changelog - SmartLingo Pro
==========================

All notable changes to SmartLingo Pro are documented here.


Version 1.6 - 2026-05-10
-------------------------

Major Features:

- **Standalone AI Assistant:** SmartLingo is now more than just a translator! You can now open a dedicated AI Assistant window anytime to chat, ask questions, or brainstorm ideas.
- **New Shortcut (NVDA + Alt + Enter):** Instantly open the AI Assistant window from anywhere.
- **Conversational History (Memory):** The AI now maintains context. You can ask follow-up questions and hold a continuous conversation, and the AI will remember the previous messages in the current session.
- **Improved Chat UI/UX:**
  - Removed the "Enable Chat Window" checkbox from settings; the Assistant is now purely shortcut-driven.
  - Added "SmartLingo is typing..." status indicator (visual and spoken by NVDA).
  - Initial focus now lands on the input field for immediate typing.
  - Added support for `Shift + Enter` to start new lines within the chat.
  - Enhanced accessibility labels and focus management for a smoother NVDA experience.
- **Context-Aware Prompting:** The AI now intelligently switches between strict translation mode and conversational assistant mode based on how the chat was initiated.

Version 1.5 - 2026-05-08

Improvements:

- Improved Auto-Swap Logic: Refactored the AI system prompt to handle bidirectional language swapping (Target to Swap and Swap to Target) for better accuracy, especially for Urdu and Hindi.
- Optimized Prompts: Added bidirectional Urdu translation examples to the AI backend to ensure consistent translation and prevent the AI from getting 'stuck' in one language.

Bug Fixes & Security:

- Fixed: Resolved an issue where some users experienced `SSL: CERTIFICATE_VERIFY_FAILED` errors during auto-updates. The updater now utilizes the `requests` library and its bundled CA certificates (`certifi`) instead of relying on the local Windows certificate store, ensuring secure and reliable updates for all users.

Version 1.4 - 2026-05-06
-------------------------

Improvements & Cleanup:

- Code Cleanup: Removed unused imports (`json`, `ssl`, `config`, `keyboardHandler`), removed unused `finally_` method, and cleaned up unused `use_mirror` parameters to keep the codebase lightweight and highly optimized.
- Confirmed that "Keep-Alive" HTTP connections (`requests.Session()`) are highly secure and optimized, causing no token leaks while ensuring maximum speed (Zero Latency Mode).
- Re-compiled to integrate all changes cleanly for NVDA 2026.1 (Python 3.13) compatibility.

Version 1.3 - 2026-05-06
-------------------------

Bug Fixes:

- Fixed: Voice dictation (NVDA + Alt + D) was not pasting transcribed text into the edit box. Root cause: wx.CallAfter(gesture.send) was unreliable — gesture ran outside NVDA's main event thread. Now correctly uses wx.CallLater(150ms) + queueHandler to ensure clipboard is ready before Ctrl+V is sent.

Improvements:

- Translations have been significantly improved.
- Added Voice Typing (Dictation) feature: Type directly into edit boxes using voice without AI translation (NVDA + Alt + D).
- Improved Update Dialog: When a new version is available, the addon now shows a dedicated dialog with the full "What's New" release notes from GitHub, so users know exactly what changed before installing.

Security:

- Enforced SSL certificate validation (verify=True) on all API requests (Groq, Gemini, OpenAI).
- Update downloader now validates that the download URL is from a trusted GitHub domain only.
- Added protection against path traversal and version string injection in the updater.
- Added 10 MB audio recording cap to prevent memory exhaustion.
- Added 50 MB download cap to prevent oversized update file attacks.


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
- **Auto-copy:** Decide if you want every translation to be automatically copied to your clipboard.
- NVDA Settings Panel: Fully integrated settings (NVDA + Alt + L)
- Language Announcement: Announce current language pair (NVDA + Alt + A)
- Automatic Updater: Check for new releases directly from GitHub on startup or manually from settings


SmartLingo Pro - Idea and Testing by Zameer | Code written with AI assistance
