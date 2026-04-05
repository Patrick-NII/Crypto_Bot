#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://localhost:8000/api/v1}"
export NEXT_PUBLIC_AI_URL="${NEXT_PUBLIC_AI_URL:-http://localhost:8008/api/v1}"
export NEXT_PUBLIC_BINANCE_PROXY_URL="${NEXT_PUBLIC_BINANCE_PROXY_URL:-http://localhost:3001}"
exec node node_modules/.bin/next dev "$@"
