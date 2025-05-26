#!/usr/bin/env sh
set -e

if [ -n "$CDS_API_KEY" ]; then
  # ensure home exists & write .cdsapirc
  mkdir -p "$HOME"
  {
    echo "url: https://ads.atmosphere.copernicus.eu/api"
    echo "key: $CDS_API_KEY"
  } > "$HOME/.cdsapirc"
  chmod 600 "$HOME/.cdsapirc"
fi

# finally hand off to CMD
exec "$@"