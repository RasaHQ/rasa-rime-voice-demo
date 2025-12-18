<div align="center">

<h3 align="center">
  <picture>
    <img alt="Rasa Banner" src="https://github.com/RasaHQ/.github/blob/readme/update-hello-rasa-community/assets/banner-rasa-1200x300.png?raw=true">
  </picture>
</h3>

# 🎁 Unwrap the Future: Voice Orchestration

### A low-latency voice assistant architecture orchestrating Rasa, Rime, and Deepgram.

[![Hello Rasa](https://img.shields.io/badge/Start_Building-Hello_Rasa-ff69b4?style=for-the-badge)](https://hello.rasa.ai/?utm_source=github&utm_medium=website&utm_campaign=unwrap_voice)
[![Join Community](https://img.shields.io/badge/Join_Community-Agent_Engineering-blueviolet?style=for-the-badge)](https://info.rasa.com/community?utm_source=github&utm_medium=website&utm_campaign=unwrap_voice)
[![Rasa Docs](https://img.shields.io/badge/Read_Docs-Rasa_Platform-000000?style=for-the-badge)](https://rasa.com/docs/?utm_campaign=unwrap_voice&utm_source=github&utm_content=rasa_docs)

<p align="center">
  This repository demonstrates an ultra-low latency architecture that orchestrates <b>Rasa Pro</b> (Agent), <b>Rime</b> (TTS), and <b>Deepgram</b> (ASR). It features a custom Python orchestrator, a real-time rich CLI dashboard, and CALM-based banking logic to achieve sub-second, human-like conversational turns.
</p>

</div>

---

## 🚀 The Architecture

We achieve fluid, human-like voice interaction by orchestrating best-in-class specialized services rather than using a monolithic black box.



1.  **Input:** User Audio (Simulated via Rime "Abbie" voice).
2.  **ASR (Ears):** **Deepgram Nova-2** for lightning-fast speech-to-text.
3.  **Brain:** **Rasa Pro** executes deterministic business logic (CALM) to ensure secure money transfers.
4.  **TTS (Voice):** **Rime Mist v2** generates high-fidelity agent audio with <300ms latency.
5.  **Orchestrator:** A custom Python client manages the real-time traffic to ensure immediate playback.

---

## 🛠️ Setup & Usage

### Prerequisites
* Python 3.10+
* [`uv`](https://github.com/astral-sh/uv) (for fast dependency management)

### 1. Installation
Install all dependencies into a strictly versioned virtual environment:
```bash
make install

```

### 2. Configuration

Create a `.env` file with your credentials:

```env
# Required for Rasa Pro
RASA_LICENSE=your-rasa-pro-license-key-here

# Required for NLU/Reasoning
OPENAI_API_KEY=your-openai-api-key-here

# Required for the Voice Demo
DEEPGRAM_API_KEY=your-deepgram-api-key-here
RIME_API_KEY=your-rime-api-key-here

```

### 3. Generate Audio Assets

Instead of using a live microphone (which is risky for demos), we pre-generate high-quality user prompts using Rime:

```bash
make generate-audio

```

### 4. Train the Brain

Train the Rasa CALM model to handle the banking logic:

```bash
make train

```

---

## 🎤 Run the Flash Talk Demo

To run the full orchestration, open **3 separate terminal tabs**:

**Tab 1: The Action Server** (Handles custom business logic)

```bash
make run-actions

```

**Tab 2: The Agent** (Rasa Pro Core)

```bash
make run-rasa

```

**Tab 3: The Live Client** (The Orchestrator & Visual Dashboard)

```bash
make demo

```

*You will see a rich CLI dashboard and hear the conversation flow between the User and the Agent in real-time.*

---

<br />

## 🚀 Two Ways to Get Started with Rasa

| **🤖 Start Building** | **🧠 Join the Conversation** |
| --- | --- |
| **[Try Hello Rasa](https://www.google.com/url?sa=E&source=gmail&q=https://hello.rasa.ai/?utm_source=github%26utm_medium=website%26utm_campaign=unwrap_voice)** | **[Agent Engineering Community](https://www.google.com/url?sa=E&source=gmail&q=https://info.rasa.com/community?utm_source=github%26utm_medium=website%26utm_campaign=unwrap_voice)** |
| The fastest way to prototype. An interactive playground to build **CALM** agents in your browser.<br>

<br>

<br>✨ **No setup required**<br>

<br>✨ **No NLU training needed**<br>

<br>✨ **Built-in Copilot** | The home for people building real-world AI agents. A vendor-neutral space to discuss architectures, memory, and orchestration.<br>

<br>

<br>🤝 **Meet other builders**<br>

<br>🛠️ **Share agent patterns**<br>

<br>🎓 **Learn from the best** |

<br />

<div align="center">

### Connect with us

[<img src="https://img.shields.io/badge/YouTube-Rasa-red?style=flat-square&logo=youtube" width="100"/>](https://www.google.com/search?q=https://www.youtube.com/%40RasaHQ%3Futm_campaign%3Dunwrap_voice%26utm_source%3Dgithub)
[<img src="https://img.shields.io/badge/LinkedIn-Rasa-blue?style=flat-square&logo=linkedin" width="100"/>](https://www.google.com/search?q=https://www.linkedin.com/company/rasa/%3Futm_campaign%3Dunwrap_voice%26utm_source%3Dgithub)
[<img src="https://img.shields.io/badge/Forum-Rasa_Community-brightgreen?style=flat-square&logo=discourse" width="130"/>](https://www.google.com/search?q=https://forum.rasa.com/%3Futm_campaign%3Dunwrap_voice%26utm_source%3Dgithub)

</div>