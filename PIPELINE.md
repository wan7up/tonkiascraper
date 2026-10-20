# 实现流程（Muse 云端采集管线）

自 2026-10-20 起，本仓库的数据由 Muse 云端全自动管线维护，不再依赖 GitHub Actions 直接采集
（旧方案因长期过不了 tonkiang.us 的人机验证已废弃，相关文件已清理）。

## 数据流

```
tonkiang.us（站内搜索）
  → Muse 定时任务 tonkiang-daily-collect（每日约 06:10，7 关键词逐个浏览器采集）
  → runs/query-*.json（原始采集结果）
  → runs/latest-results.json（汇总）
  → node scripts/merge_results.mjs（合并 + 筛选）
  → data.csv / data/streams.json / tvo.m3u / runs/<日期>.md（运行日志）
  → 推送 data.csv 到本仓库 main 分支
  → GitHub Actions（每日 08:00 北京时间）运行 generate_tvo.py
  → tvo.m3u（播放列表，每频道最多 6 条）
```

`data.csv` 是核心交付物：列为 `Keyword,Channel,Date,URL`，**写入前已做完所有筛选**，
拿到即最终结果，无需二次处理。

## 采集规则（浏览器任务）

- 7 个关键词：`翡翠台`、`无线新闻`、`TVB PLUS`、`VIU`、`广东体育`、`CCTV5`、`CCTV5+`
  （Now Sports 精選已于 2026-10-20 永久移除，不再采集）。
- 每个关键词取搜索结果前 3 页，记录 Channel（原样）、Date（检测日期→YYYY-MM-DD）、URL（原样）。
- 只读搜索列表页：不点外部站点、不播放视频、不下载文件。
- 遇到 "Not a Robot?" reCAPTCHA：交给 bot-challenge 专家解决，不要反复自试。
- 分页 bug 规避（tonkiang.us 已知 bug）：若搜索只显示约 3 条且翻页无变化，
  先回搜索框重新提交一次搜索恢复正常列表；翻页必须用站内分页按钮
  （站点自动附加会话令牌 `l=` 参数），**不要**直接拼 `?page=N&keyword=…` 的 URL；
  `CCTV5+` 在 URL 中必须编码为 `CCTV5%2B`，否则 `+` 被当成空格返回 CCTV5 的结果。
- 单个关键词采集失败时保留上次的 `runs/query-*.json`，记因后继续下一个，不中断整轮。

## 筛选规则（merge_results.mjs，写入 data.csv 前强制执行）

| 规则 | 配置位置 | 说明 |
|---|---|---|
| 30 天保留 | `config/channels.json` → `daysLimit` | 站点检测日期早于运行日期 30 天的丢弃（含无日期的） |
| 每频道 ≤20 条 | `config/channels.json` → `maxPerKeyword` | 按关键词分组，取日期最新的 20 条 |
| 频道排除 | `config/channels.json` → `excludeNameIncludes` | 翡翠台排除含"华丽"/"北美"；VIU 排除含"6"/"SIX" |
| 去重 | — | 以 URL 为键，已存在的更新日期/最后出现时间 |

匹配逻辑统一在 `scripts/stream_utils.mjs` 的 `channelMatchesChannel` /
`excludedByChannelRules`，播放列表生成（`generate_playlist.mjs`）与合并共用同一份实现。

## 成功实施的必备条件

1. **tonkiang.us 可访问**：云端浏览器 egress 出口正常，能打开站点搜索页。
2. **人机验证可解**：reCAPTCHA 出现时 bot-challenge 专家可用；若连续解不开，
   当轮该关键词跳过（保留旧数据），不视为整轮失败。
3. **GitHub 连接器保持授权**：Muse GitHub App 对 `wan7up/tonkiascraper` 有写入权限；
   推送为写操作，可能触发用户审批卡，需及时批准（否则 data.csv 停留在旧版本，
   但本地采集与合并不受影响）。
4. **定时任务启用**：`tonkiang-daily-collect`（cron，每日约 06:10）保持启用；
   单轮约需 1 小时（7 关键词串行，含验证码等待）。
5. **配置一致**：`config/channels.json` 的 7 个频道、`daysLimit`、`maxPerKeyword`、
   `excludeNameIncludes` 为筛选的唯一依据，改规则只改这一处。

## 故障与预期行为

- 某关键词采集失败 → 该频道沿用昨日数据，次日自动重试；data.csv 不会因此丢失该频道。
- 合并是增量式的：`--replace` 之外，新一轮只新增/更新，删除只发生在筛选规则命中时。
- GitHub Actions 的 `generate_tvo.yml` 只负责从 data.csv 生成 `tvo.m3u`，
  不做任何采集；它的运行时间（08:00）晚于 data.csv 推送（约 06:10），顺序有保障。
- `tv.txt` 为旧采集器的遗留产物，已不再生成；如需文本版列表可从 data.csv 派生。

## 本地复现（手动跑一轮）

```bash
cd ~/workspace/live-stream-scraper/scraper
# 1) 采集（浏览器任务，见上文采集规则）→ 更新 runs/query-*.json
# 2) 重建 runs/latest-results.json（queries[].items 键名：Keyword/Channel/Date/URL）
# 3) 合并筛选
node scripts/merge_results.mjs
# 4) 推送 data.csv 到 GitHub（先取远端 SHA 再 create_or_update_file，分支 main）
```
