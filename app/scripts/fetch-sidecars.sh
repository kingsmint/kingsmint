#!/bin/sh
# Downloads the binaries the app ships as sidecars (uv, jj), for this machine's Rust target (macOS, Linux), or for the
# target given (the release's universal Mac app takes both Mac targets).
set -eu
UV_VERSION=0.13.8
JJ_VERSION=0.47.1
TARGET=${1:-$(rustc -vV | sed -n 's/^host: //p')}
DEST="$(dirname "$0")/../src-tauri/binaries"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$DEST"

curl -fsSL "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-$TARGET.tar.gz" | tar -xz -C "$TMP"
mv "$TMP/uv-$TARGET/uv" "$DEST/uv-$TARGET"

# jj publishes musl builds for Linux
JJ_TARGET=$(echo "$TARGET" | sed 's/-unknown-linux-gnu$/-unknown-linux-musl/')
curl -fsSL "https://github.com/jj-vcs/jj/releases/download/v$JJ_VERSION/jj-v$JJ_VERSION-$JJ_TARGET.tar.gz" | tar -xz -C "$TMP"
mv "$(find "$TMP" -type f -name jj | head -1)" "$DEST/jj-$TARGET"

# a binary of another target may not run here
if [ $# -eq 0 ]; then
  "$DEST/uv-$TARGET" --version
  "$DEST/jj-$TARGET" --version
fi
