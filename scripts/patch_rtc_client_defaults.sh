#!/bin/bash
# 修改 rtc_client 默认设置：关闭摄像头、打开聊天框

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_FILE="$PROJECT_ROOT/src/handlers/client/rtc_client/frontend/src/store/index.ts"

if [ ! -f "$TARGET_FILE" ]; then
    echo "Error: File not found: $TARGET_FILE"
    exit 1
fi

# 备份
BACKUP_FILE="${TARGET_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$TARGET_FILE" "$BACKUP_FILE"
echo "Backup created: $BACKUP_FILE"

# 修改1: 第89行 cameraOff: false -> true
sed -i '89s/cameraOff: false,/cameraOff: true,/' "$TARGET_FILE"

# 修改2: 第94行 showChatRecords: false -> true
sed -i '94s/showChatRecords: false,/showChatRecords: true,/' "$TARGET_FILE"

# 修改3: 第110行 注释掉 accessDevice() 中的 this.cameraOff = false
sed -i '110s/^        this\.cameraOff = false$/        \/\/ this.cameraOff = false/' "$TARGET_FILE"

echo "Patching completed successfully!"
echo ""
echo "Changes made:"
echo "  Line 89:  cameraOff: false -> true"
echo "  Line 94:  showChatRecords: false -> true"
echo "  Line 110: this.cameraOff = false (commented out)"
echo ""
echo "Next steps:"
echo "  cd src/handlers/client/rtc_client/frontend"
echo "  npm run build"
