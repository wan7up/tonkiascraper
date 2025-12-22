from DrissionPage import ChromiumPage, ChromiumOptions
from datetime import datetime, timedelta
import re
import os
import time
import tempfile
import shutil
import csv

# --- 配置部分 ---
KEYWORDS = ["无线新闻", "广东体育", "翡翠台", "VIU", "tvb plus", "Now Sports 精選", "Discovery", "國家地理", "NatGeo", "HBO"] 
DAYS_LIMIT = 30  
DATA_FILE = "data.csv" 
M3U_FILE = "tv.m3u"
TXT_FILE = "tv.txt"

def handle_cloudflare(page):
    """智能处理 Cloudflare"""
    for i in range(10):
        try:
            title = page.title
            if "Just a moment" not in title and ("IPTV" in title or "Search" in title or "Tonkiang" in title):
                return True
            time.sleep(2)
        except:
            time.sleep(2)
    return False

def clean_channel_name(text):
    """清理台名"""
    return text.replace('\n', ' ').strip()

def load_history():
    """读取历史数据"""
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
        except Exception as e:
            print(f"⚠️ Error loading history: {e}")
    return history

def save_data(data_dict):
    """保存数据到三个文件"""
    try:
        # 1. CSV
        with open(DATA_FILE, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['Keyword', 'Channel', 'Date', 'URL']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            sorted_items = sorted(data_dict.items(), key=lambda x: x[1]['Keyword'])
            for url, info in sorted_items:
                writer.writerow({'Keyword': info['Keyword'], 'Channel': info['Channel'], 'Date': info['Date'], 'URL': url})
        
        # 2. M3U
        with open(M3U_FILE, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for url, info in data_dict.items():
                f.write(f'#EXTINF:-1 group-title="{info["Keyword"]}",{info["Channel"]}\n{url}\n')
        
        # 3. TXT
        with open(TXT_FILE, 'w', encoding='utf-8') as f:
            for url, info in data_dict.items():
                f.write(f'{info["Channel"]},{url}\n')
                
        print(f"💾 All files updated. Total unique items: {len(data_dict)}")
    except Exception as e:
        print(f"❌ Error saving files: {e}")

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

    # --- 2. 加载历史数据 ---
    all_data = load_history()
    current_date = datetime.now()
    cutoff_date = current_date - timedelta(days=DAYS_LIMIT)

    try:
        # --- 3. 循环搜索关键词 ---
        for kw in KEYWORDS:
            print(f"\n🚀 Processing Keyword: {kw}")
            
            try:
                # 每次都强制刷新首页，确保环境干净
                page.get('http://tonkiang.us/')
                if not handle_cloudflare(page):
                    print("   - Cloudflare check failed, skipping...")
                    continue

                search_input = page.ele('tag:input@@type!=hidden', timeout=5)
                if search_input:
                    search_input.clear()
                    search_input.input(f"{kw}\n")
                    
                    # 👇👇👇 核心修改：移除数量限制，改为“稳定性等待” 👇👇👇
                    current_items = []
                    prev_count = -1
                    stable_counter = 0
                    
                    # 最多等待 12 秒
                    for i in range(8):
                        current_items = page.eles('text:://')
                        current_count = len(current_items)
                        
                        print(f"     [Wait {i+1}] Found {current_count} links...")
                        
                        # 如果数量大于0，且跟上一次检查一样，说明加载稳定了
                        if current_count > 0 and current_count == prev_count:
                            stable_counter += 1
                            # 连续两次检查数量一致，认为加载完毕，不再傻等
                            if stable_counter >= 2:
                                print("     -> Results stabilized.")
                                break
                        else:
                            # 还在变动，重置计数器
                            stable_counter = 0
                            
                        prev_count = current_count
                        time.sleep(1.5)
                    
                    if len(current_items) == 0:
                        print("     ⚠️ No links found for this keyword.")
                        continue
                        
                    # 👆👆👆 修改结束 👆👆👆

                    # 开始提取
                    new_count = 0
                    for item in current_items:
                        try:
                            txt = item.text
                            url_match = re.search(r'((?:http|https|rtmp|rtsp)://[^\s<>"\u4e00-\u9fa5]+)', txt)
                            if not url_match: continue
                            url = url_match.group(1)

                            # 提取日期和台名
                            container = item
                            date_str = ""
                            channel_name = kw # 默认使用搜索关键字
                            
                            for i in range(3):
                                container = container.parent()
                                if not container: break
                                
                                # 找日期
                                if not date_str:
                                    mat = re.search(r'(\d{2,4}-\d{1,2}-\d{2,4})', container.text)
                                    if mat: date_str = mat.group(1)
                                
                                # 找台名
                                full_text = container.text
                                # 只有当这行文字包含了关键字，才尝试提取台名，防止抓到无关的广告文字
                                if kw in full_text:
                                    temp_name = full_text.split('http')[0].split(date_str)[0].strip()
                                    if len(temp_name) > 0 and len(temp_name) < 50:
                                        channel_name = clean_channel_name(temp_name)

                            # 处理日期
                            final_date = None
                            if date_str:
                                try:
                                    if len(date_str.split('-')[0]) == 4:
                                        dt = datetime.strptime(date_str, '%Y-%m-%d')
                                    else:
                                        dt = datetime.strptime(date_str, '%m-%d-%Y')
                                    final_date = dt
                                except: pass
                            
                            if final_date:
                                str_date = final_date.strftime('%Y-%m-%d')
                                if url in all_data:
                                    # 更新已有链接
                                    old_date = datetime.strptime(all_data[url]['Date'], '%Y-%m-%d')
                                    if final_date > old_date:
                                        all_data[url]['Date'] = str_date
                                        # 如果之前的台名是空的或者是默认关键字，尝试更新为更详细的台名
                                        if all_data[url]['Channel'] == kw and channel_name != kw:
                                            all_data[url]['Channel'] = channel_name
                                else:
                                    # 新增
                                    all_data[url] = {'Keyword': kw, 'Channel': channel_name, 'Date': str_date}
                                    new_count += 1
                        except: continue
                    
                    print(f"   -> Added/Updated items. New unique links: {new_count}")

                else:
                    print(f"❌ Input not found for {kw}")
            
            except Exception as e:
                print(f"❌ Error processing {kw}: {e}")
                time.sleep(2)

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
            # 核心规则：30天内的保留
            if item_date >= cutoff_date:
                valid_data[url] = info
            else:
                expired_count += 1
        except:
            expired_count += 1

    print(f"   Removed {expired_count} expired items.")

    # 只要有数据就保存，不再做数量限制
    if len(valid_data) > 0:
        save_data(valid_data)
    else:
        print("⚠️ No valid data remaining! Skipping save.")

if __name__ == "__main__":
    main()
