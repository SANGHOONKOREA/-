#!/usr/bin/env bash
# Install the sketch-to-sld Claude Code skill into the current project
# (or your home dir for global use).
#
# Usage:
#   bash install-skill.sh                     # install to ./.claude/skills/
#   bash install-skill.sh --global            # install to ~/.claude/skills/
set -euo pipefail

DEST_BASE=".claude/skills"
if [[ "${1:-}" == "--global" ]]; then
  DEST_BASE="$HOME/.claude/skills"
fi

REPO="SANGHOONKOREA/-"
BRANCH="claude/image-to-dwg-conversion-kW8ZE"
URL="https://github.com/${REPO}/raw/${BRANCH}/image-to-dwg/output/sketch-to-sld-skill.tar.gz"

mkdir -p "${DEST_BASE}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "Downloading skill from ${URL}"
curl -fsSL "${URL}" -o "${tmp}/skill.tar.gz"
tar -xzf "${tmp}/skill.tar.gz" -C "${DEST_BASE}"
echo "Installed to ${DEST_BASE}/sketch-to-sld/"
echo
echo "Next steps:"
echo "  pip install ezdxf matplotlib pillow opencv-python-headless pytesseract"
echo "  apt-get install tesseract-ocr   # (optional, for OCR cross-check)"
echo
echo "Then in any Claude Code session in this project, ask:"
echo "  '이 이미지를 DWG로 변환해줘 (image attached)'"
echo "and the skill will trigger automatically."
