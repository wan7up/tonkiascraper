#!/bin/bash

# --- 配置 ---
SOURCE="/mnt/media/data.csv"
TARGET_DIR="/root/tv_scraper"

# --- 1. 搬运文件 ---
if [ -f "$SOURCE" ]; then
    cp -f "$SOURCE" "$TARGET_DIR/"
else
    echo "⚠️  在 /mnt/media 没找到 data.csv，停止运行。"
    exit 1
fi

# --- 2. Git 上传 ---
cd "$TARGET_DIR"

# 防报错配置
git config --global --add safe.directory "$TARGET_DIR"

# 【关键修改】先 Add/Commit，保证工作区干净，然后再 Pull
git add data.csv
git commit -m "Auto update: $(date '+%Y-%m-%d %H:%M:%S')"

# 【关键修改】Pull 在 Commit 之后
# -X theirs 表示：如果有冲突，强制使用“我的(N1)”版本，覆盖 Github 的
git pull origin main --rebase -X theirs

# 最后推送
git push origin main