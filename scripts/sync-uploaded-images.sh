#!/usr/bin/env sh
# Sync CMS uploads from assets to static so /images/uploads/* resolve at build and on live.
# Pages CMS writes to assets/images/uploads; Hugo only publishes static/ to output.
set -e
mkdir -p static/images/uploads
if [ -d "assets/images/uploads" ]; then
  for f in assets/images/uploads/*; do
    [ -f "$f" ] && cp "$f" static/images/uploads/
  done
fi
