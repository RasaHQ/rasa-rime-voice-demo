# ==============================================================================
# 🎨 Terminal Colors & UI
# ==============================================================================
GREEN   := $(shell tput -Txterm setaf 2)
YELLOW  := $(shell tput -Txterm setaf 3)
BLUE    := $(shell tput -Txterm setaf 4)
MAGENTA := $(shell tput -Txterm setaf 5)
RED     := $(shell tput -Txterm setaf 1)
RESET   := $(shell tput -Txterm sgr0)

# ==============================================================================
# 🛠️ Path & Environment Configuration
# ==============================================================================
VENV_NAME := .venv
PYTHON    := ./$(VENV_NAME)/bin/python
RASA      := $(PYTHON) -m rasa
UV        := $(shell which uv)

ifneq (,$(wildcard .env))
    include .env
    export
endif

.DEFAULT_GOAL := help

# ==============================================================================
# 📖 Help
# ==============================================================================
.PHONY: help
help: ## Show this help message
	@echo ''
	@echo '$(MAGENTA)🎁 Unwrap the Future: Rasa + Rime + Deepgram$(RESET)'
	@echo ''
	@echo '$(YELLOW)First-time setup:$(RESET)'
	@echo '  $(GREEN)make install$(RESET)          Install dependencies into .venv'
	@echo '  $(GREEN)make generate-audio$(RESET)   Generate the user voice audio files (requires RIME_API_KEY)'
	@echo '  $(GREEN)make train$(RESET)             Train the Rasa dialogue model'
	@echo ''
	@echo '$(YELLOW)Diagnostics:$(RESET)'
	@echo '  $(GREEN)make verify$(RESET)            Pre-flight check: API keys, services, audio files'
	@echo ''
	@echo '$(YELLOW)Run the demo (3 separate terminals):$(RESET)'
	@echo '  $(GREEN)make run-actions$(RESET)       Tab 1 — Start the Action Server'
	@echo '  $(GREEN)make run-rasa$(RESET)           Tab 2 — Start the Rasa Agent'
	@echo '  $(GREEN)make demo$(RESET)               Tab 3 — Run the Live Orchestrator'
	@echo ''
	@echo '$(YELLOW)Development:$(RESET)'
	@echo '  $(GREEN)make test$(RESET)              Run the test suite (unit + integration)'
	@echo '  $(GREEN)make test-unit$(RESET)         Run unit tests only (no live services needed)'
	@echo '  $(GREEN)make inspect$(RESET)           Interactive Rasa shell for manual testing'
	@echo '  $(GREEN)make clean$(RESET)             Remove build artefacts and generated audio'
	@echo ''
	@echo '$(YELLOW)Tooling:$(RESET)'
	@echo '  $(GREEN)make annotate$(RESET)          Add/update QV-LLM header blocks'
	@echo '  $(GREEN)make flatten$(RESET)           Flatten repo into a single text bundle'
	@echo ''

# ==============================================================================
# 🚀 Setup
# ==============================================================================
.PHONY: check-uv
check-uv:
	@if [ -z "$(UV)" ]; then \
		echo "$(RED)✗ uv not found. Install it from https://github.com/astral-sh/uv$(RESET)"; \
		exit 1; \
	fi

.PHONY: install
install: check-uv ## Install all dependencies into .venv
	@echo "$(BLUE)Creating virtual environment and installing dependencies...$(RESET)"
	$(UV) venv $(VENV_NAME)
	$(UV) pip install pip setuptools
	$(UV) pip install -e .
	@echo "$(GREEN)✓ Setup complete.$(RESET)"

.PHONY: generate-audio
generate-audio: ## Generate user voice audio files via Rime (requires RIME_API_KEY)
	@echo "$(BLUE)Generating user audio files via Rime...$(RESET)"
	$(PYTHON) generate_user_audio.py
	@echo "$(GREEN)✓ Audio generation complete.$(RESET)"

.PHONY: train
train: ## Train the Rasa CALM dialogue model
	@echo "$(BLUE)Training Rasa model...$(RESET)"
	$(RASA) train
	@echo "$(GREEN)✓ Training complete.$(RESET)"

# ==============================================================================
# 🔍 Diagnostics
# ==============================================================================
.PHONY: verify
verify: ## Run pre-flight checks: API keys, connectivity, audio files
	@echo "$(BLUE)Running pre-flight diagnostics...$(RESET)"
	$(PYTHON) verify_setup.py

# ==============================================================================
# 🎤 Demo (3 separate terminals)
# ==============================================================================
.PHONY: run-actions
run-actions: ## Tab 1: Start the Rasa Action Server
	@echo "$(MAGENTA)Starting Action Server on port 5055...$(RESET)"
	$(RASA) run actions

.PHONY: run-rasa
run-rasa: ## Tab 2: Start the Rasa Agent
	@echo "$(MAGENTA)Starting Rasa Agent on port 5005...$(RESET)"
	$(RASA) run --enable-api --cors "*"

.PHONY: demo
demo: ## Tab 3: Run the live voice orchestration demo
	@echo "$(MAGENTA)Starting live voice demo...$(RESET)"
	$(PYTHON) demo_live.py

# ==============================================================================
# 🎭 The Heist Demo — add these targets to your existing Makefile
# ==============================================================================

.PHONY: run-rasa-heist
run-rasa-heist: ## Start Rasa with sub agents enabled (use this instead of run-rasa for the heist)
	@echo "$(MAGENTA)Starting Rasa with sub agents...$(RESET)"
	$(RASA) run --enable-api --cors "*" --sub-agents sub_agents

.PHONY: demo-heist
demo-heist: ## Run "The Heist at First National Bank" security demo
	@echo "$(MAGENTA)Starting The Heist demo...$(RESET)"
	@echo "$(YELLOW)Ensure these are running first:$(RESET)"
	@echo "  $(GREEN)make run-actions$(RESET)       Tab 1"
	@echo "  $(GREEN)make run-rasa-heist$(RESET)    Tab 2  ← note: NOT make run-rasa"
	@echo ""
	$(PYTHON) demo_heist.py

.PHONY: train-heist
train-heist: ## Train the Rasa model with sub agents
	@echo "$(BLUE)Training Rasa model with sub agents...$(RESET)"
	$(RASA) train --sub-agents sub_agents
	@echo "$(GREEN)✓ Training complete.$(RESET)"

.PHONY: verify-heist
verify-heist: ## Pre-flight check for all heist demo components
	@echo "$(BLUE)Verifying heist demo components...$(RESET)"
	$(PYTHON) -c "from agents.caller_agent import CallerAgent; print('  ✓ caller_agent')"
	$(PYTHON) -c "from agents.security_classifier import SecurityClassifier; print('  ✓ security_classifier')"
	$(PYTHON) -c "from scenario.arc import SCENARIO_ARC; print(f'  ✓ scenario arc ({len(SCENARIO_ARC)} turns)')"
	$(PYTHON) -c "from services.tts_service import RimeTTS; print('  ✓ tts_service (multi-voice)')"
	@echo "$(GREEN)✓ All heist components ready.$(RESET)"
	@echo ""
	@echo "$(YELLOW)Sub agent directory:$(RESET)"
	@ls -la sub_agents/llm_manager/
 

# ==============================================================================
# 🧪 Testing
# ==============================================================================
.PHONY: test
test: ## Run the full test suite (unit + integration, requires running Rasa)
	@echo "$(BLUE)Running full test suite...$(RESET)"
	$(PYTHON) -m pytest tests/test_flows.py -v

.PHONY: test-unit
test-unit: ## Run unit tests only (no live services required)
	@echo "$(BLUE)Running unit tests...$(RESET)"
	$(PYTHON) -m pytest tests/test_flows.py -v -m "not integration"

# ==============================================================================
# 🛠️ Development Utilities
# ==============================================================================
.PHONY: inspect
inspect: ## Open interactive Rasa shell for manual conversation testing
	@echo "$(BLUE)Opening interactive Rasa shell...$(RESET)"
	$(RASA) shell

.PHONY: inspect-debug
inspect-debug: ## Interactive Rasa shell with debug logging
	@echo "$(BLUE)Opening interactive Rasa shell (debug)...$(RESET)"
	$(RASA) shell --debug

.PHONY: clean
clean: ## Remove build artefacts, generated audio, and cache files
	@echo "$(YELLOW)Cleaning up...$(RESET)"
	rm -rf .rasa models results tests/audio_responses
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Clean complete.$(RESET)"

.PHONY: clean-audio
clean-audio: ## Remove generated audio files only (re-run make generate-audio to restore)
	@echo "$(YELLOW)Removing generated audio files...$(RESET)"
	rm -rf tests/audio
	@echo "$(GREEN)✓ Audio files removed. Run: make generate-audio$(RESET)"

# ==============================================================================
# 🔧 Tooling (annotate + flatten)
# ==============================================================================
ANNOTATE_SCOPE       ?= .
ANNOTATE_EXT         ?= .py,.yaml,.yml,.toml,.env
ANNOTATE_MAX_NEIGHBORS ?= 6

.PHONY: annotate
annotate: ## Add/update QV-LLM header blocks across repo files
	$(PYTHON) scripts/annotate_headers.py \
		--scope "$(ANNOTATE_SCOPE)" \
		--extensions "$(ANNOTATE_EXT)" \
		--max-neighbors "$(ANNOTATE_MAX_NEIGHBORS)" \
		--remove-legacy-path-line

FLATTEN_OUT   ?= _transient-files/flatten
FLATTEN_EXT   ?= .py,.yaml,.yml,.toml,.env,.example,.md
FLATTEN_SKIP  ?= .git,.venv,__pycache__,.mypy_cache,.pytest_cache,.ruff_cache,build,dist,.egg-info,node_modules
FLATTEN_SCOPE ?= .
MAX_BYTES     ?= 4000000

.PHONY: flatten
flatten: ## Flatten repo into a single shareable text bundle
	@echo "$(BLUE)Flattening '$(FLATTEN_SCOPE)' → $(FLATTEN_OUT)...$(RESET)"
	@mkdir -p "$(FLATTEN_OUT)"
	$(PYTHON) scripts/flatten.py \
		--mode scope \
		--scope "$(FLATTEN_SCOPE)" \
		--out-dir "$(FLATTEN_OUT)" \
		--extensions "$(FLATTEN_EXT)" \
		--skip-dirs "$(FLATTEN_SKIP)" \
		--exclude "flat.txt" \
		--exclude "_transient-files/**" \
		$(if $(MAX_BYTES),--max-bytes $(MAX_BYTES),)
	@echo "$(GREEN)✓ Done. See: $(FLATTEN_OUT)/manifest.md$(RESET)"

.PHONY: flatten-scope
flatten-scope: ## Flatten a specific directory: make flatten-scope SCOPE=path/to/dir
	@test -n "$(SCOPE)" || (echo "Usage: make flatten-scope SCOPE=path/to/dir" && exit 1)
	$(PYTHON) scripts/flatten.py \
		--mode scope \
		--scope "$(SCOPE)" \
		--out-dir "$(FLATTEN_OUT)" \
		--extensions "$(FLATTEN_EXT)" \
		--skip-dirs "$(FLATTEN_SKIP)" \
		--exclude "flat.txt" \
		--exclude "_transient-files/**" \
		--max-bytes 4000000

.PHONY: flatten-clean
flatten-clean: ## Remove transient flatten outputs
	rm -rf "$(FLATTEN_OUT)"