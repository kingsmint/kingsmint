#!/bin/sh
# Builds the app's web page in dist/: Vite bundles ui/ (vite.config.js), then the files Vite does not bundle are copied:
# Web Awesome, which its loader fetches from /vendor/, Lucide's icons for <wa-icon>, and i18n.json, which the server reads for its pages.
set -eu
cd "$(dirname "$0")/.."
[ -d ui/node_modules ] || (cd ui && npm ci --silent)
(cd ui && npx vite build --logLevel error)
# Web Awesome: only its build for the browser (dist-cdn), the package has others
mkdir -p dist/vendor/@awesome.me/webawesome
cp -R ui/node_modules/@awesome.me/webawesome/dist-cdn dist/vendor/@awesome.me/webawesome/
mkdir -p dist/vendor/lucide-static
cp -R ui/node_modules/lucide-static/icons dist/vendor/lucide-static/
cp ui/i18n.json dist/
# the Claude app's extension, which the app offers to install (claude_extension in main.rs); with the developer's uv
# or the sidecar of this machine (scripts/fetch-sidecars.sh)
UV=$(command -v uv || ls src-tauri/binaries/uv-"$(rustc -vV | sed -n 's/^host: //p')"* | head -1)
"$UV" run --no-project --python '>=3.11' python ../desktop/build.py dist >/dev/null
rm dist/kingsmint.plugin
