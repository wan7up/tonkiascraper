import csv
import os

def generate_tvo():
    # --- 配置区域 ---
    INPUT_CSV = "data.csv"
    OUTPUT_M3U = "tvo.m3u"
    
    # 频道顺序列表
    TARGET_CHANNELS = ["翡翠台", "无线新闻", "TVB PLUS", "VIU", "广东体育"]
    # ----------------
    
    print(f"🚀 开始生成定制列表: {OUTPUT_M3U}")

    # 1. 读取数据库
    all_data = []
    if os.path.exists(INPUT_CSV):
        with open(INPUT_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                all_data.append(row)
    else:
        print(f"❌ 找不到 {INPUT_CSV}，请确保先运行主抓取程序。")
        return

    # 2. 准备写入内容
    m3u_lines = ["#EXTM3U"]
    count = 0

    # 3. 严格按照指定顺序遍历
    for target_name in TARGET_CHANNELS:
        # 3.1 初步筛选：名字包含关键词的
        matches = [row for row in all_data if target_name in row['Name']]
        
        # 3.2 【特殊过滤】如果是 VIU，剔除带 6 或 SIX 的
        if target_name == "VIU":
            filtered_matches = []
            for item in matches:
                # 转大写比较，防止 Six, six, SIX 大小写不一致
                name_upper = item['Name'].upper()
                if '6' not in name_upper and 'SIX' not in name_upper:
                    filtered_matches.append(item)
            matches = filtered_matches

        # 如果这个台没源，就跳过
        if not matches:
            continue

        # 3.3 排序逻辑
        # 优先级 1: URL包含 "jdshipin" (True > False)
        # 优先级 2: Date (字符串比较，越新越大)
        # reverse=True 表示大的排前面
        matches.sort(
            key=lambda x: ("jdshipin" in x['URL'], x['Date']), 
            reverse=True
        )

        # 3.4 写入数据
        for item in matches:
            # 统一重命名为 target_name (例如 "翡翠台")
            m3u_lines.append(f"#EXTINF:-1,{target_name}")
            m3u_lines.append(item['URL'])
            count += 1

    # 4. 保存文件
    with open(OUTPUT_M3U, 'w', encoding='utf-8') as f:
        f.write("\n".join(m3u_lines))
    
    print(f"✅ 生成完毕！共包含 {count} 个频道，已保存为 {OUTPUT_M3U}")

if __name__ == "__main__":
    generate_tvo()
