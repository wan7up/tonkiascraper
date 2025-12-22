from DrissionPage import ChromiumPage, ChromiumOptions
from datetime import datetime, timedelta
import re
import os
import time
import tempfile
import shutil
import csv

# --- 配置部分 ---
KEYWORDS = ["无线新闻", "广东体育", "翡翠台", "VIU", "tvb plus", "NatGeo_twn", "Now Sports 精選", "discoveryhd_twn", "tlc_twn", "國家地理", "hbohd_twn"]
DAYS_LIMIT = 30
DATA_FILE = "data.csv"
M3U_FILE = "tv.m3u"
TXT_FILE = "tv.txt"

def handle_cloudflare(page):
    """(保持原版) 智能处理 Cloudflare"""
    print("🛡️ Checking Cloudflare status...")
    for i in range(10):
        try:
            title = page.title
            if "Just a moment" not in title and ("IPTV" in title or "Search" in title or "Tonkiang" in title):
                print(f"✅ Access Granted! (Title: {title})")
                return True
            time.sleep(3)
        except:
            time.sleep(3)
    print("⚠️ Cloudflare check timed out")
    return False

# --- 读取历史数据 ---
def load_history():
    history = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    history[row['URL']] = {
                        'Channel': row['Channel'],
                        'Date': row['Date'],
                        'Keyword': row['Keyword']
                    }
            print(f"📖 Loaded {len(history)} items from history database.")
        except Exception as e:
            print(f"⚠️ History load failed: {e}")
    return history

# --- 保存数据逻辑 ---
def save_all_files(data_dict):
    try:
        # 1. 保存 CSV
        with open(DATA_FILE, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['Keyword', 'Channel', 'Date', 'URL']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            sorted_items = sorted(data_dict.items(), key=lambda x: x[1]['Keyword'])
            for url, info in sorted_items:
                writer.writerow({
                    'Keyword': info['Keyword'],
                    'Channel': info['Channel'],
                    'Date': info['Date'],
                    'URL': url
                })
        
        # 2. 保存 M3U
        with open(M3U_FILE, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for url, info in data_dict.items():
                f.write(f'#EXTINF:-1 group-title="{info["Keyword"]}",{info["Channel"]}\n{url}\n')

        # 3. 保存 TXT
        with open(TXT_FILE, 'w', encoding='utf-8') as f:
            for url, info in data_dict.items():
                f.write(f'{info["Channel"]},{url}\n')

        print(f"💾 Database updated: {len(data_dict)} total items saved.")
    except Exception as e:
        print(f"❌ Save failed: {e}")

def main():
    # --- 1. 环境配置 ---
    temp_user_dir = tempfile.mkdtemp()
    co = ChromiumOptions()
    co.headless(True)
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument(f'--user-data-dir={temp_user_dir}')
    co.set_argument('--remote-allow-origins=*')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')

    chrome_path = os.getenv('CHROME_PATH')
    if chrome_path:
        co.set_paths(browser_path=chrome_path)

    try:
        page = ChromiumPage(co)
        print("✅ Browser launched successfully!")
    except Exception as e:
        print(f"❌ Browser Init Failed: {e}")
        try: shutil.rmtree(temp_user_dir) 
        except: pass
        return

    # --- 2. 准备数据 ---
    all_data = load_history() 
    current_date = datetime.now()
    cutoff_date = current_date - timedelta(days=DAYS_LIMIT)

    try:
        # --- 3. 循环搜索 ---
        for kw in KEYWORDS:
            print(f"\n🚀 Processing Keyword: {kw}")
            
            try:
                page.get('http://tonkiang.us/')
                handle_cloudflare(page) 
                
                search_input = page.ele('tag:input@@type!=hidden', timeout=5)
                if search_input:
                    search_input.clear()
                    # ⚠️ 保持原版搜索逻辑：输入文字 -> 点击按钮
                    search_input.input(kw)
                    print(f"   - Input keyword: {kw}")
                    
                    try:
                        search_btn = search_input.next('tag:button') or page.ele('tag:button@@type=submit')
                        if search_btn:
                            print("   - Clicking Search Button...")
                            search_btn.click()
                        else:
                            print("   - Button not found, trying Enter...")
                            search_input.input('\n')
                    except Exception as e:
                        print(f"   - Click error: {e}, using Enter fallback.")
                        search_input.input('\n')

                    time.sleep(3) 
                    if len(page.eles('text:://')) <= 8:
                        print("   - Links count low, waiting 3 more seconds...")
                        time.sleep(3)

                else:
                    print(f"❌ Input box not found for {kw}, skipping.")
                    continue

                # --- 提取与更新逻辑 ---
                items = page.eles('text:://')
                new_found_count = 0
                
                print(f"   - Page analysis: Found {len(items)} raw links.")

                for item in items:
                    try:
                        # 1. 提取 URL
                        txt = item.text
                        url_match = re.search(r'((?:http|https|rtmp|rtsp)://[^\s<>"\u4e00-\u9fa5]+)', txt)
                        if not url_match: continue
                        url = url_match.group(1)

                        # 2. 提取日期和台名
                        container = item
                        date_str = ""
                        channel_name = kw # 先默认，后面尝试覆盖
                        
                        # 向上找容器获取更多信息
                        for _ in range(3):
                            container = container.parent()
                            if not container: break
                            
                            # 提取日期
                            if not date_str:
                                mat = re.search(r'(\d{2,4}-\d{1,2}-\d{2,4})', container.text)
                                if mat: date_str = mat.group(1)
                            
                            # 👇👇👇 核心修改：无条件提取真实台名 👇👇👇
                            # 不再检查 kw 是否存在，直接做减法：整行文字 - URL - 日期 = 台名
                            full_text = container.text
                            # 简单粗暴：以 http 切割，取前面部分
                            text_before_url = full_text.split('http')[0]
                            
                            # 如果有日期，把日期也替换为空
                            if date_str:
                                text_before_url = text_before_url.replace(date_str, '')
                            
                            # 去掉首尾空格和换行
                            temp_name = text_before_url.strip().replace('\n', ' ')
                            
                            # 校验：如果不为空且长度合理，就认为是真正的台名
                            if len(temp_name) > 1 and len(temp_name) < 60:
                                channel_name = temp_name
                                # 找到台名就可以跳出循环了（通常第一层或第二层父级就有）
                                # 但为了保险可以继续找日期，这里不break，继续找日期

                        # 3. 数据合并逻辑
                        if date_str:
                            try:
                                if len(date_str.split('-')[0]) == 4:
                                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                                else:
                                    dt = datetime.strptime(date_str, '%m-%d-%Y')
                                str_date = dt.strftime('%Y-%m-%d')

                                # 只有当日期有效才存入
                                if url in all_data:
                                    # 更新逻辑
                                    old_date = datetime.strptime(all_data[url]['Date'], '%Y-%m-%d')
                                    if dt > old_date:
                                        all_data[url]['Date'] = str_date
                                        # 总是更新台名，因为新抓到的可能更准确
                                        all_data[url]['Channel'] = channel_name
                                else:
                                    # 新增逻辑
                                    all_data[url] = {
                                        'Keyword': kw,
                                        'Channel': channel_name,
                                        'Date': str_date
                                    }
                                    new_found_count += 1
                                    print(f"     -> New: {channel_name} ({str_date})")
                            except: pass
                    except: continue
                
                print(f"   - {kw}: Processed. Found {new_found_count} new unique items.")

            except Exception as e:
                print(f"❌ Error scraping {kw}: {e}")
                continue

    except Exception as e:
        print(f"❌ Global Error: {e}")
    finally:
        if page: page.quit()
        try: shutil.rmtree(temp_user_dir)
        except: pass

    # --- 4. 清理与保存 ---
    print("\n🧹 Cleaning old data...")
    valid_data = {}
    expired_count = 0
    
    for url, info in all_data.items():
        try:
            item_date = datetime.strptime(info['Date'], '%Y-%m-%d')
            if item_date >= cutoff_date:
                valid_data[url] = info
            else:
                expired_count += 1
        except:
            expired_count += 1

    print(f"   Removed {expired_count} expired items.")
    print(f"   Total valid items remaining: {len(valid_data)}")

    if len(valid_data) > 0:
        save_all_files(valid_data)
    else:
        print("⚠️ No valid data remaining! Skipping save.")

if __name__ == "__main__":
    main()
