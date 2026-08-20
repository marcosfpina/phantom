# Phantom - Enterprise-Grade ML Framework
# Just command runner: https://github.com/casey/just
#
# Quick Start:
#   just            # Show all commands
#   just dev        # Enter development environment
#   just test       # Run test suite
#   just lint       # Run all linters
#   just build      # Build project

# Default recipe (show help)
default:
    @just --list --unsorted

# ═══════════════════════════════════════════════════════════════
# DEVELOPMENT ENVIRONMENT
# ═══════════════════════════════════════════════════════════════

# Enter Nix development shell (recommended)
dev:
    @echo "🚀 Entering Phantom development environment..."
    nix develop

# Enter development shell with specific system
dev-for SYSTEM:
    @echo "🚀 Entering development environment for {{SYSTEM}}..."
    nix develop .#devShells.{{SYSTEM}}.default

# Update flake dependencies
update:
    @echo "📦 Updating flake.lock..."
    nix flake update
    @echo "✅ Dependencies updated"

# Show flake outputs
show:
    nix flake show

# ═══════════════════════════════════════════════════════════════
# BUILDING
# ═══════════════════════════════════════════════════════════════

# Build all packages
build:
    @echo "🏗️  Building Phantom..."
    nix build
    @echo "✅ Build complete"

# Build specific package
build-package PACKAGE:
    @echo "🏗️  Building {{PACKAGE}}..."
    nix build .#{{PACKAGE}}
    @echo "✅ {{PACKAGE}} built successfully"

# Build and install to system (NixOS)
install:
    @echo "📦 Installing Phantom to system..."
    sudo nixos-rebuild switch --flake /etc/nixos#kernelcore --max-jobs 8 --cores 8
    @echo "✅ System rebuilt with Phantom"

# Run all Nix checks (CI validation)
check:
    @echo "🔍 Running flake checks..."
    nix flake check --show-trace
    @echo "✅ All checks passed"

# ═══════════════════════════════════════════════════════════════
# TESTING
# ═══════════════════════════════════════════════════════════════

# Run all tests
test:
    @echo "🧪 Running test suite..."
    pytest tests/ -v
    @echo "✅ Tests complete"

# Run tests with coverage
test-cov:
    @echo "🧪 Running tests with coverage..."
    pytest tests/ -v --cov=phantom --cov-report=html --cov-report=term
    @echo "📊 Coverage report generated at htmlcov/index.html"
    @echo "✅ Tests complete"

# Run specific test file
test-file FILE:
    @echo "🧪 Testing {{FILE}}..."
    pytest {{FILE}} -v

# Run tests matching pattern
test-match PATTERN:
    @echo "🧪 Running tests matching: {{PATTERN}}"
    pytest tests/ -v -k "{{PATTERN}}"

# Run unit tests only
test-unit:
    @echo "🧪 Running unit tests..."
    pytest tests/ -v -m unit

# Run integration tests
test-integration:
    @echo "🧪 Running integration tests..."
    pytest tests/ -v -m integration

# Run tests requiring GPU
test-gpu:
    @echo "🧪 Running GPU tests..."
    pytest tests/ -v -m gpu

# ═══════════════════════════════════════════════════════════════
# CODE QUALITY
# ═══════════════════════════════════════════════════════════════

# Run all linters and formatters
lint: ruff-check mypy

# Check code with ruff (no fixes)
ruff-check:
    @echo "🔍 Checking code with ruff..."
    ruff check src/ tests/
    @echo "✅ Ruff check complete"

# Fix auto-fixable issues
ruff-fix:
    @echo "🔧 Fixing code with ruff..."
    ruff check src/ tests/ --fix
    ruff format src/ tests/
    @echo "✅ Code fixed and formatted"

# Format code only
fmt:
    @echo "✨ Formatting code..."
    ruff format src/ tests/
    @echo "✅ Code formatted"

# Type check with mypy
mypy:
    @echo "🔍 Type checking with mypy..."
    mypy src/
    @echo "✅ Type check complete"

# Run pre-commit hooks on all files
pre-commit-all:
    @echo "🔍 Running pre-commit hooks..."
    pre-commit run --all-files
    @echo "✅ Pre-commit checks complete"

# Install pre-commit hooks
pre-commit-install:
    @echo "🔧 Installing pre-commit hooks..."
    pre-commit install
    @echo "✅ Pre-commit hooks installed"

# ═══════════════════════════════════════════════════════════════
# RUNNING
# ═══════════════════════════════════════════════════════════════

# Run Phantom CLI
run *ARGS:
    @echo "🎯 Running Phantom..."
    phantom {{ARGS}}

# Start API server (default port 8008 — matches securellm-mcp PHANTOM_URL)
serve PORT="8008":
    @echo "🌐 Starting Phantom API on port {{PORT}}..."
    phantom-api --port {{PORT}}

# Start Cortex API (backend for the desktop GUI, proxied through Vite on :1420)
cortex:
    @echo "🧠 Starting Cortex API on port 8087..."
    phantom-api

# Start GTK4 Writer Sandbox desktop app
desktop:
    @echo "🖥️  Starting Phantom Writer Desktop..."
    phantom-desktop

ui:
    @echo "🖥️  Starting Phantom Writer Desktop..."
    phantom-desktop

# Build legacy Tauri/Svelte desktop static assets
ui-build-legacy:
    @echo "🏗️  Building legacy Cortex Desktop (static)..."
    @cd cortex-desktop && npm run build

# Start legacy Tauri/Svelte desktop app
desktop-legacy:
    @echo "🖥️  Starting legacy Cortex Desktop..."
    @cd cortex-desktop && npm run tauri dev

# Run CORTEX demo
demo:
    @echo "🎬 Running CORTEX demo..."
    ./scripts/cortex_demo.sh

# ═══════════════════════════════════════════════════════════════
# VALIDATION & DEBUGGING
# ═══════════════════════════════════════════════════════════════

# Validate full stack
validate:
    @echo "✅ Validating Phantom stack..."
    ./scripts/validate_stack.sh

# Calculate VRAM requirements
vram MODEL="30" QUANT="Q4_K_M" CTX="4096":
    @echo "💾 Calculating VRAM for {{MODEL}}B model..."
    python src/phantom/tools/vram_calculator.py --model-size "{{MODEL}}" --quantization "{{QUANT}}" --context-size "{{CTX}}"

# Interactive VRAM calculator
vram-interactive:
    @echo "💾 Starting interactive VRAM calculator..."
    python src/phantom/tools/vram_calculator.py --interactive

# Check system resources
resources:
    @echo "📊 System Resources:"
    @echo "CPU: $(nproc) cores"
    @echo "RAM: $(free -h | awk '/^Mem:/ {print $2}')"
    @if command -v nvidia-smi &> /dev/null; then \
        echo "GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader)"; \
    else \
        echo "GPU: Not detected"; \
    fi

# ═══════════════════════════════════════════════════════════════
# DOCUMENTATION
# ═══════════════════════════════════════════════════════════════

# Generate architecture diagrams
docs-arch:
    @echo "📐 Generating architecture diagrams..."
    ./scripts/arch-generator.sh
    @echo "✅ Diagrams generated"

# Serve documentation locally (if using MkDocs/Sphinx)
# Serve documentation locally
docs-serve:
    @echo "📚 Documentation is available in the 'docs/' directory."
    @echo "💡 You can view it by opening docs/index.md (if it exists) or browsing the folder."

# Generate API documentation (Placeholder)
docs-api:
    @echo "📚 API Documentation generation is not yet configured."

# ═══════════════════════════════════════════════════════════════
# CLEANING
# ═══════════════════════════════════════════════════════════════

# Clean build artifacts
clean:
    @echo "🧹 Cleaning build artifacts..."
    rm -rf build/ dist/ *.egg-info
    rm -rf .pytest_cache .ruff_cache .mypy_cache
    rm -rf htmlcov/ .coverage
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    @echo "✅ Clean complete"

# Deep clean (including Nix artifacts)
clean-all: clean
    @echo "🧹 Deep cleaning..."
    rm -rf result result-*
    nix-collect-garbage
    @echo "✅ Deep clean complete"

# ═══════════════════════════════════════════════════════════════
# CI/CD
# ═══════════════════════════════════════════════════════════════

# Run full CI pipeline locally
ci: lint test
    @echo "✅ CI pipeline complete"

# Run CI with coverage
ci-full: lint test-cov check
    @echo "✅ Full CI pipeline complete"

# Prepare for release
release-prep VERSION:
    @echo "📦 Preparing release {{VERSION}}..."
    @echo "1. Updating version in pyproject.toml..."
    @echo "2. Running full CI..."
    just ci-full
    @echo "3. Creating git tag..."
    git tag -a v{{VERSION}} -m "Release v{{VERSION}}"
    @echo "✅ Release {{VERSION}} prepared. Push with: git push origin v{{VERSION}}"

# ═══════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════

# Show project statistics
stats:
    @echo "📊 Phantom Project Statistics"
    @echo "────────────────────────────────────────"
    @echo "Python files: $(find src/phantom -name '*.py' | wc -l)"
    @echo "Lines of code: $(find src/phantom -name '*.py' -exec wc -l {} + | tail -1 | awk '{print $1}')"
    @echo "Test files: $(find tests -name '*.py' | wc -l)"
    @echo "Documentation: $(find docs -name '*.md' | wc -l) markdown files"
    @echo "Git commits: $(git rev-list --count HEAD)"
    @echo "Contributors: $(git shortlog -sn | wc -l)"

# Show git log in pretty format
log LINES="10":
    @git log --oneline --graph --decorate -n {{LINES}}

# Search codebase
search PATTERN:
    @echo "🔍 Searching for: {{PATTERN}}"
    @rg "{{PATTERN}}" src/

# ═══════════════════════════════════════════════════════════════
# MAINTENANCE
# ═══════════════════════════════════════════════════════════════

# Update Python dependencies
deps-update:
    @echo "📦 Updating flake dependencies..."
    nix flake update
    @echo "✅ Dependencies updated."

# Security audit
audit:
    @echo "🔒 Running security audit..."
    @echo "Python packages:"
    pip-audit
    @echo "\nRust packages:"
    cd cortex-desktop/src-tauri && cargo audit
    @echo "✅ Security audit complete"

# Check for outdated dependencies
deps-outdated:
    @echo "📦 Checking outdated dependencies..."
    @echo "Rust crates:"
    cd cortex-desktop/src-tauri && cargo outdated
    @echo "✅ Check complete"

# Fix common issues automatically
fix-all: ruff-fix pre-commit-install
    @echo "🔧 Running all automatic fixes..."
    @echo "✅ Fixes applied"

# ═══════════════════════════════════════════════════════════════
# EXAMPLES & DEMOS
# ═══════════════════════════════════════════════════════════════

# Run example: Basic document processing
example-basic:
    @echo "📖 Running basic example..."
    phantom process demo_input/financial_report.md -o /tmp/phantom_output.json
    @cat /tmp/phantom_output.json | jq '.themes'

# Run example: Batch processing
example-batch:
    @echo "📖 Running batch processing example..."
    phantom batch-process demo_input/ -o /tmp/phantom_batch/

# Run example: Semantic search
example-search:
    @echo "📖 Running semantic search example..."
    @echo "⚠️  TODO: Add semantic search example"

# ═══════════════════════════════════════════════════════════════
# HELP & INFO
# ═══════════════════════════════════════════════════════════════

# Show environment information
info:
    @echo "╔══════════════════════════════════════════════════════════════════╗"
    @echo "║                          PHANTOM v2.0                            ║"
    @echo "║            AI-Powered Document Intelligence Pipeline             ║"
    @echo "╚══════════════════════════════════════════════════════════════════╝"
    @echo ""
    @echo "Environment:"
    @echo "  Python: $(python --version 2>&1 | cut -d' ' -f2)"
    @echo "  Nix: $(nix --version 2>&1 | cut -d' ' -f3)"
    @echo "  Just: $(just --version)"
    @echo "  Git: $(git --version 2>&1 | cut -d' ' -f3)"
    @echo ""
    @echo "Paths:"
    @echo "  Project: $(pwd)"
    @echo "  Python: $(which python)"
    @echo ""
    @echo "Quick Commands:"
    @echo "  just dev      - Enter development environment"
    @echo "  just test     - Run tests"
    @echo "  just lint     - Check code quality"
    @echo "  just run      - Run Phantom CLI"
    @echo ""
    @echo "For full command list: just --list"
