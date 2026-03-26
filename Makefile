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
	@echo '$(MAGENTA)🏦 Rasa + Speechmatics: Voice Security Demo$(RESET)'
	@echo ''
	@echo '$(YELLOW)First-time setup:$(RESET)'
	@echo '  $(GREEN)make install$(RESET)          Install dependencies into .venv'
	@echo '  $(GREEN)make generate-audio$(RESET)   Generate the user voice audio files'
	@echo '  $(GREEN)make train$(RESET)             Train the Rasa dialogue model (basic demo)'
	@echo '  $(GREEN)make train-heist$(RESET)       Train with sub agents (heist demo)'
	@echo ''
	@echo '$(YELLOW)Diagnostics:$(RESET)'
	@echo '  $(GREEN)make verify$(RESET)            Pre-flight check: API keys, services, audio files'
	@echo '  $(GREEN)make verify-heist$(RESET)      Pre-flight check for heist demo components'
	@echo ''
	@echo '$(YELLOW)Basic Demo (3 terminals):$(RESET)'
	@echo '  $(GREEN)make run-actions$(RESET)       Tab 1 — Start the Action Server'
	@echo '  $(GREEN)make run-rasa$(RESET)          Tab 2 — Start Rasa (basic demo)'
	@echo '  $(GREEN)make demo$(RESET)              Tab 3 — Run the basic voice demo'
	@echo ''
	@echo '$(YELLOW)Heist Demo (4 terminals):$(RESET)'
	@echo '  $(GREEN)make run-mcp$(RESET)           Tab 0 — MCP proxy (heist only)'
	@echo '  $(GREEN)make run-actions$(RESET)       Tab 1 — Start the Action Server'
	@echo '  $(GREEN)make run-rasa-heist$(RESET)    Tab 2 — Start Rasa with sub agents enabled'
	@echo '  $(GREEN)make demo-heist$(RESET)        Tab 3 — Run The Heist security demo'
	@echo ''
	@echo '$(YELLOW)Development:$(RESET)'
	@echo '  $(GREEN)make test$(RESET)              Run the test suite (unit + integration)'
	@echo '  $(GREEN)make test-unit$(RESET)         Run unit tests only (no live services needed)'
	@echo '  $(GREEN)make inspect$(RESET)           Interactive Rasa shell for manual testing'
	@echo '  $(GREEN)make run-rasa-heist-debug$(RESET)  Rasa with filtered debug logging'
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
generate-audio: ## Generate user voice audio files via Speechmatics TTS
	@echo "$(BLUE)Generating user audio files via Speechmatics...$(RESET)"
	$(PYTHON) generate_user_audio.py
	@echo "$(GREEN)✓ Audio generation complete.$(RESET)"

# ==============================================================================
# 🏋️ Training
# ==============================================================================
.PHONY: train
train: ## Train the Rasa CALM dialogue model (basic demo — no sub agents)
	@echo "$(BLUE)Training Rasa model...$(RESET)"
	$(RASA) train
	@echo "$(GREEN)✓ Training complete.$(RESET)"

.PHONY: train-heist
train-heist: ## Train Rasa with sub agents enabled (required for heist demo)
	@echo "$(BLUE)Training Rasa model with sub agents...$(RESET)"
	$(RASA) train --sub-agents sub_agents
	@echo "$(GREEN)✓ Training complete (sub agents included).$(RESET)"

# ==============================================================================
# 🔍 Diagnostics
# ==============================================================================
.PHONY: verify
verify: ## Run pre-flight checks: API keys, connectivity, audio files
	@echo "$(BLUE)Running pre-flight diagnostics...$(RESET)"
	$(PYTHON) verify_setup.py

.PHONY: verify-heist
verify-heist: ## Pre-flight check for all heist demo components
	@echo "$(BLUE)Verifying heist demo components...$(RESET)"
	$(PYTHON) -c "from agents.caller_agent import CallerAgent; print('  ✓ caller_agent')"
	$(PYTHON) -c "from agents.security_classifier import SecurityClassifier; print('  ✓ security_classifier')"
	$(PYTHON) -c "from scenario.arc import SCENARIO_ARC; print(f'  ✓ scenario arc ({len(SCENARIO_ARC)} turns)')"
	$(PYTHON) -c "from services.speechmatics_service import SpeechmaticsService; print('  ✓ speechmatics_service (TTS + ASR)')"
	@test -f sub_agents/llm_manager/config.yml && echo "  ✓ sub_agents/llm_manager/config.yml" || echo "  ✗ sub_agents/llm_manager/config.yml MISSING"
	@test -f sub_agents/llm_manager/manager_agent.py && echo "  ✓ sub_agents/llm_manager/manager_agent.py" || echo "  ✗ sub_agents/llm_manager/manager_agent.py MISSING"
	@echo "$(GREEN)✓ Heist verification complete.$(RESET)"

# ==============================================================================
# 🎤 Basic Demo (3 separate terminals)
# ==============================================================================
.PHONY: run-actions
run-actions: ## Tab 1: Start the Rasa Action Server (used by both demos)
	@echo "$(MAGENTA)Starting Action Server on port 5055...$(RESET)"
	$(RASA) run actions

.PHONY: run-rasa
run-rasa: ## Tab 2: Start Rasa Agent (basic demo only — no sub agents)
	@echo "$(MAGENTA)Starting Rasa Agent on port 5005...$(RESET)"
	$(RASA) run --enable-api --cors "*"

.PHONY: demo
demo: ## Tab 3: Run the basic voice orchestration demo
	@echo "$(MAGENTA)Starting basic voice demo...$(RESET)"
	$(PYTHON) demo_live.py

# ==============================================================================
# 🎭 Heist Demo (4 separate terminals)
# ==============================================================================
.PHONY: run-mcp
run-mcp: ## Tab 0: Start the MCP proxy server (required for heist demo)
	@echo "$(BLUE)Starting MCP proxy server on port 8999...$(RESET)"
	uvx mcp-proxy --port 8999 --host 0.0.0.0 --allow-origin "*" -- uvx mcp-server-fetch

.PHONY: run-rasa-heist
run-rasa-heist: ## Tab 2: Start Rasa with sub agents (REQUIRED for heist demo)
	@echo "$(MAGENTA)Starting Rasa Agent with sub agents on port 5005...$(RESET)"
	@echo "$(YELLOW)Note: sub agents loaded from: sub_agents/$(RESET)"
	$(RASA) run --enable-api --cors "*" --sub-agents sub_agents

.PHONY: run-rasa-heist-debug
run-rasa-heist-debug: ## Tab 2: Start Rasa with sub agents + filtered debug logging
	@echo "$(MAGENTA)Starting Rasa Agent (DEBUG MODE) with sub agents on port 5005...$(RESET)"
	@echo "$(YELLOW)Note: logs filtered to LLM command parsing, flows, and errors$(RESET)"
	$(RASA) run --enable-api --cors "*" --sub-agents sub_agents --debug 2>&1 | \
		grep -E "(CompactLLM|StartFlow|CancelFlow|parse_commands|predict_commands|WARNING|ERROR|request_human|llm_manager)" || true

.PHONY: demo-heist
demo-heist: ## Tab 3: Run The Heist at First National Bank security demo
	@echo "$(MAGENTA)Starting The Heist demo...$(RESET)"
	@echo "$(YELLOW)Ensure these are running first:$(RESET)"
	@echo "  $(GREEN)make run-mcp$(RESET)           Tab 0  ← MCP proxy (heist only)"
	@echo "  $(GREEN)make run-actions$(RESET)       Tab 1"
	@echo "  $(GREEN)make run-rasa-heist$(RESET)    Tab 2  ← NOT make run-rasa"
	@echo ""
	$(PYTHON) demo_heist.py

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
	$(RASA) shell --debug

.PHONY: clean
clean: ## Remove build artefacts, generated audio, and cache files
	@echo "$(YELLOW)Cleaning up...$(RESET)"
	rm -rf .rasa models results tests/audio_responses
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Clean complete.$(RESET)"

.PHONY: clean-audio
clean-audio: ## Remove generated audio files only
	@echo "$(YELLOW)Removing generated audio files...$(RESET)"
	rm -rf tests/audio
	@echo "$(GREEN)✓ Run: make generate-audio$(RESET)"

# ==============================================================================
# 🔧 Tooling (annotate + flatten)
# ==============================================================================
ANNOTATE_SCOPE         ?= .
ANNOTATE_EXT           ?= .py,.yaml,.yml,.toml,.env
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