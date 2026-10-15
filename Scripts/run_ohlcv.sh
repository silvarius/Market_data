#!/usr/bin/env bash
set -u

VERSION="0-1-0"

DIR="/home/ubuntu/Donnees_import"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$DIR/logs"
DATA_DIR="$DIR/Donnees"
REPORT_DIR="$DIR/Rapports"
mkdir -p "$LOG_DIR" "$DATA_DIR" "$REPORT_DIR"

STAMP="$(date -u +%Y%m%d_%H%M%S)"
DATE_ONLY="$(date -u +%Y-%m-%d)"
REPORT_FILE="$REPORT_DIR/rapport_${DATE_ONLY}.txt"

SCRIPTS=(
  "Hyperliquid/hyperliquid-future-ohlcv-arg.py"
  "Kraken/kraken-future-ohlcv-arg.py"
  "Mexc/mexc-spot-ohlcv-arg.py"
)
overall_status=0

{
  echo "Rapport d'import du ${DATE_ONLY} (run_ohlcv.sh v${VERSION})"
  echo "================================"
} > "$REPORT_FILE"

for script in "${SCRIPTS[@]}"; do
  name="$(basename "${script%.py}")"
  log_file="$LOG_DIR/${name}_${STAMP}.log"
  echo "[$(date -u +%FT%TZ)] Lancement de $script" >> "$log_file"
  /usr/bin/python3 "$SCRIPT_DIR/$script" --out-dir "$DATA_DIR" >> "$log_file" 2>&1
  status=$?
  echo "[$(date -u +%FT%TZ)] $script terminé (code $status)" >> "$log_file"
  if [ "$status" -eq 0 ]; then
    echo "${name}: OK" >> "$REPORT_FILE"
  else
    echo "${name}: ECHEC (code ${status})" >> "$REPORT_FILE"
    overall_status=1
  fi
done

exit "$overall_status"
