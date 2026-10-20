#!/usr/bin/env bash
# Print medical-aegis issue #1 comments newer than the last one we answered.
# Usage: bash scripts/issue_inbox.sh [since_iso]   (default: read from docs/interfaces/issue_last_seen.txt)
SINCE=${1:-$(cat "$(dirname "$0")/../docs/interfaces/issue_last_seen.txt" 2>/dev/null || echo 1970-01-01T00:00:00Z)}
gh api "repos/chancanmakeit/medical-aegis/issues/1/comments?per_page=100" \
  --jq ".[] | select(.created_at > \"$SINCE\") | \"=== \(.id) \(.created_at)\n\(.body)\n\""
gh api "repos/chancanmakeit/Medhypertrace/issues?state=open" --jq '.[] | "Medhypertrace issue #\(.number): \(.title)"'
