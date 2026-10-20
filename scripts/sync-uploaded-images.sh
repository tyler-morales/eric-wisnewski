#!/usr/bin/env sh
# Sync CMS uploads from assets to static so /images/uploads/* and /audio/uploads/* resolve.
# Pages CMS writes to assets/, including subfolders writers create. Hugo publishes static/
# as original bytes (no resize), which is what keeps multi-megabyte JPEGs intact.
set -e
sync_uploads() {
  src=$1
  dest=$2
  mkdir -p "$dest"
  if [ -d "$src" ]; then
    cp -R "$src"/. "$dest"/
  fi
}
sync_uploads assets/images/uploads static/images/uploads
sync_uploads assets/audio/uploads static/audio/uploads
