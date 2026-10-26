#!/usr/bin/env bash
# Apply the versioned swegemma adapter to a disposable harness2 clone.
#
# The clone lives under tmp/ (git-ignored). This script refuses a different
# upstream commit: the patch is generated against exactly that tree.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
CLONE="${HARNESS2_CLONE:-$REPO_ROOT/tmp/harness2}"
PIN="1cfe254e8d25b15f37048c3730134686abe60335"
PATCH="$HERE/swegemma-adapter.patch"

if [ ! -d "$CLONE/.git" ]; then
  git clone https://github.com/google-research/harness2 "$CLONE"
fi

HEAD="$(git -C "$CLONE" rev-parse HEAD)"
if [ "$HEAD" != "$PIN" ]; then
  echo "error: $CLONE is at $HEAD, expected $PIN" >&2
  echo "move it aside or check out the pin before applying the patch" >&2
  exit 1
fi

if git -C "$CLONE" apply --reverse --check "$PATCH" >/dev/null 2>&1; then
  echo "patch already applied"
else
  git -C "$CLONE" apply --check "$PATCH"
  git -C "$CLONE" apply "$PATCH"
  echo "applied $PATCH"
fi

if command -v uv >/dev/null 2>&1; then
  if [ ! -x "$CLONE/.venv/bin/python" ]; then
    uv venv --python 3.13 "$CLONE/.venv"
    uv pip install --python "$CLONE/.venv/bin/python" -e "$CLONE"
  fi
  echo "fork ready: $CLONE/.venv/bin/python"
else
  echo "uv not found; run with PYTHONPATH=$CLONE python3 (3.12+)"
fi

cat <<EOF

Next, from the repository root:
  export OPENAI_BASE_URL=http://127.0.0.1:1234/v1
  export HARNESS_MODEL=gemma-4-31b-it-qat
  export HARNESS2_SWEGEMMA_ROOT=\$PWD
  export HARNESS2_SWEGEMMA_SUBSET=dev-v1
  PYTHONPATH=$CLONE python3 "$REPO_ROOT/tools/harness2-swegemma/falsifier.py"
EOF
