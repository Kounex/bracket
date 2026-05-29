#!/bin/sh
cat > /app/dist/config.js <<EOF
window.__BRACKET_CONFIG__ = {
  API_BASE_URL: "${API_BASE_URL:-}"
};
EOF

exec "$@"
