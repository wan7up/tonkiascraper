import csv
import os

def generate_tvo():
    # --- 配置区域 ---
    INPUT_CSV = "data.csv"
    OUTPUT_M3U = "tvo.m3u"
    
    # 想要的频道顺序 (这些既是搜索词，也是最终显示的频道名)
    TARGET_CHANNELS = ["翡翠台", "无线新闻", "TVB PLUS", "VIU", "广东体育"]
    # ----------------
    
    print(f"🚀 开始生成定制列表: {OUTPUT_M3U}")

    # 1. 读取 CSV 文件
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 错误: 找不到 {INPUT_CSV}")
        return

    all_data = []
    # 使用 utf-8-sig 防止 Windows 的 BOM 字符问题
    with open(INPUT_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        # 自动识别列名 (防止大小写或空格问题)
        headers = reader.fieldnames
        if not headers:
            print("❌ CSV 文件为空！")
            return
            
        # 找到正确的列名 (你的文件里应该是 'Channel', 'URL', 'Date')
        channel_col = next((h for h in headers if h.strip().lower() == 'channel'), None)
        url_col = next((h for h in headers if h.strip().lower() == 'url'), None)
        date_col = next((h for h in headers if h.strip().lower() == 'date'), None)
        
        # 如果找不到 Channel 列，尝试找 Name 列兼容
        if not channel_col:
            channel_col = next((h for h in headers if h.strip().lower() == 'name'), None)

        if not channel_col or not url_col:
            print(f"❌ 无法识别列名! 检测到的表头: {headers}")
            return

        for row in reader:
            # 标准化数据
            all_data.append({
                'Channel': row.get(channel_col, ''),
                'URL': row.get(url_col, ''),
                'Date': row.get(date_col, '1970-01-01')
            })

    # 2. 准备生成 M3U
    m3u_lines = ["#EXTM3U"]
    count = 0

    # 3. 按指定顺序遍历
    for target in TARGET_CHANNELS:
        # 3.1 筛选逻辑
        # 在 'Channel' 列中查找包含目标词的行 (不区分大小写)
        matches = []
        for row in all_data:
            channel_name = row['Channel']
            if target.lower() in channel_name.lower():
                matches.append(row)
        
        # 3.2 【VIU 特殊过滤】
        # 如果是 VIU，剔除包含 "6" 或 "SIX" 的
        if target == "VIU":
            filtered_matches = []
            for item in matches:
                c_name = item['Channel'].upper()
                # 检查是否含有 6 或 SIX
                if '6' not in c_name and 'SIX' not in c_name:
                    filtered_matches.append(item)
            matches = filtered_matches

        if not matches:
            continue

        # 3.3 排序逻辑
        # 权重1: URL 里有 jdshipin (True排前)
        # 权重2: 日期 (越新排前)
        matches.sort(
            key=lambda x: ("jdshipin" in x['URL'], x['Date']), 
            reverse=True
        )

        # 3.4 写入数据 (使用 target 作为频道名)
        for item in matches:
            m3u_lines.append(f"#EXTINF:-1,{target}")
            m3u_lines.append(item['URL'])
            count += 1

    # 4. 保存
    with open(OUTPUT_M3U, 'w', encoding='utf-8') as f:
        f.write("\n".join(m3u_lines))
    
    print(f"✅ 生成完毕！已保存 {count} 个频道到 {OUTPUT_M3U}")

if __name__ == "__main__":
    generate_tvo()
