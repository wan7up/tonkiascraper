#!/bin/bash

# --- 配置 ---
SOURCE="/mnt/media/data.csv"
TARGET_DIR="/root/tv_scraper"

# --- 1. 搬运文件 ---
if [ -f "$SOURCE" ]; then
    cp -f "$SOURCE" "$TARGET_DIR/"
else
    echo "⚠️  /mnt/media 没找到 data.csv，停止运行。"
    exit 1
fi

# --- 2. Git 智能同步 ---
cd "$TARGET_DIR"

# 设置安全目录
git config --global --add safe.directory "$TARGET_DIR"

# 【第一步：先登记本地所有变化】
# 不管是 data.csv 变了，还是脚本变了，全部先存入本地暂存区
# 这样就不会报 "unstaged changes" 错误了
git add .

# 【第二步：提交本地版本】
# 即使没变化，这步报错也无所谓，继续往下走
git commit -m "Auto update: $(date '+%Y-%m-%d %H:%M:%S')" > /dev/null 2>&1

# 【第三步：拉取 GitHub 的变化】
# --rebase: 把你的新数据“嫁接”到 GitHub 最新版本之后
# -X theirs: 如果万一 data.csv 都有修改，以 Github 的为准？不，这里我们通常不用加参数，
# 让 Git 自动合并。如果你重命名了文件，Git 会自动识别。
git pull origin main --rebase

# 【第四步：推送】
git push origin main