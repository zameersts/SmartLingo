# Welcome to SmartLingo Pro! 👋

SmartLingo Pro is your personal, AI-powered translator built right into the NVDA screen reader. 

We built this addon so you wouldn't have to constantly switch windows or juggle different translation websites. With SmartLingo Pro, you can instantly translate any text you've copied, or even just speak into your microphone and have it translated—all without leaving what you're currently doing!

## 🌟 What can it do?

- **Instant Translations:** Just copy some text, press a hotkey, and get an instant AI translation read out to you.
- **Speak to Translate:** Press a hotkey, speak into your microphone, and we'll translate your voice!
- **Smart Language Detection:** You don't even need to tell it what language you're copying—it'll figure it out automatically.
- **Quick Language Swap:** Easily switch between the language you're translating *from* and the one you're translating *to*. It even does this automatically if it detects you're already reading in your target language!
- **Standalone AI Assistant:** SmartLingo is now your personal AI companion. Open the chat window anytime to ask questions, write content, or refine translations with full conversation context.
- **Auto-Copy:** As soon as a translation is ready, we copy it to your clipboard so you can paste it anywhere.
- **Automatic Updates:** Don't worry about missing new features! SmartLingo checks for new versions on GitHub and updates itself.
- **Pick your AI:** You're not locked into one system. Choose between Google Gemini, OpenAI, or Groq based on what you prefer.

## 🛠️ What do you need to use it?

It's pretty simple to get started, but you will need a couple of things:
1. **NVDA Screen Reader** (version 2024.1 or newer).
2. **Windows 10** or a newer version.
3. **An API Key:** This is basically a password that lets the addon talk to the AI. You can get one for free:
   - **Groq** (Fast and completely free): [Get it here](https://console.groq.com)
   - **Google Gemini** (Has a great free tier): [Get it here](https://aistudio.google.com)
   - **OpenAI** (Paid, but very powerful): [Get it here](https://platform.openai.com)
4. *(Optional but recommended)* A microphone for voice input. The addon will help you install "PyAudio" the first time you try to use your voice.

## 🚀 How to Install

1. Grab the `SmartLingo.nvda-addon` file from our Releases page.
2. Just double-click the file! NVDA will handle the rest.
3. When NVDA asks, let it restart.
4. Once NVDA is back up, go to **NVDA Menu > Preferences > Settings**, find **SmartLingo Pro** in the list, and paste in your API key.

## ⌨️ Important Keyboard Shortcuts

We've tried to make the shortcuts as easy to remember as possible:

- **NVDA + Alt + T** : Translate whatever text you currently have copied.
- **NVDA + Alt + V** : Start/Stop recording your voice for translation.
- **NVDA + Alt + C** : Cancel an ongoing voice recording or translation. Says "Nothing to cancel" if idle.
- **NVDA + Alt + S** : Swap your source and target languages around.
- **NVDA + Alt + A** : Check what languages you are currently translating between.
- **NVDA + Alt + L** : Jump straight into the SmartLingo settings.
- **NVDA + Alt + Enter** : Open the Standalone AI Assistant chat window.

## ⚙️ Customizing SmartLingo

You can tweak how SmartLingo works by going to **NVDA Settings > SmartLingo Pro**. Here's what you can change:

- **AI Model & API Key:** Choose which AI brain you want to use and give it the key.
- **Languages:** Set what language you usually translate from (or leave it on Auto-detect) and what language you want things translated into.
- **Auto-Swap:** If you have this turned on and you try to translate something that's *already* in your target language, SmartLingo will be smart enough to flip the languages around for you!
- **Auto-copy:** Decide if you want every translation to be automatically copied to your clipboard.

## 🎤 Using Your Voice

Want to just talk? It's easy!
- Press **NVDA + Alt + V**, say what you want to translate, and press the shortcut again to stop.
- Note: Voice input requires a Groq or OpenAI API key. Gemini does not support speech recognition.
- The first time you use voice, ensure PyAudio is available (included with the addon).

## 🙌 Credits & Thanks

- This addon was brought to life with the help of AI (Google Gemini).
- Inspired by amazing addons like Instant Translator.
- Idea, design, and testing by Zameer.

---
*Note: SmartLingo Pro is open-source software licensed under the GNU General Public License v2.0.*
