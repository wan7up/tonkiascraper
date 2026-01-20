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

# 标准三连：拉取(主分支) -> 添加 -> 提交 -> 推送(主分支)
# 注意：这里加了 -X ours，意思是如果有冲突，以我(本地N1)的文件为准
git pull origin main --rebase -X ours
git add data.csv
git commit -m "Auto update: $(date '+%Y-%m-%d %H:%M:%S')"
git push origin main