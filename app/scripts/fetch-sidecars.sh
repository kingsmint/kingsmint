#!/bin/sh
# Downloads the binaries the app ships as sidecars (uv, jj), for this machine's Rust target (macOS, Linux, Windows in
# Git Bash), or for the target given (the release's universal Mac app takes both Mac targets).
set -eu
UV_VERSION=0.13.8
JJ_VERSION=0.47.1
TARGET=${1:-$(rustc -vV | sed -n 's/^host: //p')}
DEST="$(dirname "$0")/../src-tauri/binaries"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$DEST"
case "$TARGET" in
  *-windows-*) EXT=.exe ARCHIVE=zip ;;
  *) EXT= ARCHIVE=tar.gz ;;
esac

# fetch <url>: downloads and unpacks the archive into $TMP
fetch() {
  curl -fsSL -o "$TMP/a.$ARCHIVE" "$1"
  if [ "$ARCHIVE" = zip ]; then unzip -qo "$TMP/a.zip" -d "$TMP"; else tar -xzf "$TMP/a.tar.gz" -C "$TMP"; fi
}

fetch "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-$TARGET.$ARCHIVE"
mv "$(find "$TMP" -type f -name "uv$EXT" | head -1)" "$DEST/uv-$TARGET$EXT"

# jj publishes musl builds for Linux
JJ_TARGET=$(echo "$TARGET" | sed 's/-unknown-linux-gnu$/-unknown-linux-musl/')
fetch "https://github.com/jj-vcs/jj/releases/download/v$JJ_VERSION/jj-v$JJ_VERSION-$JJ_TARGET.$ARCHIVE"
mv "$(find "$TMP" -type f -name "jj$EXT" | head -1)" "$DEST/jj-$TARGET$EXT"

# a binary of another target may not run here
if [ $# -eq 0 ]; then
  "$DEST/uv-$TARGET$EXT" --version
  "$DEST/jj-$TARGET$EXT" --version
fi
