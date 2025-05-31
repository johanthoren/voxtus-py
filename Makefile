# Voxtus Development Makefile
# Uses uv for fast Python package management

.PHONY: help install dev-install test test-ci release verify-uv verify-act

# Default target
help: ## Show this help message
	@echo "Voxtus Development Commands:"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "Release Examples:"
	@current_version=$$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	IFS='.' read -r major minor patch <<< "$$current_version"; \
	patch_version="$$major.$$minor.$$((patch + 1))"; \
	minor_version="$$major.$$((minor + 1)).0"; \
	major_version="$$((major + 1)).0.0"; \
	echo "  \033[36mmake release\033[0m        Bump patch version and release ($$current_version -> $$patch_version)"; \
	echo "  \033[36mmake release patch\033[0m  Bump patch version and release ($$current_version -> $$patch_version)"; \
	echo "  \033[36mmake release minor\033[0m  Bump minor version and release ($$current_version -> $$minor_version)"; \
	echo "  \033[36mmake release major\033[0m  Bump major version and release ($$current_version -> $$major_version)"

# Dependency verification
verify-uv: ## Verify uv is installed
	@which uv > /dev/null || (echo "❌ uv is not installed. Install with:" && \
	echo "  curl -LsSf https://astral.sh/uv/install.sh | sh" && \
	echo "  # or: pip install uv" && \
	echo "  # or: brew install uv (macOS)" && exit 1)
	@echo "✅ uv is available"

verify-act: ## Verify act is installed  
	@which act > /dev/null || (echo "❌ act is not installed. Install with:" && \
	echo "  brew install act (macOS)" && \
	echo "  # or: https://github.com/nektos/act#installation" && exit 1)
	@echo "✅ act is available"

# Development setup
install: verify-uv ## Install package and dependencies
	uv sync
	uv pip install -e .

dev-install: verify-uv ## Install package in development mode with dev dependencies
	uv sync --extra dev
	uv pip install -e ".[dev]"

# Testing
test: verify-uv ## Run tests
	uv run pytest

test-coverage: verify-uv ## Run tests with coverage report
	uv run pytest --cov=voxtus --cov-report=term-missing

test-ci: verify-act ## Run tests using act (GitHub Actions locally)
	act -W .github/workflows/test.yml

# Release process
release: verify-uv ## Bump version, commit, tag and push (args: patch|minor|major, default: patch)
	@echo "🚀 Starting release process..."
	@echo
	@# Determine version bump type (default to patch)
	@VERSION_TYPE="$(filter-out release,$(MAKECMDGOALS))"; \
	if [ -z "$$VERSION_TYPE" ]; then VERSION_TYPE="patch"; fi; \
	echo "📈 Version bump type: $$VERSION_TYPE"; \
	echo
	@# Check working directory is clean
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "⚠️  Working directory has uncommitted changes:"; \
		git status --short; \
		echo; \
		read -p "Stage all changes and commit before release? [y/N] " commit_changes; \
		if [ "$$commit_changes" = "y" ]; then \
			read -p "Enter commit message: " commit_msg; \
			if [ -z "$$commit_msg" ]; then \
				echo "❌ Commit message cannot be empty"; \
				exit 1; \
			fi; \
			echo "📝 Staging all changes..."; \
			git add .; \
			echo "💾 Committing changes..."; \
			git commit -m "$$commit_msg"; \
			echo "✅ Changes committed"; \
		else \
			echo "❌ Release aborted. Please commit or stash changes first."; \
			exit 1; \
		fi; \
	fi
	@echo "✅ Working directory is clean"
	@# Run tests
	@echo "🧪 Running tests with coverage..."
	@coverage_output=$$(uv run pytest --cov=voxtus --cov-report=term-missing 2>&1); \
	echo "$$coverage_output"; \
	coverage_percent=$$(echo "$$coverage_output" | grep -o 'TOTAL.*[0-9]\+%' | grep -o '[0-9]\+%' | sed 's/%//'); \
	if [ -n "$$coverage_percent" ] && [ "$$coverage_percent" -lt 80 ]; then \
		echo "⚠️  Coverage is $$coverage_percent% (below 80% threshold)"; \
		read -p "Continue with release anyway? [y/N] " confirm; \
		if [ "$$confirm" != "y" ]; then \
			echo "❌ Release aborted due to low coverage"; \
			exit 1; \
		fi; \
		echo "✅ Continuing with release despite low coverage"; \
	else \
		echo "✅ Coverage check passed ($$coverage_percent%)"; \
	fi
	@# Bump version
	@VERSION_TYPE="$(filter-out release,$(MAKECMDGOALS))"; \
	if [ -z "$$VERSION_TYPE" ]; then VERSION_TYPE="patch"; fi; \
	echo "📝 Bumping $$VERSION_TYPE version..."; \
	current_version=$$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	echo "Current version: $$current_version"; \
	IFS='.' read -r major minor patch <<< "$$current_version"; \
	case "$$VERSION_TYPE" in \
		patch) new_version="$$major.$$minor.$$((patch + 1))" ;; \
		minor) new_version="$$major.$$((minor + 1)).0" ;; \
		major) new_version="$$((major + 1)).0.0" ;; \
		*) echo "❌ Invalid version type: $$VERSION_TYPE. Use patch, minor, or major"; exit 1 ;; \
	esac; \
	echo "New version: $$new_version"; \
	sed -i '' 's/^version = ".*"/version = "'$$new_version'"/' pyproject.toml; \
	echo "✅ Updated pyproject.toml with version $$new_version"; \
	echo "📝 Committing version bump..."; \
	git add pyproject.toml; \
	git commit -m "Bump version to $$new_version"; \
	echo "✅ Version bump committed"; \
	echo "🏷️  Creating git tag: $$new_version"; \
	git tag "$$new_version"; \
	echo "📤 Pushing commit and tag to origin..."; \
	current_branch=$$(git branch --show-current); \
	git push origin "$$current_branch"; \
	git push origin "$$new_version"; \
	echo "🎉 Release $$new_version completed!"; \
	echo "📦 Package will be available on PyPI shortly"

# Allow version arguments to be treated as targets (prevents "No rule to make target" error)
patch minor major:
	@true 