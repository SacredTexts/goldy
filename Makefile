.PHONY: test lint install uninstall update verify help

GOLDY_HOME := $(HOME)/.goldy
SCRIPTS_DIR := $(GOLDY_HOME)/scripts

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

test: ## Run the test suite
	python3 -m pytest tests/ -v 2>/dev/null || python3 -m unittest discover -s tests -v

lint: ## Check Python files for syntax errors
	python3 -m py_compile scripts/goldy.py
	python3 -m py_compile scripts/goldy_loop.py
	python3 -m py_compile scripts/goldy_install.py
	@echo "All core scripts compile cleanly."
	@for f in scripts/*.py; do \
		python3 -m py_compile "$$f" 2>/dev/null || echo "WARN: $$f has issues"; \
	done
	@echo "Lint complete."

install: ## Install goldy globally (symlinks + commands)
	bash install.sh

uninstall: ## Remove goldy from this system
	@echo "Removing goldy installation..."
	rm -f $(HOME)/.claude/commands/goldy.md
	rm -f $(HOME)/.claude/commands/goldy-loop.md
	rm -f $(HOME)/.claude/GOLD-STANDARD-SAMPLE-PLAN.md
	rm -rf $(HOME)/.claude/skills/goldy
	rm -rf $(HOME)/.agents/skills/goldy
	rm -rf $(HOME)/.codex/skills/goldy
	@echo "Goldy uninstalled. The repo at ~/.goldy/ is preserved."
	@echo "To fully remove: rm -rf ~/.goldy"

update: ## Pull latest changes and re-install
	git pull --ff-only
	bash install.sh

verify: ## Verify installation integrity
	python3 scripts/goldy_install.py verify

count: ## Show file counts
	@echo "Python scripts: $$(find scripts -name '*.py' | wc -l | tr -d ' ')"
	@echo "Data CSVs:      $$(find data -name '*.csv' | wc -l | tr -d ' ')"
	@echo "References:     $$(find references -name '*.md' | wc -l | tr -d ' ')"
	@echo "Commands:       $$(find commands -name '*.md' | wc -l | tr -d ' ')"
