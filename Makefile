# ==============================================================================
# 🎨 Terminal Colors & UI
# ==============================================================================
GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
BLUE   := $(shell tput -Txterm setaf 4)
MAGENTA:= $(shell tput -Txterm setaf 5)
RESET  := $(shell tput -Txterm sgr0)

# ==============================================================================
# 🛠️ Path & Environment Configuration
# ==============================================================================
# We use the local directory (.) because this recipe is self-contained
VENV_NAME := .venv
PYTHON    := ./$(VENV_NAME)/bin/python
RASA      := $(PYTHON) -m rasa
UV        := $(shell which uv)

# Ensure .env is loaded for make commands if needed
ifneq (,$(wildcard .env))
    include .env
    export
endif

.DEFAULT_GOAL := help

# ==============================================================================
# 📖 Help & Instructions
# ==============================================================================
help: ## Show this help message
	@echo ''
	@echo '${MAGENTA}🎁 Unwrap the Future: Rasa + Rime + Deepgram Demo${RESET}'
	@echo ''
	@echo '${YELLOW}Setup:${RESET}'
	@echo '  ${GREEN}make install${RESET}         - Install dependencies into .venv using uv'
	@echo '  ${GREEN}make generate-audio${RESET}  - Generate the "User Voice" files using Rime'
	@echo ''
	@echo '${YELLOW}Live Stage Commands (Run in 3 separate tabs):${RESET}'
	@echo '  ${GREEN}make run-actions${RESET}     - Tab 1: Start Action Server'
	@echo '  ${GREEN}make run-rasa${RESET}        - Tab 2: Start Rasa Agent'
	@echo '  ${GREEN}make demo${RESET}            - Tab 3: Run the Live Client'
	@echo ''

# ==============================================================================
# 🚀 Setup & Prep
# ==============================================================================
.PHONY: check-uv
check-uv:
	@if [ -z "$(UV)" ]; then echo "${RED}uv not found. Please install uv.${RESET}"; exit 1; fi

.PHONY: install
install: check-uv ## Install dependencies into .venv
	@echo "${BLUE}Creating virtual environment and installing dependencies...${RESET}"
	$(UV) venv $(VENV_NAME)
	$(UV) pip install pip setuptools
	$(UV) pip install -e .
	@echo "${BLUE}Downloading Spacy model...${RESET}"
	$(PYTHON) -m spacy download en_core_web_md
	@echo "${GREEN}✓ Setup complete.${RESET}"

.PHONY: generate-audio
generate-audio: ## Generate static user audio files for the demo
	@echo "${BLUE}Generating user audio prompts via Rime...${RESET}"
	$(PYTHON) scripts/generate_user_audio.py
	@echo "${GREEN}✓ Audio generation complete.${RESET}"

.PHONY: train
train: ## Train the Rasa model
	@echo "${BLUE}Training Rasa model...${RESET}"
	$(RASA) train
	@echo "${GREEN}✓ Training complete.${RESET}"

# ==============================================================================
# 🎤 Live Demo Execution
# ==============================================================================
.PHONY: run-actions
run-actions: ## Tab 1: Start the Action Server
	@echo "${MAGENTA}Starting Action Server...${RESET}"
	$(RASA) run actions

.PHONY: run-rasa
run-rasa: ## Tab 2: Start the Rasa Server
	@echo "${MAGENTA}Starting Rasa Core...${RESET}"
	$(RASA) run --enable-api --cors "*" --debug

.PHONY: demo
demo: ## Tab 3: Run the Visual Client
	@echo "${MAGENTA}Starting Live Voice Client...${RESET}"
	$(PYTHON) demo_live.py

.PHONY: clean
clean: ## Clean up temporary files
	rm -rf .rasa models results tests/audio_responses
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete