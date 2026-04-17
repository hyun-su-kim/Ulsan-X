#!/bin/bash
# PROJECT-STATUS.md에서 14일 이상 된 'done (YYYY-MM-DD)' 항목을 제거
# 사용: ./tools/prune-status.sh [--dry-run]

FILE="$(dirname "$0")/../docs/status/PROJECT-STATUS.md"
DAYS=14
TODAY=$(date +%s)
DRY_RUN=false

[[ "$1" == "--dry-run" ]] && DRY_RUN=true

if [ ! -f "$FILE" ]; then
  echo "ERROR: $FILE not found"
  exit 1
fi

PRUNED=0
while IFS= read -r line; do
  if echo "$line" | grep -qE 'done \([0-9]{4}-[0-9]{2}-[0-9]{2}\)'; then
    date_str=$(echo "$line" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}')
    item_ts=$(date -d "$date_str" +%s 2>/dev/null)
    if [ -z "$item_ts" ]; then
      item_ts=$(date -j -f "%Y-%m-%d" "$date_str" +%s 2>/dev/null)
    fi
    if [ -n "$item_ts" ]; then
      diff_days=$(( (TODAY - item_ts) / 86400 ))
      if [ "$diff_days" -gt "$DAYS" ]; then
        echo "PRUNE ($diff_days days old): $line"
        if [ "$DRY_RUN" = false ]; then
          escaped=$(echo "$line" | sed 's/[[\.*^$()+?{|]/\\&/g')
          sed -i "/$escaped/d" "$FILE"
        fi
        PRUNED=$((PRUNED + 1))
      fi
    fi
  fi
done < "$FILE"

if [ "$PRUNED" -eq 0 ]; then
  echo "Nothing to prune."
elif [ "$DRY_RUN" = true ]; then
  echo "Dry run: $PRUNED item(s) would be pruned."
else
  echo "Pruned $PRUNED item(s) from $FILE"
fi
