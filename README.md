# Welcome to SmartLingo Pro! 👋

SmartLingo Pro is your personal, AI-powered translator built right into the NVDA screen reader.

We built this addon so you wouldn't have to constantly switch windows or juggle different translation websites. With SmartLingo Pro, you can instantly translate any text you've copied, or even just speak into your microphone and have it translated—all without leaving what you're currently doing!

## 🌟 What can it do?

- **Instant Translations:** Just copy some text, press a hotkey, and get an instant AI translation read out to you.
- **Speak to Translate:** Press a hotkey, speak into your microphone, and we'll translate your voice!
- **Smart Language Detection:** You don't even need to tell it what language you're copying—it'll figure it out automatically.
- **Quick Language Swap:** Easily switch between the language you're translating *from* and the one you're translating *to*. It even does this automatically if it detects you're already reading in your target language!
- **Standalone AI Assistant:** SmartLingo is now your personal AI companion. Open the chat window anytime to ask questions, brainstorm ideas, or hold a natural conversation with full context.
- **Auto-Copy:** As soon as a translation is ready, we copy it to your clipboard so you can paste it anywhere.
- **Automatic Updates:** Don't worry about missing new features! SmartLingo checks for new versions on GitHub and updates itself.
- **Pick your AI:** You're not locked into one system. Choose between Google Gemini, Groq, or Google Translate based on what you prefer (Google Translate does not require an API key for text translation).

## 🛠️ What do you need to use it?

It's pretty simple to get started, but you will need a couple of things:

1. **NVDA Screen Reader** (version 2024.1 or newer).
2. **Windows 10** or a newer version.
3. **An API Key:** This is basically a password that lets the addon talk to the AI. You can get one for free from [Groq](https://console.groq.com) or [Google AI Studio](https://aistudio.google.com) (Gemini). *(Note: If you use the built-in Google Translate model, you do not need any API key for text translation. However, voice features will still require a Groq API key.)*
4. *(Optional)* A microphone for voice input. Note: Voice input requires a Groq API key. Gemini and Google Translate do not support speech recognition (STT) natively in this addon.

## 🚀 How to Install

1. Grab the `SmartLingo-1.8.nvda-addon` file from our [Releases page](https://github.com/zameersts/SmartLingo/releases).
2. Just double-click the file! NVDA will handle the rest.
3. When NVDA asks, let it restart.
4. Once NVDA is back up, go to **NVDA Menu > Preferences > Settings**, find **SmartLingo Pro** in the list, and paste in your API key.

## ⌨️ Important Keyboard Shortcuts

We've tried to make the shortcuts as easy to remember as possible:

| Shortcut | What it does |
|---|---|
| **NVDA + Alt + T** | Translate whatever text you currently have copied. |
| **NVDA + Alt + V** | Start/Stop recording your voice for translation. |
| **NVDA + Alt + D** | Start/Stop voice typing (dictation) directly into an edit box without translation. |
| **NVDA + Alt + C** | Cancel an ongoing voice recording or translation. Says "Nothing to cancel" if idle. |
| **NVDA + Alt + S** | Swap your source and target languages around. |
| **NVDA + Alt + A** | Check what languages you are currently translating between. |
| **NVDA + Alt + L** | Jump straight into the SmartLingo settings. |
| **NVDA + Alt + Enter** | Open the Standalone AI Assistant chat window for a natural conversation. |

## ⚙️ Customizing SmartLingo

You can tweak how SmartLingo works by going to **NVDA Settings > SmartLingo Pro**. Here's what you can change:

- **AI Model & API Key:** Choose which AI brain you want to use and give it the key.
- **Languages:** Set what language you usually translate from (or leave it on Auto-detect) and what language you want things translated into.
- **Auto-Swap & Language for swapping:** If you try to translate something that's *already* in your target language, SmartLingo will be smart enough to flip the languages around for you!
- **Auto-copy:** Decide if you want every translation to be automatically copied to your clipboard.

## 🎤 Using Your Voice

Want to just talk? It's easy!

- Press **NVDA + Alt + V**, say what you want to translate, and press the shortcut again to stop.
- For voice typing (dictation) without translation, press **NVDA + Alt + D** to type directly into an active edit box.
- To cancel at any time, press **NVDA + Alt + C**.
- **Important:** Voice input (both voice translation and dictation) requires a **Groq API key** to function. This is because speech-to-text is handled by Groq's Whisper API. Gemini and Google Translate do not support speech-to-text natively in the addon. You must provide a Groq API key in the settings to use voice features, even if your translation model is set to Gemini or Google Translate.
- PyAudio is included with the addon and does not need to be installed separately.

## 🆕 What's New

### Version 1.8 (2026-05-21)

- **Free Google Translate:** Added Google Translate as a free translation option. No API key is required for text translation.
- **More Stable:** Fixed random freezes and crashes during heavy use.
- **Smarter Cancel & Retries:** Requests cancel properly and automatically retry on temporary network errors.
- **Large Text Safe:** Very large clipboard text no longer hangs NVDA.
- **Optimized Memory:** Fixed excessive memory growth during long chat sessions.
- **Improved Chat UI:** Chat window now announces "Response received" instead of speaking the full AI response.
- **Zero-Lag Voice Recording:** Optimized audio processing to prevent lag during long recordings.
- **Clearer Error Messages:** More descriptive errors for invalid API keys, rate limits, and connection issues.
- **Note:** Voice input still needs a free Groq API key (Google Translate doesn't do speech recognition).

### Version 1.7 (2026-05-13)

- **Get API Key Buttons:** Added convenient buttons in the settings panel to quickly open the websites for Groq and Gemini API keys.
- **Removed OpenAI:** Removed ChatGPT/OpenAI support as it is no longer free.
- **Fixed Voice Dictation:** Resolved an issue where voice dictation did not correctly support Roman Urdu script conversion.

## 📜 Changelog

See the full [changelog](docs/changelog.md) for every version (1.0 to 1.8).

## 🙌 Credits & Thanks

- This addon was brought to life with the help of AI (Google Gemini).
- Inspired by amazing addons like Instant Translator.
- Idea, design, and testing by Zameer.

---

*Note: SmartLingo Pro is open-source software licensed under the GNU General Public License v2.0.*