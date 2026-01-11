from DrissionPage import ChromiumPage, ChromiumOptions
from datetime import datetime, timedelta
import re
import os
import time
import tempfile
import shutil
import csv

# --- 配置部分 ---
KEYWORDS =  [ "广东体育", "无线新闻", "翡翠台", "VIU", "TVB PLUS", "NatGeo_twn", "Now Sports 精選", "discoveryhd_twn", "tlc_twn", "國家地理", "hbohd_twn"]
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
                
              # --- 新增：不管有没有被墙，先拍张照存证 ---
         page.get_screenshot(path='debug_proof.png', full_page=True)
                print("📸 Debug screenshot saved as debug_proof.png")
                # ---------------------------------------

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

                # --- 4. 通用提取逻辑 (不再针对特定词) ---
                items = page.eles('text:://')
                new_found = 0
                
                for item in items:
                    try:
                        # 1. 提取 URL
                        txt = item.text
                        url_match = re.search(r'((?:http|https|rtmp|rtsp)://[^\s<>"\u4e00-\u9fa5]+)', txt)
                        if not url_match: continue
                        url = url_match.group(1)

                        # 2. 寻找完整信息块
                        container = item
                        full_text_block = ""
                        
                        # 向上找包含换行符的父级，这是最准确的定位方式
                        for _ in range(3):
                            container = container.parent()
                            if not container: break
                            if "\n" in container.text:
                                full_text_block = container.text
                                break
                        
                        if not full_text_block:
                            full_text_block = container.text if container else ""

                        # 3. 按行解析 (通用逻辑)
                        # 清洗每一行：去掉首尾空格、去掉制表符、去掉看不见的符号
                        lines = [line.strip() for line in full_text_block.split('\n') if line.strip()]
                        
                        channel_name = "" # 初始为空，不预设为 kw
                        date_str = ""
                        
                        for line in lines:
                            # 忽略 URL 行
                            if "://" in line: continue
                            
                            # 检查是否是日期行
                            mat = re.search(r'(\d{2,4}-\d{1,2}-\d{2,4})', line)
                            if mat:
                                date_str = mat.group(1)
                                continue 
                            
                            # 如果还没找到台名，且这行不是URL也不是日期，那它就是台名
                            # 这里不再检查 len(line) < 50，防止某些长名字被漏掉
                            # 也不再检查是否包含关键字，完全信任页面显示
                            if not channel_name:
                                channel_name = line
                        
                        # 如果实在没提取到台名，才用关键字兜底 (防止空名)
                        if not channel_name:
                            channel_name = kw

                        # 4. 存入数据
                        if date_str:
                            try:
                                if len(date_str.split('-')[0]) == 4:
                                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                                else:
                                    dt = datetime.strptime(date_str, '%m-%d-%Y')
                                str_date = dt.strftime('%Y-%m-%d')

                                # 核心：总是用页面上抓到的真实名字 (channel_name) 更新数据库
                                if url in all_data:
                                    # 即使 URL 已存在，只要页面上的名字不是默认关键字，就更新它
                                    # 这样可以修正以前被错误存为 "VIU" 的数据
                                    if channel_name != kw:
                                        all_data[url]['Channel'] = channel_name
                                    
                                    # 更新日期
                                    old_date = datetime.strptime(all_data[url]['Date'], '%Y-%m-%d')
                                    if dt > old_date:
                                        all_data[url]['Date'] = str_date
                                else:
                                    # 新增
                                    all_data[url] = {
                                        'Keyword': kw,
                                        'Channel': channel_name,
                                        'Date': str_date
                                    }
                                    new_found += 1
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
