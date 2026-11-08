#!/bin/sh
# App container start (Cloud Run). Puts the POST /api/ask route to the QueryService into the nginx
# config, starts the drive-time cache refresh, then runs nginx in the foreground.
# QUERY_SERVICE_URL is read here at start, so the image holds no service address.
set -eu

conf=/etc/nginx/nginx.conf
url=${QUERY_SERVICE_URL:-}
url=${url%/}

if [ -z "$url" ]; then
  echo "QUERY_SERVICE_URL is not set: /api/ask returns 503, and the App uses its built-in filters." >&2
  route='location = /api/ask { return 503; }'
elif printf '%s' "$url" | grep -Eq '^https?://[A-Za-z0-9.-]+(:[0-9]+)?$'; then
  host=${url#*://}
  host=${host%%:*}
  # The QueryService refuses bodies over 16,384 bytes; its own deadline is under 60 s.
  route="location = /api/ask { client_max_body_size 16k; proxy_pass $url/api/ask; proxy_http_version 1.1; proxy_ssl_server_name on; proxy_set_header Host $host; proxy_read_timeout 60s; }"
else
  echo "QUERY_SERVICE_URL must be http(s)://host[:port] with no path or query." >&2
  exit 1
fi

sed -i "s|#@QUERY_SERVICE_ROUTE@|$route|" "$conf"

node scripts/cache-drive-times.ts --watch &
exec nginx -g 'daemon off;'
