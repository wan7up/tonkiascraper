from DrissionPage import ChromiumPage, ChromiumOptions
from datetime import datetime, timedelta
import re
import os
import time
import tempfile
import shutil
import csv

# --- 配置部分 ---
KEYWORDS = ["无线新闻", "广东体育", "翡翠台"] # 在这里修改你的搜索词
DAYS_LIMIT = 30  # 有效期 30 天
DATA_FILE = "data.csv" # 核心数据库文件
M3U_FILE = "tv.m3u"
TXT_FILE = "tv.txt"

def handle_cloudflare(page):
    """智能处理 Cloudflare"""
    print("🛡️ Checking Cloudflare status...")
    for i in range(10):
        try:
            title = page.title
            if "Just a moment" not in title and ("IPTV" in title or "Search" in title or "Tonkiang" in title):
                print(f"✅ Access Granted! (Title: {title})")
                return True
            print(f"   - Still in waiting room... ({i+1}/10)")
            time.sleep(3)
        except:
            time.sleep(3)
    print("⚠️ Cloudflare check timed out")
    return False

def clean_channel_name(text):
    """清理台名，去除多余空格和无关字符"""
    # 提取主要文字，去掉可能的 CSS 干扰
    text = text.replace('\n', ' ').strip()
    return text

def load_history():
    """读取历史数据 (URL -> {name, date, keyword})"""
    history = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # key 是 URL，value 是其他信息
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
    """保存数据到 CSV 和 M3U"""
    # 1. 保存 CSV (作为下次的历史数据)
    try:
        with open(DATA_FILE, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['Keyword', 'Channel', 'Date', 'URL']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            # 按关键字排序，好看一点
            sorted_items = sorted(data_dict.items(), key=lambda x: x[1]['Keyword'])
            
            for url, info in sorted_items:
                writer.writerow({
                    'Keyword': info['Keyword'],
                    'Channel': info['Channel'],
                    'Date': info['Date'],
                    'URL': url
                })
        print(f"💾 Updated {DATA_FILE} with {len(data_dict)} items.")
    except Exception as e:
        print(f"❌ Error saving CSV: {e}")

    # 2. 生成 M3U (供外部使用)
    try:
        with open(M3U_FILE, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for url, info in data_dict.items():
                # 格式: #EXTINF:-1 group-title="关键字",台名
                f.write(f'#EXTINF:-1 group-title="{info["Keyword"]}",{info["Channel"]}\n{url}\n')
        print(f"📺 Generated {M3U_FILE}")
    except Exception as e:
        print(f"❌ Error saving M3U: {e}")

    # 3. 生成 TXT
    try:
        with open(TXT_FILE, 'w', encoding='utf-8') as f:
            for url, info in data_dict.items():
                f.write(f'{info["Channel"]},{url}\n')
        print(f"📝 Generated {TXT_FILE}")
    except Exception as e:
        print(f"❌ Error saving TXT: {e}")

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
    all_data = load_history() # 格式: {url: {Channel, Date, Keyword}}
    current_date = datetime.now()
    cutoff_date = current_date - timedelta(days=DAYS_LIMIT)

    try:
        # --- 3. 开始抓取新数据 ---
        for kw in KEYWORDS:
            print(f"\n🚀 Processing Keyword: {kw}")
            try:
                page.get('http://tonkiang.us/')
                handle_cloudflare(page)
                
                search_input = page.ele('tag:input@@type!=hidden', timeout=5)
                if search_input:
                    search_input.clear()
                    search_input.input(f"{kw}\n")
                    print(f"   - Searching for {kw}...")
                    
                    # 智能等待
                    for i in range(10):
                        items = page.eles('text:://')
                        if len(items) > 5:
                            print("     -> Results loaded!")
                            break
                        time.sleep(1.5)
                else:
                    print(f"❌ Input not found for {kw}")
                    continue

                # 提取数据
                new_count = 0
                for item in items:
                    try:
                        # 提取链接
                        txt = item.text
                        url_match = re.search(r'((?:http|https|rtmp|rtsp)://[^\s<>"\u4e00-\u9fa5]+)', txt)
                        if not url_match: continue
                        url = url_match.group(1)

                        # 提取日期
                        container = item
                        date_str = ""
                        channel_name = kw # 默认台名为关键字，下面尝试从页面提取
                        
                        # 向上找父级获取日期，同时找台名
                        # Tonkiang 结构通常是: <div> 结果文字... 日期... <a href=...>Link</a> </div>
                        # 我们尝试获取整行的文本作为台名来源
                        for i in range(3):
                            container = container.parent()
                            if not container: break
                            
                            # 找日期
                            if not date_str:
                                mat = re.search(r'(\d{2,4}-\d{1,2}-\d{2,4})', container.text)
                                if mat: date_str = mat.group(1)
                            
                            # 找台名 (简单处理：取父级文本，去掉链接和日期，剩下的就是可能的台名)
                            # 这是一个粗略的提取，因为网页结构多变
                            full_text = container.text
                            if kw in full_text: # 确保这行文字里包含了关键字，才认为是台名
                                # 简单的清洗逻辑
                                temp_name = full_text.split('http')[0].split(date_str)[0].strip()
                                if len(temp_name) > 0 and len(temp_name) < 50:
                                    channel_name = clean_channel_name(temp_name)

                        # 格式化日期
                        final_date = None
                        if date_str:
                            try:
                                if len(date_str.split('-')[0]) == 4:
                                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                                else:
                                    dt = datetime.strptime(date_str, '%m-%d-%Y')
                                final_date = dt
                            except: pass
                        
                        # 逻辑判断：新增或更新
                        if final_date:
                            str_date = final_date.strftime('%Y-%m-%d')
                            
                            # 如果链接已存在
                            if url in all_data:
                                # 更新日期为最新的
                                old_date_str = all_data[url]['Date']
                                try:
                                    old_date = datetime.strptime(old_date_str, '%Y-%m-%d')
                                    if final_date > old_date:
                                        all_data[url]['Date'] = str_date
                                        # 可以选择更新台名，也可以保留旧的，这里选择保留旧的台名除非旧的为空
                                        if not all_data[url]['Channel']:
                                            all_data[url]['Channel'] = channel_name
                                        # print(f"     -> Updated: {channel_name} ({str_date})")
                                except: pass
                            else:
                                # 新增链接
                                all_data[url] = {
                                    'Keyword': kw,
                                    'Channel': channel_name,
                                    'Date': str_date
                                }
                                new_count += 1
                                print(f"     -> New: {channel_name} | {str_date}")

                    except Exception as e: continue
                
                print(f"   - Added {new_count} new links for {kw}")

            except Exception as e:
                print(f"❌ Error processing {kw}: {e}")

    except Exception as e:
        print(f"❌ Global Error: {e}")
    finally:
        if page: page.quit()
        try: shutil.rmtree(temp_user_dir)
        except: pass

    # --- 4. 清理过期数据 & 保存 ---
    print("\n🧹 Cleaning old data...")
    valid_data = {}
    expired_count = 0
    
    for url, info in all_data.items():
        try:
            item_date = datetime.strptime(info['Date'], '%Y-%m-%d')
            # 核心保留逻辑：只有日期在 30 天以内的保留
            if item_date >= cutoff_date:
                valid_data[url] = info
            else:
                expired_count += 1
        except:
            # 日期格式错误的也删掉
            expired_count += 1

    print(f"   Removed {expired_count} expired items (older than {cutoff_date.strftime('%Y-%m-%d')})")
    print(f"   Total valid items: {len(valid_data)}")

    # 5. 安全保存 (只有当有效数据大于0时才保存，防止全删光了)
    if len(valid_data) > 0:
        save_data(valid_data)
    else:
        print("⚠️ No valid data remaining! Skipping save to protect old files.")

if __name__ == "__main__":
    main()
