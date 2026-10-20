import csv
import os

def generate_tvo():
    # --- 1. 核心配置区域 (直接写死 LOGO 和 EPG 名字) ---
    INPUT_CSV = "data.csv"
    OUTPUT_M3U = "tvo.m3u"
    EPG_URL = "https://raw.githubusercontent.com/fanmingming/live/main/e.xml"
    MAX_COUNT_PER_CHANNEL = 6

    # 格式： "CSV搜索关键词": {"显示名称": "xxx", "logo": "xxx"}
    # 注意：字典的顺序决定了最终 M3U 的频道顺序
    CHANNEL_CONFIG = {
        "翡翠台": {
            "display_name": "翡翠台",
            "logo": "https://raw.githubusercontent.com/fanmingming/live/main/tv/翡翠台.png"
        },
        "无线新闻": {
            "display_name": "无线新闻",
            "logo": "https://raw.githubusercontent.com/fanmingming/live/main/tv/无线新闻台.png"
        },
        "TVB PLUS": {
            "display_name": "TVBPlus",
            "logo": "https://raw.githubusercontent.com/fanmingming/live/main/tv/TVBPlus.png"
        },
        "VIU": {  
            # 搜索时用 "VIU"，但生成时改名为 "VIUTV" 以匹配 EPG 和 Logo
            "display_name": "VIUTV", 
            "logo": "https://raw.githubusercontent.com/fanmingming/live/main/tv/viutv.png"
        },
        "广东体育": {
            "display_name": "广东体育",
            "logo": "https://raw.githubusercontent.com/fanmingming/live/main/tv/广东体育.png"
        },
        "CCTV5": {
            "display_name": "CCTV5",
            "logo": "https://logo.catvod.com/CCTV5.png"
        },
        "CCTV5+": {
            "display_name": "CCTV5+",
            "logo": "https://logo.catvod.com/CCTV5+.png"
        }
    }
    # -----------------------------------------------
    
    print(f"🚀 开始生成定制列表: {OUTPUT_M3U}")

    # 2. 读取 CSV
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 错误: 找不到 {INPUT_CSV}")
        return

    all_data = []
    with open(INPUT_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        # 自动识别表头
        headers = reader.fieldnames
        if not headers: return
            
        # 模糊匹配列名
        channel_col = next((h for h in headers if h.strip().lower() in ['channel', 'name']), None)
        url_col = next((h for h in headers if h.strip().lower() == 'url'), None)
        date_col = next((h for h in headers if h.strip().lower() == 'date'), None)

        if not channel_col or not url_col:
            print(f"❌ 列名识别失败: {headers}")
            return

        for row in reader:
            all_data.append({
                'Channel': row.get(channel_col, ''),
                'URL': row.get(url_col, ''),
                'Date': row.get(date_col, '1970-01-01')
            })

    # 3. 准备生成内容
    m3u_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
    total_count = 0

    # 4. 遍历配置字典
    for search_key, config in CHANNEL_CONFIG.items():
        display_name = config['display_name'] # 最终显示的名字 (如 VIUTV)
        logo_url = config['logo']             # LOGO 地址
        
        # 4.1 筛选: 用 search_key (如 "VIU") 去 CSV 里找
        matches = []
        for row in all_data:
            if search_key.lower() in row['Channel'].lower():
                matches.append(row)
        
        # 4.2 特殊过滤 (VIU 剔除 6/SIX；CCTV5 剔除 CCTV5+，避免子串匹配串台)
        if search_key == "VIU":
            filtered_matches = []
            for item in matches:
                c_name = item['Channel'].upper()
                if '6' not in c_name and 'SIX' not in c_name:
                    filtered_matches.append(item)
            matches = filtered_matches
        if search_key == "CCTV5":
            matches = [item for item in matches if 'CCTV5+' not in item['Channel'].upper()]

        if not matches:
            continue

        # 4.3 排序: jdshipin 优先 > 日期降序
        matches.sort(
            key=lambda x: ("jdshipin" in x['URL'], x['Date']), 
            reverse=True
        )

        # 4.4 截取前 MAX_COUNT_PER_CHANNEL 个
        matches = matches[:MAX_COUNT_PER_CHANNEL]

        # 4.5 写入 M3U
        for item in matches:
            # 这里的 display_name 同时用于 tvg-name 和频道显示名
            # 这样既能匹配 EPG，又能显示好看的名字
            line = f'#EXTINF:-1 tvg-name="{display_name}" tvg-logo="{logo_url}" group-title="精选频道",{display_name}'
            m3u_lines.append(line)
            m3u_lines.append(item['URL'])
            total_count += 1

    # 5. 保存文件
    with open(OUTPUT_M3U, 'w', encoding='utf-8') as f:
        f.write("\n".join(m3u_lines))
    
    print(f"✅ 生成完毕！已写入 {total_count} 个频道到 {OUTPUT_M3U}")

if __name__ == "__main__":
    generate_tvo()
