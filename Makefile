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

.PHONY: add-paths
add-paths: ## Add file paths as first-line comments to all Python files
	@echo "${BLUE}Adding file paths as comments to Python files...${RESET}"
	@echo '#!/usr/bin/env python' > add_paths.py
	@echo '# add_paths.py' >> add_paths.py
	@echo '"""' >> add_paths.py
	@echo 'Script to add file paths as first-line comments to Python files.' >> add_paths.py
	@echo '"""' >> add_paths.py
	@echo 'import os' >> add_paths.py
	@echo 'import sys' >> add_paths.py
	@echo 'import traceback' >> add_paths.py
	@echo '' >> add_paths.py
	@echo 'EXTENSIONS = (".py", ".yaml", ".yml", ".toml", ".env", ".example")' >> add_paths.py
	@echo '' >> add_paths.py
	@echo 'def update_file(filepath):' >> add_paths.py
	@echo '    try:' >> add_paths.py
	@echo '        relpath = os.path.relpath(filepath)' >> add_paths.py
	@echo '        print(f"Processing {relpath}...")' >> add_paths.py
	@echo '' >> add_paths.py
	@echo '        with open(filepath, "r") as f:' >> add_paths.py
	@echo '            content = f.read()' >> add_paths.py
	@echo '' >> add_paths.py
	@echo '        lines = content.split("\\n")' >> add_paths.py
	@echo '        if not lines:' >> add_paths.py
	@echo '            print(f"  Skipping {relpath}: empty file")' >> add_paths.py
	@echo '            return' >> add_paths.py
	@echo '' >> add_paths.py
	@echo '        has_path_comment = False' >> add_paths.py
	@echo '        if lines[0].strip().startswith("#"):' >> add_paths.py
	@echo '            has_path_comment = True' >> add_paths.py
	@echo '            old_line = lines[0]' >> add_paths.py
	@echo '            lines[0] = f"# {relpath}"' >> add_paths.py
	@echo '            print(f"  Replacing comment: {old_line} -> # {relpath}")' >> add_paths.py
	@echo '        else:' >> add_paths.py
	@echo '            lines.insert(0, f"# {relpath}")' >> add_paths.py
	@echo '            print(f"  Adding new comment: # {relpath}")' >> add_paths.py
	@echo '' >> add_paths.py
	@echo '        with open(filepath, "w") as f:' >> add_paths.py
	@echo '            f.write("\\n".join(lines))' >> add_paths.py
	@echo '' >> add_paths.py
	@echo '        print(f"  Updated {relpath}")' >> add_paths.py
	@echo '    except Exception as e:' >> add_paths.py
	@echo '        print(f"  Error processing {filepath}: {str(e)}")' >> add_paths.py
	@echo '        traceback.print_exc()' >> add_paths.py
	@echo '' >> add_paths.py
	@echo 'def main():' >> add_paths.py
	@echo '    try:' >> add_paths.py
	@echo '        count = 0' >> add_paths.py
	@echo '        print("Starting file scan...")' >> add_paths.py
	@echo '        for root, dirs, files in os.walk("."):' >> add_paths.py
	@echo '            # Skip hidden and build directories' >> add_paths.py
	@echo '            if any(x in root for x in [".git", ".venv", "__pycache__", ".mypy_cache",' >> add_paths.py
	@echo '                                      ".pytest_cache", ".ruff_cache", "build", "dist", ".egg-info"]):' >> add_paths.py
	@echo '                continue' >> add_paths.py
	@echo '' >> add_paths.py
	@echo '            for file in files:' >> add_paths.py
	@echo '                if file.endswith(EXTENSIONS):' >> add_paths.py
	@echo '                    filepath = os.path.join(root, file)' >> add_paths.py
	@echo '                    update_file(filepath)' >> add_paths.py
	@echo '                    count += 1' >> add_paths.py
	@echo '' >> add_paths.py
	@echo '        print(f"Processed {count} files (extensions: {EXTENSIONS})")' >> add_paths.py
	@echo '    except Exception as e:' >> add_paths.py
	@echo '        print(f"Fatal error: {str(e)}")' >> add_paths.py
	@echo '        traceback.print_exc()' >> add_paths.py
	@echo '        sys.exit(1)' >> add_paths.py
	@echo '' >> add_paths.py
	@echo 'if __name__ == "__main__":' >> add_paths.py
	@echo '    main()' >> add_paths.py
	@chmod +x add_paths.py
	@$(PYTHON) add_paths.py
	@rm add_paths.py
	@echo "${GREEN}✓ File paths added to all files${RESET}"