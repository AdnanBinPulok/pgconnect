#!/usr/bin/env bash

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <version>"
  echo "Example: $0 0.7.3"
  exit 1
fi

TARGET_VERSION="$1"

if [[ ! "$TARGET_VERSION" =~ ^[0-9]+(\.[0-9]+)*$ ]]; then
  echo "Invalid version: $TARGET_VERSION"
  echo "Use a version like 0.7.3"
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCANNED=0
VALID=0
UPGRADED=0
SKIPPED=0
FAILED=0

should_skip() {
  local path="$1"
  [[ "$path" == *".git"* ]] && return 0
  [[ "$path" == *"__pycache__"* ]] && return 0
  [[ "$path" == *".pytest_cache"* ]] && return 0
  [[ "$path" == *"node_modules"* ]] && return 0
  return 1
}

pgconnect_version() {
  local python="$1"
  "$python" -c "
from importlib.metadata import PackageNotFoundError, version
try:
    print(version('pgconnect'))
except PackageNotFoundError:
    raise SystemExit(1)
"
}

process_venv() {
  local venv_path="$1"
  local python="$venv_path/bin/python"

  if [[ ! -x "$python" ]]; then
    echo "[SKIP] Not a valid venv (missing bin/python): $venv_path"
    SKIPPED=$((SKIPPED + 1))
    return
  fi

  if ! "$python" -c 'import sys; raise SystemExit(0 if hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix) else 1)' 2>/dev/null; then
    echo "[SKIP] Folder named venv but Python is not isolated: $venv_path"
    SKIPPED=$((SKIPPED + 1))
    return
  fi

  VALID=$((VALID + 1))

  if ! old_version="$(pgconnect_version "$python" 2>/dev/null)"; then
    echo "[SKIP] pgconnect not installed: $venv_path"
    SKIPPED=$((SKIPPED + 1))
    return
  fi

  if [[ "$old_version" == "$TARGET_VERSION" ]]; then
    echo "[SKIP] Already on $TARGET_VERSION: $venv_path"
    SKIPPED=$((SKIPPED + 1))
    return
  fi

  local new_version
  echo ""
  echo "[REINSTALL] $venv_path"
  echo "            current version: $old_version"
  echo "            target version:  $TARGET_VERSION"

  if ! "$python" -m pip uninstall -y pgconnect; then
    echo "[FAIL] Could not uninstall pgconnect in $venv_path"
    FAILED=$((FAILED + 1))
    return
  fi

  if ! "$python" -m pip install "pgconnect==${TARGET_VERSION}"; then
    echo "[FAIL] Could not install pgconnect==${TARGET_VERSION} in $venv_path"
    FAILED=$((FAILED + 1))
    return
  fi

  if ! new_version="$(pgconnect_version "$python" 2>/dev/null)"; then
    echo "[FAIL] pgconnect missing after reinstall in $venv_path"
    FAILED=$((FAILED + 1))
    return
  fi

  echo "[OK] Installed pgconnect $new_version"
  UPGRADED=$((UPGRADED + 1))

  if ! "$python" -m pip check >/dev/null 2>&1; then
    echo "[WARN] Dependency conflicts in $venv_path. Check with:"
    echo "       $python -m pip check"
  fi
}

echo ""
echo "========================================"
echo " pgconnect venv upgrader"
echo " Scan root: $ROOT"
echo " Target version: $TARGET_VERSION"
echo "========================================"
echo ""

while IFS= read -r venv_path; do
  if should_skip "$venv_path"; then
    continue
  fi
  SCANNED=$((SCANNED + 1))
  process_venv "$venv_path"
done < <(
  find "$ROOT" \
    \( -path '*/.git/*' -o -path '*/__pycache__/*' -o -path '*/.pytest_cache/*' -o -path '*/node_modules/*' \) -prune \
    -o -type d -name venv -print
)

echo ""
echo "========================================"
echo " Done"
echo " venv folders found : $SCANNED"
echo " valid venvs        : $VALID"
echo " reinstalled        : $UPGRADED"
echo " skipped            : $SKIPPED"
echo " failed             : $FAILED"
echo "========================================"
echo ""

exit 0
