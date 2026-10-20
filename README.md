# tonkiascraper

直播源自动采集与发布。7 个频道：翡翠台、无线新闻、TVB PLUS、VIU、广东体育、CCTV5、CCTV5+。

## 数据流

```
Muse 云端每日 06:10 自动采集 tonkiang.us（浏览器采集，可过人机验证）
        ↓ 合并 + 筛选：只保留 30 天内、每频道 ≤20 条、剔除排除频道（华丽/SIX 等）
    data.csv            ← 筛选后的最终源列表（本仓库的核心交付物）
        ↓ GitHub Actions 每日 08:00 运行 generate_tvo.py
    tvo.m3u             ← 播放列表（每频道最多 6 条，jdshipin 优先、日期倒序）
```

## 文件说明

| 文件 | 说明 |
|---|---|
| `data.csv` | 筛选后的直播源（`Keyword,Channel,Date,URL`），由采集任务推送 |
| `generate_tvo.py` | 从 data.csv 生成 tvo.m3u 的脚本 |
| `tvo.m3u` | 自动生成的播放列表（含 EPG、台标） |
| `.github/workflows/generate_tvo.yml` | 每日 08:00（北京时间）自动生成 tvo.m3u，也可手动触发 |

## 历史

- 2026-10 之前：GitHub Actions 直接采集，因长期过不了 tonkiang.us 的人机验证而废弃（相关文件已清理）。
- 2026-10-20 起：改由 Muse 云端浏览器采集 + 自动筛选，data.csv 即最终结果。
