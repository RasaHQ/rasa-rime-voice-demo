# 🎁 Unwrap the Future: Voice Orchestration

A minimal, low-latency voice assistant architecture demonstrating the power of **Rasa (Orchestration)** + **Rime (TTS)** + **Deepgram (ASR)**.

## 🚀 The Architecture


1.  **Input:** User Audio (Simulated)
2.  **ASR:** Deepgram Nova-2 (Speech-to-Text)
3.  **Brain:** Rasa Pro (NLU + Dialogue Management)
4.  **TTS:** Rime Mist v2 (Ultra-low latency Text-to-Speech)

## 🛠️ Setup

Prerequisites: Python 3.10+, `uv` installed.

1.  **Install Dependencies:**
    ```bash
    make install
    ```

2.  **Configure Credentials:**
    Create a `.env` file with:
    ```env
    RASA_LICENSE=...
    DEEPGRAM_API_KEY=...
    RIME_API_KEY=...
    OPENAI_API_KEY=...
    ```

3.  **Train the Agent:**
    ```bash
    make train
    ```

4.  **Generate Audio Assets:**
    ```bash
    make generate-audio
    ```

## 🎤 Run the Flash Talk Demo

Open 3 terminal tabs:

**Tab 1 (Action Server):**
```bash
make run-actions

```

**Tab 2 (Rasa Core):**

```bash
make run-rasa

```

**Tab 3 (The Visual Client):**

```bash
make demo

```