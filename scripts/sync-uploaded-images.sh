#!/usr/bin/env sh
# Sync CMS uploads from assets to static so /images/uploads/* and /audio/uploads/* resolve.
# Pages CMS writes to assets/; Hugo only publishes static/ to output.
set -e
sync_uploads() {
  src=$1
  dest=$2
  mkdir -p "$dest"
  if [ -d "$src" ]; then
    for f in "$src"/*; do
      [ -f "$f" ] && cp "$f" "$dest/"
    done
  fi
}
sync_uploads assets/images/uploads static/images/uploads
sync_uploads assets/audio/uploads static/audio/uploads
