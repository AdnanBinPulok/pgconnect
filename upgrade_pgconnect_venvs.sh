#!/usr/bin/env bash

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <version>"
  echo "Example: $0 0.7.4"
  exit 1
fi

TARGET_VERSION="$1"

if [[ ! "$TARGET_VERSION" =~ ^[0-9]+(\.[0-9]+)*$ ]]; then
  echo "Invalid version: $TARGET_VERSION"
  echo "Use a version like 0.7.4"
  exit 1
fi

pypi_wheel_url() {
  local version="$1"
  curl -sf "https://pypi.org/pypi/pgconnect/${version}/json" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data.get('urls', []):
    if item.get('packagetype') == 'bdist_wheel':
        print(item['url'])
        break
else:
    raise SystemExit(1)
"
}

if ! TARGET_WHEEL_URL="$(pypi_wheel_url "$TARGET_VERSION")"; then
  echo "pgconnect ${TARGET_VERSION} is not on PyPI."
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

prepare_pip() {
  local python="$1"
  local venv_path="$2"

  echo "          upgrading pip..."
  if ! "$python" -m pip install --upgrade pip --no-cache-dir; then
    echo "[FAIL] Could not upgrade pip in $venv_path"
    return 1
  fi

  echo "          purging pip cache..."
  "$python" -m pip cache purge >/dev/null 2>&1 || true
  return 0
}

install_pgconnect_wheel() {
  local python="$1"
  local wheel_url="$2"

  "$python" -m pip install --no-cache-dir "$wheel_url"
}

process_venv() {
  local venv_path="$1"
  local python="$venv_path/bin/python"
  local old_wheel_url=""

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

  if ! prepare_pip "$python" "$venv_path"; then
    FAILED=$((FAILED + 1))
    return
  fi

  if ! old_wheel_url="$(pypi_wheel_url "$old_version")"; then
    echo "[WARN] Could not resolve PyPI wheel for rollback version ${old_version}"
  fi

  if ! "$python" -m pip uninstall -y pgconnect; then
    echo "[FAIL] Could not uninstall pgconnect in $venv_path"
    FAILED=$((FAILED + 1))
    return
  fi

  echo "          installing from PyPI wheel (bypasses stale pip index)..."
  if ! install_pgconnect_wheel "$python" "$TARGET_WHEEL_URL"; then
    echo "[FAIL] Could not install pgconnect ${TARGET_VERSION} in $venv_path"
    if [[ -n "$old_wheel_url" ]]; then
      echo "[ROLLBACK] Restoring pgconnect ${old_version}"
      if install_pgconnect_wheel "$python" "$old_wheel_url"; then
        echo "[OK] Restored pgconnect ${old_version}"
      else
        echo "[FAIL] Rollback failed. Install manually:"
        echo "       $python -m pip install --no-cache-dir $old_wheel_url"
      fi
    fi
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
echo " Wheel URL: $TARGET_WHEEL_URL"
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
