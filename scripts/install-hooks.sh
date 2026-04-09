#!/usr/bin/env bash
# install-hooks.sh — Install blueprint git hooks into .git/hooks/
#
# Usage:
#   bash scripts/install-hooks.sh
#
# What it installs:
#   post-commit  — runs `blueprint diff --from HEAD~1 --to HEAD` after each commit
#                  so blueprint_changes.json stays up-to-date automatically.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"

if [[ -z "$REPO_ROOT" ]]; then
  echo "ERROR: Not inside a git repository." >&2
  exit 1
fi

GIT_HOOKS_DIR="$REPO_ROOT/.git/hooks"
mkdir -p "$GIT_HOOKS_DIR"

# ---- post-commit hook ----
HOOK_PATH="$GIT_HOOKS_DIR/post-commit"

cat > "$HOOK_PATH" <<'HOOK'
#!/usr/bin/env bash
# Blueprint post-commit hook
# Runs `blueprint diff` after each commit to update blueprint_changes.json.
# blueprint_changes.json can then be committed separately (or by CI).

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Skip silently if the scanner is not installed in this environment
if ! python -c "import scanner.main" 2>/dev/null; then
  exit 0
fi

# Check if there is a previous commit to compare against
if ! git rev-parse --verify HEAD~1 >/dev/null 2>&1; then
  # Initial commit — nothing to diff against
  exit 0
fi

echo "[blueprint hook] Running blueprint diff (HEAD~1 → HEAD)…"
python -m scanner.main diff --from HEAD~1 --to HEAD || {
  echo "[blueprint hook] diff failed (non-fatal)" >&2
}
HOOK

chmod +x "$HOOK_PATH"
echo "[blueprint] Installed post-commit hook → $HOOK_PATH"
echo ""
echo "  The hook runs:  python -m scanner.main diff --from HEAD~1 --to HEAD"
echo "  Output appends to: blueprint_changes.json"
echo ""
echo "  To commit the change log manually after a session:"
echo "    git add blueprint_changes.json && git commit -m 'chore: update blueprint change log'"
