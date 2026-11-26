#!/usr/bin/env bash
# Wait until the CI workflow (ci.yml) has finished on a commit; succeed only if it passed.
#
# Usage: wait-for-ci.sh <commit-sha>     (needs GH_TOKEN and GITHUB_REPOSITORY)
#
# Waits for the whole CI run, not for one check: the gate check "CI complete" is only
# created once the other CI jobs end, so a deploy started right after a push (a tag on
# a fresh merge) found no such check and stopped at once (v1.0.0, 2026-11-15).
set -euo pipefail

SHA="${1:?commit sha}"
REPO="${GITHUB_REPOSITORY:?}"
INTERVAL="${WAIT_INTERVAL:-20}"
MAX_WAIT="${MAX_WAIT:-5400}"          # 90 min: CI takes ~20 min
NO_RUN_GRACE="${NO_RUN_GRACE:-600}"    # a CI run must exist within 10 min of the start

start=$(date +%s)
while :; do
  elapsed=$(( $(date +%s) - start ))
  # One line per CI run on this commit: "<status> <conclusion>"
  # Filters out pull_request events so the gate evaluates only the deployed commit's push / dispatch runs.
  # Only the LATEST run counts (a re-run that failed after an earlier success means "not passing").
  # A GitHub API hiccup (5xx, rate limit) is not a CI result: wait and ask again.
  if ! runs=$(gh api "repos/$REPO/actions/workflows/ci.yml/runs?head_sha=$SHA&per_page=50" \
           --jq '[.workflow_runs[] | select(.event != "pull_request")] | sort_by(.created_at) | last
                 | if . == null then empty else "\(.status) \(.conclusion // "-")" end' 2>/dev/null); then
    if [ "$elapsed" -ge "$MAX_WAIT" ]; then
      echo "::error::GitHub API unreachable and CI not confirmed on $SHA after ${MAX_WAIT}s."
      exit 1
    fi
    echo "GitHub API did not answer; asking again in ${INTERVAL}s"
    sleep "$INTERVAL"
    continue
  fi
  if grep -q '^completed success$' <<<"$runs"; then
    echo "CI passed on $SHA."
    exit 0
  fi
  if [ -n "$runs" ] && ! grep -qv '^completed ' <<<"$runs"; then
    echo "::error::CI finished on $SHA without passing:"; echo "$runs"
    exit 1
  fi
  if [ -z "$runs" ] && [ "$elapsed" -ge "$NO_RUN_GRACE" ]; then
    echo "::error::No CI run found for $SHA after ${NO_RUN_GRACE}s."
    exit 1
  fi
  if [ "$elapsed" -ge "$MAX_WAIT" ]; then
    echo "::error::CI still not finished on $SHA after ${MAX_WAIT}s."
    exit 1
  fi
  echo "CI on $SHA: ${runs:-not started yet} — waiting ${INTERVAL}s"
  sleep "$INTERVAL"
done
