#!/usr/bin/env bash
# Test the desktop app's printing through a REAL system print queue (CUPS) on Linux:
# a raw queue "POS-80" that sends to a fake network thermal printer on 127.0.0.1:$PORT.
# The Rust test opens / closes that fake printer itself (on, off, paused queue).
#   sudo apt-get install -y cups cups-client cups-bsd libcups2-dev
#   bash infrastructure/scripts/test-print-queue.sh          (as root)
#   SUDO=sudo bash infrastructure/scripts/test-print-queue.sh (CI runner)
set -euo pipefail
PORT="${LUXE_PRINT_QUEUE_PORT:-19100}"
SUDO="${SUDO:-}"
pgrep -x cupsd >/dev/null || { $SUDO cupsd 2>/dev/null || $SUDO service cups start; sleep 2; }
$SUDO lpadmin -x POS-80 2>/dev/null || true
$SUDO lpadmin -p POS-80 -E -v "socket://127.0.0.1:${PORT}" -m raw -D "POS-80 thermal (test)"
cd "$(dirname "$0")/../../apps/desktop-cms/src-tauri"
trap '$SUDO lpadmin -x POS-80 2>/dev/null || true' EXIT
SUDO="$SUDO" LUXE_PRINT_QUEUE_PORT="$PORT" cargo test system_print_queue_end_to_end -- --ignored --nocapture
