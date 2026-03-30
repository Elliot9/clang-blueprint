#!/usr/bin/env bash
# setup.sh — T-01: 建立 Python 虛擬環境並安裝所有依賴
# 用法: bash scripts/setup.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv"

echo "=== clang-blueprint setup ==="
echo "Repo: $REPO_ROOT"

# ── 1. Python version check ────────────────────────────────────────────────
# Prefer Homebrew Python 3.11+ if the default is too old
for candidate in "${PYTHON:-}" python3.13 python3.12 python3.11 python3.10 python3; do
  [[ -z "$candidate" ]] && continue
  if command -v "$candidate" &>/dev/null; then
    PYTHON_BIN="$candidate"
    break
  fi
done
PY_VERSION=$("$PYTHON_BIN" -c "import sys; print('%d.%d' % sys.version_info[:2])")
REQUIRED="3.9"
if "$PYTHON_BIN" -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"; then
  echo "✓ Python $PY_VERSION"
else
  echo "✗ Python $REQUIRED+ required (found $PY_VERSION)" >&2
  exit 1
fi

# ── 2. Create venv ─────────────────────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment at $VENV_DIR ..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
else
  echo "✓ Virtual environment already exists at $VENV_DIR"
fi

PIP="$VENV_DIR/bin/pip"
PYTHON_VENV="$VENV_DIR/bin/python"

# ── 3. Upgrade pip ────────────────────────────────────────────────────────
"$PIP" install --quiet --upgrade pip

# ── 4. Install dependencies ───────────────────────────────────────────────
echo "Installing Python dependencies ..."
"$PIP" install --quiet -r "$REPO_ROOT/requirements.txt"

# ── 5. Install package in editable mode ──────────────────────────────────
echo "Installing clang-blueprint in editable mode ..."
"$PIP" install --quiet -e "$REPO_ROOT[dev]"

# ── 6. Verify libclang ───────────────────────────────────────────────────
echo "Verifying libclang ..."
if "$PYTHON_VENV" -c "import clang.cindex; clang.cindex.Index.create(); print('✓ libclang OK')"; then
  :
else
  echo ""
  echo "⚠ libclang import failed. Try one of:"
  echo "   macOS:  brew install llvm && export DYLD_LIBRARY_PATH=\$(brew --prefix llvm)/lib"
  echo "   Ubuntu: sudo apt-get install libclang-16-dev"
  echo "           export LD_LIBRARY_PATH=/usr/lib/llvm-16/lib"
fi

# ── 7. Verify pytest ──────────────────────────────────────────────────────
"$VENV_DIR/bin/pytest" --version | head -1 && echo "✓ pytest OK"

echo ""
echo "=== Setup complete ==="
echo "Activate with:  source $VENV_DIR/bin/activate"
echo "Run tests with: pytest tests/"
echo "Run scanner:    blueprint scan --project-root <dir>"
