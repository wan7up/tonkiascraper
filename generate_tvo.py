import csv
import os

def generate_tvo():
    # --- 配置区域 ---
    INPUT_CSV = "data.csv"
    OUTPUT_M3U = "tvo.m3u"
    
    # EPG 地址 (Fanmingming)
    EPG_URL = "https://raw.githubusercontent.com/fanmingming/live/main/e.xml"

    # 想要的频道顺序
    # 注意：这些名字将作为 tvg-name 用于匹配 EPG，请尽量使用标准台名
    TARGET_CHANNELS = ["翡翠台", "无线新闻", "TVB PLUS", "VIU", "广东体育"]
    
    # 每个频道保留的最大数量
    MAX_COUNT_PER_CHANNEL = 10
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
        
        # 自动识别列名
        headers = reader.fieldnames
        if not headers:
            print("❌ CSV 文件为空！")
            return
            
        # 找到正确的列名
        channel_col = next((h for h in headers if h.strip().lower() == 'channel'), None)
        url_col = next((h for h in headers if h.strip().lower() == 'url'), None)
        date_col = next((h for h in headers if h.strip().lower() == 'date'), None)
        
        # 兼容性处理
        if not channel_col:
            channel_col = next((h for h in headers if h.strip().lower() == 'name'), None)

        if not channel_col or not url_col:
            print(f"❌ 无法识别列名! 检测到的表头: {headers}")
            return

        for row in reader:
            all_data.append({
                'Channel': row.get(channel_col, ''),
                'URL': row.get(url_col, ''),
                'Date': row.get(date_col, '1970-01-01')
            })

    # 2. 准备生成 M3U
    # 【新增】在头部添加 x-tvg-url 引用 EPG
    m3u_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
    
    total_count = 0

    # 3. 按指定顺序遍历
    for target in TARGET_CHANNELS:
        # 3.1 筛选逻辑
        matches = []
        for row in all_data:
            if target.lower() in row['Channel'].lower():
                matches.append(row)
        
        # 3.2 VIU 特殊过滤 (剔除 6 或 SIX)
        if target == "VIU":
            filtered_matches = []
            for item in matches:
                c_name = item['Channel'].upper()
                if '6' not in c_name and 'SIX' not in c_name:
                    filtered_matches.append(item)
            matches = filtered_matches

        if not matches:
            continue

        # 3.3 排序逻辑 (jdshipin优先 > 日期降序)
        matches.sort(
            key=lambda x: ("jdshipin" in x['URL'], x['Date']), 
            reverse=True
        )

        # 3.4 【新增】只保留前 N 个
        matches = matches[:MAX_COUNT_PER_CHANNEL]

        # 3.5 写入数据
        for item in matches:
            # 【新增】添加 tvg-name="{target}" 以匹配 EPG
            # 如果不加这个，播放器不知道这个台对应 EPG 里的哪一个
            line_info = f'#EXTINF:-1 tvg-name="{target}" group-title="精选频道",{target}'
            m3u_lines.append(line_info)
            m3u_lines.append(item['URL'])
            total_count += 1

    # 4. 保存
    with open(OUTPUT_M3U, 'w', encoding='utf-8') as f:
        f.write("\n".join(m3u_lines))
    
    print(f"✅ 生成完毕！每个频道限制 {MAX_COUNT_PER_CHANNEL} 个，共 {total_count} 个源，已保存至 {OUTPUT_M3U}")

if __name__ == "__main__":
    generate_tvo()
