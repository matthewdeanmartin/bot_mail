#!/usr/bin/env bash
# Smoke test
set -ou pipefail

PASS=0
FAIL=0
CLI_PYTHON="${PYTHON:-python}"

run_cli() {
    "$CLI_PYTHON" -m bot_mail "$@"
}

check() {
    local desc="$1"
    shift
    if "$@" > /dev/null 2>&1; then
        echo "  PASS: $desc"
        ((PASS++))
    else
        echo "  FAIL: $desc  (cmd: $*)"
        ((FAIL++))
    fi
}

echo "=== bot_mail basic_checks ==="
echo ""
echo "using: ${CLI_PYTHON} -m bot_mail"
echo ""

echo "--- global flags ---"
check "bot_mail --help"    run_cli --help

echo ""
echo "=== Results: ${PASS} passed, ${FAIL} failed ==="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
