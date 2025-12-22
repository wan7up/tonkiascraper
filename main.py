from DrissionPage import ChromiumPage, ChromiumOptions
from datetime import datetime, timedelta
import re
import os
import time
import tempfile
import shutil
import csv  # 引入 CSV 模块

# --- 配置部分 ---
KEYWORDS = ["无线新闻", "广东体育", "翡翠台", "VIU", "tvb plus", "now SPORTS PRIME", "Now Sports 精選", "Discovery", "國家地理", "NatGeo", "HBO"]
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

# --- 新增：读取历史数据 ---
def load_history():
    history = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 以 URL 为 Key，方便快速查找
                    history[row['URL']] = {
                        'Channel': row['Channel'],
                        'Date': row['Date'],
                        'Keyword': row['Keyword']
                    }
            print(f"📖 Loaded {len(history)} items from history database.")
        except Exception as e:
            print(f"⚠️ History load failed: {e}")
    return history

# --- 新增：保存数据逻辑 ---
def save_all_files(data_dict):
    try:
        # 1. 保存 CSV (数据库)
        with open(DATA_FILE, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['Keyword', 'Channel', 'Date', 'URL']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            # 按关键字排序
            sorted_items = sorted(data_dict.items(), key=lambda x: x[1]['Keyword'])
            for url, info in sorted_items:
                writer.writerow({
                    'Keyword': info['Keyword'],
                    'Channel': info['Channel'],
                    'Date': info['Date'],
                    'URL': url
                })
        
        # 2. 保存 M3U (播放列表)
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
    # --- 1. 环境配置 (完全保持原版) ---
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
    # 加载历史 CSV 数据
    all_data = load_history() 
    
    current_date = datetime.now()
    cutoff_date = current_date - timedelta(days=DAYS_LIMIT)

    try:
        # --- 3. 循环搜索 (核心逻辑严格保持“成功版”原样) ---
        for kw in KEYWORDS:
            print(f"\n🚀 Processing Keyword: {kw}")
            
            try:
                page.get('http://tonkiang.us/')
                handle_cloudflare(page) 
                
                search_input = page.ele('tag:input@@type!=hidden', timeout=5)
                if search_input:
                    search_input.clear()
                    # ⚠️ 保持原版：只输入文字
                    search_input.input(kw)
                    print(f"   - Input keyword: {kw}")
                    
                    # ⚠️ 保持原版：优先找按钮点击
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

                    # ⚠️ 保持原版：等待逻辑
                    time.sleep(3) 
                    if len(page.eles('text:://')) <= 8:
                        print("   - Links count low, waiting 3 more seconds...")
                        time.sleep(3)

                else:
                    print(f"❌ Input box not found for {kw}, skipping.")
                    continue

                # --- 提取与更新逻辑 (这里接入 CSV 逻辑) ---
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

                        # 2. 提取日期和台名 (保持原版正则)
                        container = item
                        date_str = ""
                        channel_name = kw # 默认台名为关键字
                        
                        for _ in range(3):
                            container = container.parent()
                            if not container: break
                            
                            # 找日期
                            if not date_str:
                                mat = re.search(r'(\d{2,4}-\d{1,2}-\d{2,4})', container.text)
                                if mat: date_str = mat.group(1)
                            
                            # 找更详细的台名 (可选优化，不强求，防止破坏逻辑)
                            full_text = container.text
                            if kw in full_text:
                                temp_name = full_text.split('http')[0].split(date_str if date_str else "")[0].strip()
                                if len(temp_name) > 0 and len(temp_name) < 50:
                                    channel_name = temp_name.replace('\n', ' ').strip()

                        # 3. 数据合并逻辑
                        if date_str:
                            try:
                                # 格式化日期
                                if len(date_str.split('-')[0]) == 4:
                                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                                else:
                                    dt = datetime.strptime(date_str, '%m-%d-%Y')
                                str_date = dt.strftime('%Y-%m-%d')

                                # --> CSV 核心逻辑：对比更新 <--
                                if url in all_data:
                                    # 如果已存在，检查是否需要更新日期
                                    old_date = datetime.strptime(all_data[url]['Date'], '%Y-%m-%d')
                                    if dt > old_date:
                                        all_data[url]['Date'] = str_date
                                        # 如果新名字比旧名字(默认关键字)更详细，也更新名字
                                        if all_data[url]['Channel'] == kw and channel_name != kw:
                                            all_data[url]['Channel'] = channel_name
                                else:
                                    # 如果不存在，新增
                                    all_data[url] = {
                                        'Keyword': kw,
                                        'Channel': channel_name,
                                        'Date': str_date
                                    }
                                    new_found_count += 1
                                    print(f"     -> New: {str_date} | {url[:30]}...")
                            except: pass
                    except: continue
                
                print(f"   - {kw}: Found {new_found_count} new items (others merged/updated).")

            except Exception as e:
                print(f"❌ Error scraping {kw}: {e}")
                continue

    except Exception as e:
        print(f"❌ Global Error: {e}")
    finally:
        if page: page.quit()
        try: shutil.rmtree(temp_user_dir)
        except: pass

    # --- 4. 清理过期数据 & 保存 ---
    print("\n🧹 Cleaning old data (Limit: 30 days)...")
    valid_data = {}
    expired_count = 0
    
    # 遍历所有数据（包括刚抓的和历史的）
    for url, info in all_data.items():
        try:
            item_date = datetime.strptime(info['Date'], '%Y-%m-%d')
            if item_date >= cutoff_date:
                valid_data[url] = info
            else:
                expired_count += 1
        except:
            expired_count += 1 # 日期格式不对也删掉

    print(f"   Removed {expired_count} expired items.")
    print(f"   Total valid items remaining: {len(valid_data)}")

    # 只有当有数据剩余时才保存，防止意外清空
    if len(valid_data) > 0:
        save_all_files(valid_data)
    else:
        print("⚠️ No valid data remaining! Skipping save to protect files.")

if __name__ == "__main__":
    main()
