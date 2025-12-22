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
    """保存数据"""
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
                # 1. 打开首页
                page.get('http://tonkiang.us/')
                if not handle_cloudflare(page):
                    print("   - Cloudflare check failed, skipping...")
                    continue
                
                # 2. 寻找输入框
                search_input = page.ele('tag:input@@type!=hidden', timeout=5)
                if not search_input:
                    print("❌ Input not found")
                    continue
                
                # 3. 输入关键字
                search_input.clear()
                search_input.input(kw)
                
                # 4. 【核心修复】使用 JS 暴力提交表单
                # 不再寻找按钮，而是直接找到输入框所属的 Form，强制 Submit
                print("   - Submitting form via JS...")
                try:
                    # 尝试找到输入框的父级 Form 元素并提交
                    # 这行代码的意思是：找到 search_input 的父级 form 标签，然后执行 submit()
                    form = search_input.parent('tag:form')
                    if form:
                        # 使用 DrissionPage 的 run_js 直接执行原生 JS 提交，最稳
                        page.run_js('arguments[0].submit()', form)
                    else:
                        # 如果找不到 form 标签，尝试回车兜底
                        search_input.input('\n')
                except Exception as e:
                    print(f"   ⚠️ JS Submit failed: {e}, trying Enter key.")
                    search_input.input('\n')

                # 5. 等待加载 (移除数量检查，改为纯等待)
                page.wait.load_start()
                
                # 简单的动态等待：只要有结果就行，不判断数量是否达标
                found_items = []
                prev_count = -1
                
                # 最多等 8 秒
                for i in range(8):
                    found_items = page.eles('text:://') # 寻找所有带 :// 的文本
                    count = len(found_items)
                    
                    # 只要数量稳定了（不再变化），就认为加载完了
                    if count > 0 and count == prev_count:
                         break
                    
                    prev_count = count
                    time.sleep(1)

                print(f"     -> Found {len(found_items)} potential links. Processing...")

                # 6. 提取数据 (靠正则和日期过滤垃圾)
                new_count = 0
                for item in found_items:
                    try:
                        # 提取链接
                        txt = item.text
                        url_match = re.search(r'((?:http|https|rtmp|rtsp)://[^\s<>"\u4e00-\u9fa5]+)', txt)
                        if not url_match: continue
                        url = url_match.group(1)

                        # 提取日期 (这是区分“真结果”和“首页广告”的关键)
                        container = item
                        date_str = ""
                        channel_name = kw 
                        
                        for i in range(3):
                            container = container.parent()
                            if not container: break
                            
                            if not date_str:
                                mat = re.search(r'(\d{2,4}-\d{1,2}-\d{2,4})', container.text)
                                if mat: date_str = mat.group(1)
                            
                            # 提取台名
                            full_text = container.text
                            if kw in full_text:
                                temp_name = full_text.split('http')[0].split(date_str)[0].strip()
                                if len(temp_name) > 0 and len(temp_name) < 50:
                                    channel_name = clean_channel_name(temp_name)

                        # 【核心过滤】只有找到了有效日期，才认为是有效结果
                        # 首页的“联系我们”链接周围是不会有日期的，会被这里自动过滤
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
                            
                            # 合并/更新逻辑
                            if url in all_data:
                                old_date = datetime.strptime(all_data[url]['Date'], '%Y-%m-%d')
                                if final_date > old_date:
                                    all_data[url]['Date'] = str_date
                                    # 如果旧名字是默认关键字，新名字更详细，则更新名字
                                    if all_data[url]['Channel'] == kw and channel_name != kw:
                                        all_data[url]['Channel'] = channel_name
                            else:
                                all_data[url] = {'Keyword': kw, 'Channel': channel_name, 'Date': str_date}
                                new_count += 1
                    except: continue
                
                print(f"   -> Validated & Added: {new_count} new unique links.")

            except Exception as e:
                print(f"❌ Error processing {kw}: {e}")

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
        save_data(valid_data)
    else:
        print("⚠️ No valid data remaining! Skipping save.")

if __name__ == "__main__":
    main()
