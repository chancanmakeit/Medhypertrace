#!/usr/bin/env bash
# Print medical-aegis issue comments (ALL issues, not only #1) and newly opened issues newer than the last one we read.
# Usage: bash scripts/issue_inbox.sh [since_iso]   (default: read from docs/interfaces/issue_last_seen.txt)
# Round 65: repo-wide (issue #2 was opened by another agent on 2026-10-27 and the #1-only version missed it);
# --paginate so threads past 100 comments are not truncated.
SINCE=${1:-$(cat "$(dirname "$0")/../docs/interfaces/issue_last_seen.txt" 2>/dev/null || echo 1970-01-01T00:00:00Z)}
R=chancanmakeit/medical-aegis
gh api --paginate "repos/$R/issues?state=all&since=$SINCE&per_page=100" \
  --jq ".[] | select(.created_at > \"$SINCE\") | \"=== NEW ISSUE #\(.number) \(.created_at) [\(.state)] \(.title)\n\(.body)\n\""
gh api --paginate "repos/$R/issues/comments?since=$SINCE&per_page=100" \
  --jq ".[] | select(.created_at > \"$SINCE\") | \"=== #\(.issue_url | split(\"/\") | last) \(.id) \(.created_at)\n\(.body)\n\""
gh api "repos/chancanmakeit/Medhypertrace/issues?state=open" --jq '.[] | "Medhypertrace issue #\(.number): \(.title)"'
# Round 82: always end with an index of every new comment (id, time, length) so a truncated read is visible.
# Rule: only advance issue_last_seen.txt to the newest created_at in THIS index after reading every listed body in full.
echo "=== INDEX (comments since $SINCE)"
gh api --paginate "repos/$R/issues/comments?since=$SINCE&per_page=100" \
  --jq ".[] | select(.created_at > \"$SINCE\") | \"#\(.issue_url | split(\"/\") | last) \(.id) \(.created_at) len=\(.body|length)\""
