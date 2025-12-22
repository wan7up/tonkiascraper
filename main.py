from DrissionPage import ChromiumPage, ChromiumOptions
from datetime import datetime, timedelta
import re
import os
import time
import tempfile
import shutil
import csv # 引入 CSV

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

# --- 新增：读取历史 CSV ---
def load_history():
    history = {}
    if os.path.exists("data.csv"):
        try:
            with open("data.csv", 'r', encoding='utf-8', newline='') as f:
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

# --- 新增：保存所有文件 ---
def save_files(data_dict):
    try:
        # 1. 保存 CSV
        with open("data.csv", 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['Keyword', 'Channel', 'Date', 'URL']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            sorted_items = sorted(data_dict.items(), key=lambda x: x[1]['Keyword'])
            for url, info in sorted_items:
                writer.writerow({'Keyword': info['Keyword'], 'Channel': info['Channel'], 'Date': info['Date'], 'URL': url})
        
        # 2. 保存 M3U
        with open("tv.m3u", 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for url, info in data_dict.items():
                f.write(f'#EXTINF:-1 group-title="{info["Keyword"]}",{info["Channel"]}\n{url}\n')

        # 3. 保存 TXT
        with open("tv.txt", 'w', encoding='utf-8') as f:
            for url, info in data_dict.items():
                f.write(f'{info["Channel"]},{url}\n')

        print(f"💾 Database updated: {len(data_dict)} items saved.")
    except Exception as e:
        print(f"❌ Save failed: {e}")

def main():
    # --- 1. 环境配置 (保持原版) ---
    temp_user_dir = tempfile.mkdtemp()
    co = ChromiumOptions()
    co.headless(True)
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    # 这里的窗口大小很重要，防止按钮被挡住
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
    
    # 你的原版关键词
    keywords = ["无线新闻", "广东体育", "翡翠台", "VIU", "tvb plus", "NatGeo_twn", "Now Sports 精選", "discoveryhd_twn", "tlc_twn", "國家地理", "hbohd_twn"]
    days_limit = 30
    current_date = datetime.now()
    cutoff_date = current_date - timedelta(days=days_limit)

    try:
        # --- 3. 循环搜索 ---
        for kw in keywords:
            print(f"\n🚀 Processing Keyword: {kw}")
            
            try:
                page.get('http://tonkiang.us/')
                handle_cloudflare(page) 
                
                search_input = page.ele('tag:input@@type!=hidden', timeout=5)
                if search_input:
                    search_input.clear()
                    # 原版用的是 f"{kw}\n"，但调试证明回车失效了
                    # 这里改为只输字，后面手动点按钮
                    search_input.input(kw)
                    
                    # 👇👇👇 关键修复：必须物理点击按钮才能跳出首页 👇👇👇
                    try:
                        # 尝试找输入框旁边的按钮，或者 type=submit 的按钮
                        search_btn = search_input.next('tag:button') or page.ele('tag:button@@type=submit')
                        if search_btn:
                            search_btn.click()
                        else:
                            # 实在找不到才用回车兜底
                            search_input.input('\n')
                    except:
                        search_input.input('\n')
                    
                    # 保持原版的等待时间
                    page.wait(3) 

                else:
                    print(f"❌ Input box not found for {kw}, skipping.")
                    continue

                # --- 提取逻辑 (基于原版，但修复台名提取) ---
                items = page.eles('text:://')
                new_found = 0
                
                # 简单的检查：如果还在首页，通常 text::// 数量很少或者全是乱七八糟的
                if len(items) > 0:
                    for item in items:
                        try:
                            # 1. 提取链接
                            txt = item.text
                            url_match = re.search(r'((?:http|https|rtmp|rtsp)://[^\s<>"\u4e00-\u9fa5]+)', txt)
                            if not url_match: continue
                            url = url_match.group(1)

                            # 2. 提取日期和台名 (向上找父级)
                            container = item
                            date_str = ""
                            channel_name = kw # 默认值，下面尝试覆盖
                            
                            for _ in range(3):
                                container = container.parent()
                                if not container: break
                                
                                # 找日期
                                if not date_str:
                                    mat = re.search(r'(\d{2,4}-\d{1,2}-\d{2,4})', container.text)
                                    if mat: date_str = mat.group(1)
                                
                                # 👇👇👇 核心修改：提取真实台名 👇👇👇
                                # 只要这行字里有内容，就尝试切割出名字
                                full_text = container.text
                                # 逻辑：砍掉 http 后面的，再砍掉日期，剩下的就是名字
                                temp_text = full_text.split('http')[0]
                                if date_str:
                                    temp_text = temp_text.replace(date_str, '')
                                
                                clean_name = temp_text.strip().replace('\n', ' ')
                                # 如果剩下的名字长度合理(大于1且小于50)，就采用它
                                if len(clean_name) > 1 and len(clean_name) < 50:
                                    channel_name = clean_name

                            # 3. 存入数据 (结合 CSV 逻辑)
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
                                            # 总是更新为最新抓到的名字
                                            all_data[url]['Channel'] = channel_name
                                    else:
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

    # --- 4. 清理与保存 (CSV 逻辑) ---
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
