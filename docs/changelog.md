Changelog - SmartLingo Pro
==========================

All notable changes to SmartLingo Pro are documented here.

Version 1.10
------------

New feature:

- Auto-translate clipboard (new setting, off by default): any text you copy is translated right away. Text SmartLingo puts on the clipboard itself is skipped, so it never translates its own output.

Voice input:

- Voice engine rebuilt on a clear state machine. Cancelling during transcription now works, and commands are held off with "Voice input is in progress, please wait." while it runs.
- Silence is trimmed and quiet recordings are boosted, without the audioop module that Python 3.13 removed.
- A recording with no speech is refused instead of being sent to Whisper.
- Whisper is now asked for a verbatim transcript, with sampling at 0 so it stops looping. Mixed Urdu, Hindi or Bengali with English keeps its English words in English.
- Only languages Whisper supports can be selected, so the request is no longer rejected.
- Specific errors for a wrong language, bad key, oversized clip, rate limit and outage, instead of one generic failure.
- Speech timeout raised from 45 to 90 seconds, so long recordings are not cut off.
- Recordings under 0.4 seconds are refused, and recording stops at 5 minutes.
- A microphone buffer overflow is filled with matching silence, so a word is no longer cut in half.
- The start tone plays before the microphone opens, so it never lands in your transcript.

Voice dictation:

- Dictated text is inserted through NVDA's own text interface instead of fake Ctrl+V presses, so the wrong window can no longer jump to the front and a key can no longer stick down.
- If you move somewhere that cannot accept text, the text stays on your clipboard and you are told why.
- Error messages are spoken, never typed into your document.

Settings:

- AI Assistant model (new): choose Groq or Gemini for the chat window. It is completely separate from the translation model, so changing one never affects the other. Groq is the default.
- Spoken language for voice input (new): set the language you actually speak, instead of it being forced to your translation source language. Automatic detection is the default.
- Dictation script: the old "Voice Dictation language" name, now clearer.
- Automatically translate newly copied clipboard text (new, off by default).
- Update check now also repeats every 6 hours, not just at startup.

Translation:

- Groq token limit raised from 1024 to 4096, so long answers are no longer cut off.
- DeepL long text is split on word boundaries, so words no longer run together across chunks.
- The dictation instruction always said "Roman Urdu" even for Hindi, Bengali or Nepali. It now names your language.
- An empty answer now gives a clear message instead of silence.
- Roman script dictation asks for a Groq or Gemini key instead of quietly falling back to Groq.

AI Assistant (open it with NVDA+Alt+Enter):

- The assistant answers instead of translating. It shared the translator's instructions, so it often translated your question instead of answering it. It now has its own instructions and replies in the language you wrote in.
- Chat feels more natural: the reply temperature was raised from 0.1 to 0.6, because at 0.1 the model was too strict and fell back to translating.
- You can pick the assistant's AI separately (Groq or Gemini), with no effect on the translation model.
- If the wrong AI is picked, you get a clear message. Google Translate and DeepL only translate text, they cannot talk.
- Errors now appear in the chat window. It used to get stuck on "SmartLingo is typing..." with the reason only spoken.
- A reply no longer raises the window or takes your focus. The window only comes up if you opened it.
- Copying during a chat no longer clears the conversation. The clipboard watcher stays out of the way while the chat window is open.

Announcements:

- Voice translation says "Recording started for translation...", voice typing says "Recording started for typing...".
- Stopping says "Transcribing..." once, after the tone and the tail of the audio.
- Pressing the same key again during transcription cancels it.
- Translate, chat, swap and settings say "Voice input is in progress, please wait." while voice input runs.

Housekeeping:

- Unused imports removed, and state handling cleaned up in the updater, chat window and settings.
Version 1.9
------------

New feature:

- **DeepL (Free):** Added DeepL as a free translation model. No API key required. Long text is split automatically and auto-detect and auto-swap work with it too.

Voice recognition:

- **Mixed Urdu and English:** English words like WiFi, settings, update and email now stay in English instead of changing into Urdu.
- **Whisper large v3:** Upgraded the speech recognition model for better accuracy.
- **Audio cleanup:** Silent gaps are trimmed and quiet audio is made louder before transcription.
- **Mic overflow:** Buffer overflow is now detected and handled cleanly instead of damaging the audio.

Settings:

- **DeepL (Free)** added to the AI model dropdown.

Version 1.8 - 2026-05-21
-------------------------

New Feature:

- **Google Translate Support:** Added Google Translate as a free translation option. No API key is required for text translation.

Improvements & Stability:

- **Fixed Stability Issues:** Resolved random NVDA freezes and crashes during heavy translation or voice input sessions.
- **Intelligent Cancellation:** Translation requests are now properly cancelled when a new one starts or the user manually cancels (NVDA+Alt+C).
- **Network Resilience:** Added automatic retries with exponential backoff for temporary API or network failures (429, 5xx).
- **Large Text Protection:** Prevents NVDA from hanging when translating very large clipboard content.
- **Zero-Lag Voice Recording:** Optimized audio processing to prevent lag during long recordings.
- **Optimized Memory Usage:** Fixed excessive memory growth during long chat sessions.
- **Improved Chat UI:** Chat window now announces "Response received" instead of speaking the full AI response.
- **Clearer Error Messages:** More descriptive errors for invalid API keys, rate limits, and connection issues.

Notes:

- **Voice Features:** Voice Translation (NVDA+Alt+V) and Voice Dictation (NVDA+Alt+D) still require a Groq API key (Whisper), even if translation is set to Google Translate or Gemini.

Version 1.7 - 2026-05-13
-------------------------

Improvements:

- **Added "Get API Key" Buttons:** The settings panel now features dedicated buttons to quickly open the Groq and Gemini API key dashboards, making setup much faster.
- **Removed OpenAI (ChatGPT) Support:** Support for OpenAI has been removed as their API is no longer free. The addon now focuses on high-quality free providers (Groq and Gemini).
- **Fixed Voice Dictation Roman Urdu Support:** Resolved an issue where voice dictation (NVDA + Alt + D) did not correctly support Roman Urdu script conversion.

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

- Fixed: Voice dictation (NVDA + Alt + D) was not pasting transcribed text into the edit box. Root cause was the NVDA gesture pipeline interfering with the paste gesture — now uses raw Windows API (`ctypes keybd_event`) for a reliable Ctrl+V paste.

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
