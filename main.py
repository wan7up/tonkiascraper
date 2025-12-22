from DrissionPage import ChromiumPage, ChromiumOptions
from datetime import datetime, timedelta
import re
import os
import time
import tempfile
import shutil
import csv

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

# --- 读取历史 CSV ---
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
            print(f"📖 Loaded {len(history)} items from history.")
        except: pass
    return history

# --- 保存所有文件 ---
def save_files(data_dict):
    try:
        # 1. 保存 CSV
        with open(DATA_FILE, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['Keyword', 'Channel', 'Date', 'URL']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            sorted_items = sorted(data_dict.items(), key=lambda x: x[1]['Keyword'])
            for url, info in sorted_items:
                writer.writerow({'Keyword': info['Keyword'], 'Channel': info['Channel'], 'Date': info['Date'], 'URL': url})
        
        # 2. 保存 M3U
        with open(M3U_FILE, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for url, info in data_dict.items():
                f.write(f'#EXTINF:-1 group-title="{info["Keyword"]}",{info["Channel"]}\n{url}\n')

        # 3. 保存 TXT
        with open(TXT_FILE, 'w', encoding='utf-8') as f:
            for url, info in data_dict.items():
                f.write(f'{info["Channel"]},{url}\n')

        print(f"💾 Database updated: {len(data_dict)} items saved.")
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
    co.set_argument('--window-size=1920,1080')
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
                    search_input.input(kw)
                    
                    # 提交搜索
                    try:
                        search_btn = search_input.next('tag:button') or page.ele('tag:button@@type=submit')
                        if search_btn:
                            search_btn.click()
                        else:
                            search_input.input('\n')
                    except:
                        search_input.input('\n')
                    
                    page.wait(3) 

                else:
                    print(f"❌ Input box not found for {kw}, skipping.")
                    continue

                # --- 4. 提取逻辑 (所见即所得版) ---
                items = page.eles('text:://')
                new_found = 0
                
                # 打印第一个找到的原始文本块，用于调试
                debug_printed = False

                for item in items:
                    try:
                        # 1. 提取 URL
                        txt = item.text
                        url_match = re.search(r'((?:http|https|rtmp|rtsp)://[^\s<>"\u4e00-\u9fa5]+)', txt)
                        if not url_match: continue
                        url = url_match.group(1)

                        # 2. 向上找父级容器，直到找到包含换行符的完整块
                        container = item
                        full_text_block = ""
                        
                        # 尝试向上找 3 层
                        for _ in range(3):
                            container = container.parent()
                            if not container: break
                            if "\n" in container.text: # 如果包含换行，说明可能包含了台名和链接
                                full_text_block = container.text
                                break
                        
                        # 如果还没找到换行，可能是一行显示的，就用当前的
                        if not full_text_block:
                            full_text_block = container.text if container else ""

                        # 🛠️ 调试：打印第一个抓到的块，让你看看脚本到底“看”到了什么
                        if not debug_printed and "VIU" in kw:
                             print(f"   🔎 [Debug] Raw Block Structure:\n{repr(full_text_block)}")
                             debug_printed = True

                        # 3. 按行解析 (所见即所得)
                        # 将文本按换行符拆分
                        lines = [line.strip() for line in full_text_block.split('\n') if line.strip()]
                        
                        channel_name = kw # 默认值
                        date_str = ""
                        
                        # 分析每一行
                        for line in lines:
                            # 如果这行是 URL，跳过
                            if "://" in line: continue
                            
                            # 如果这行包含日期，提取日期
                            mat = re.search(r'(\d{2,4}-\d{1,2}-\d{2,4})', line)
                            if mat:
                                date_str = mat.group(1)
                                continue # 这行是日期行，跳过
                            
                            # 如果既不是URL也不是日期，那它极大概率就是台名！
                            # 取第一行符合条件的作为台名
                            if len(line) < 50 and not date_str: # 台名通常出现在日期之前
                                channel_name = line
                                break # 找到了就停，只取第一行

                        # 4. 存入数据
                        if date_str:
                            try:
                                if len(date_str.split('-')[0]) == 4:
                                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                                else:
                                    dt = datetime.strptime(date_str, '%m-%d-%Y')
                                str_date = dt.strftime('%Y-%m-%d')

                                # 数据合并与更新
                                if url in all_data:
                                    old_date = datetime.strptime(all_data[url]['Date'], '%Y-%m-%d')
                                    if dt > old_date:
                                        all_data[url]['Date'] = str_date
                                        # 总是更新为最新抓到的名字 (只要它不是默认关键字)
                                        if channel_name != kw:
                                            all_data[url]['Channel'] = channel_name
                                else:
                                    all_data[url] = {
                                        'Keyword': kw,
                                        'Channel': channel_name,
                                        'Date': str_date
                                    }
                                    new_found += 1
                                    # 打印日志看看抓对了没
                                    # print(f"     -> New: [{channel_name}] {str_date}")
                            except: pass
                    except: continue
                
                print(f"   - {kw}: Processed. Found {new_found} new items.")

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
    
    if len(valid_data) > 0:
        save_files(valid_data)
    else:
        print("⚠️ No valid data remaining! Skipping save.")

if __name__ == "__main__":
    main()
