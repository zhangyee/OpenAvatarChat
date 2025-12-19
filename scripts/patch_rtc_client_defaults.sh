#!/bin/bash
# 修改 rtc_client 默认设置：关闭摄像头、打开聊天框
# 直接修改构建后的 dist 文件，无需重新构建

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$PROJECT_ROOT/src/handlers/client/rtc_client/frontend/dist/assets"

INDEX_JS="$DIST_DIR/index.js"
INDEX_LEGACY_JS="$DIST_DIR/index-legacy.js"

# 检查文件是否存在
if [ ! -f "$INDEX_JS" ]; then
    echo "Error: File not found: $INDEX_JS"
    exit 1
fi

if [ ! -f "$INDEX_LEGACY_JS" ]; then
    echo "Error: File not found: $INDEX_LEGACY_JS"
    exit 1
fi

# 备份
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
cp "$INDEX_JS" "${INDEX_JS}.backup.${TIMESTAMP}"
cp "$INDEX_LEGACY_JS" "${INDEX_LEGACY_JS}.backup.${TIMESTAMP}"
echo "Backup created with timestamp: ${TIMESTAMP}"

echo "Patching index.js..."
sed -i '66028s/cameraOff: !1,/cameraOff: !0,/' "$INDEX_JS"
sed -i '66033s/showChatRecords: !1,/showChatRecords: !0,/' "$INDEX_JS"
sed -i '66046s/(this\.cameraOff = !1),/(this.cameraOff = !0),/' "$INDEX_JS"

echo "Patching index-legacy.js..."
sed -i '85653s/cameraOff: !1,/cameraOff: !0,/' "$INDEX_LEGACY_JS"
sed -i '85658s/showChatRecords: !1,/showChatRecords: !0,/' "$INDEX_LEGACY_JS"
sed -i '85682s/(e\.cameraOff = !1),/(e.cameraOff = !0),/' "$INDEX_LEGACY_JS"

echo ""
echo "Patching completed successfully!"
echo ""
echo "Changes made:"
echo "  index.js (L66028,66033,66046): cameraOff/showChatRecords !1->!0"
echo "  index-legacy.js (L85653,85658,85682): cameraOff/showChatRecords !1->!0"
echo ""
echo "No build required! Just restart the server."
