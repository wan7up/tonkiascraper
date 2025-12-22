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
    """检测是否被 Cloudflare 拦截"""
    for i in range(5):
        try:
            title = page.title
            # 如果标题正常，直接返回
            if "Just a moment" not in title and ("IPTV" in title or "Search" in title or "Tonkiang" in title):
                return True
            time.sleep(2)
        except:
            time.sleep(2)
    return False

def clean_channel_name(text):
    return text.replace('\n', ' ').strip()

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
        except: pass
    return history

def save_data(data_dict):
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
                
        print(f"💾 All files updated. Total unique items: {len(data_dict)}")
    except Exception as e:
        print(f"❌ Error saving files: {e}")

def main():
    # --- 浏览器初始化 ---
    temp_user_dir = tempfile.mkdtemp()
    co = ChromiumOptions()
    co.headless(True)
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--window-size=1920,1080') # 必须大窗口
    co.set_argument(f'--user-data-dir={temp_user_dir}')
    co.set_argument('--remote-allow-origins=*')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')

    chrome_path = os.getenv('CHROME_PATH')
    if chrome_path:
        co.set_paths(browser_path=chrome_path)

    page = None
    try:
        page = ChromiumPage(co)
        print("✅ Browser launched successfully!")
    except Exception as e:
        print(f"❌ Browser Init Failed: {e}")
        try: shutil.rmtree(temp_user_dir) 
        except: pass
        return

    # --- 加载数据 ---
    all_data = load_history()
    current_date = datetime.now()
    cutoff_date = current_date - timedelta(days=DAYS_LIMIT)

    try:
        # --- 循环搜索 ---
        for kw in KEYWORDS:
            print(f"\n🚀 Processing Keyword: {kw}")
            
            try:
                # 👇👇👇 核心修改：每次都重新加载首页 URL，而不是 Refresh 👇👇👇
                # 这能避免 POST 表单重复提交的弹窗问题，确保每次都是干净的首页
                page.get('http://tonkiang.us/')
                if not handle_cloudflare(page):
                    print("   - Cloudflare check failed, skipping...")
                    continue
                
                # 寻找输入框
                search_input = page.ele('tag:input@@type!=hidden', timeout=5)
                if search_input:
                    search_input.clear()
                    search_input.input(kw)
                    time.sleep(0.5)
                    
                    # 提交搜索 (物理回车 + JS点击双保险)
                    print("   - Submitting search...")
                    page.actions.key_down('ENTER')
                    page.actions.key_up('ENTER')
                    
                    time.sleep(1)
                    # 尝试找按钮点一下作为备份
                    try:
                        btn = search_input.next('tag:button') or page.ele('tag:button@@type=submit')
                        if btn: btn.click(by_js=True)
                    except: pass
                    
                    # 等待结果加载
                    print("   - Waiting for results...")
                    found_items = []
                    prev_count = -1
                    
                    # 动态等待
                    for i in range(10):
                        found_items = page.eles('text:://') # 寻找所有包含 :// 的文本节点
                        count = len(found_items)
                        if count > 0 and count == prev_count:
                            break
                        prev_count = count
                        time.sleep(1)

                    # 提取数据
                    new_count = 0
                    
                    # 用于调试：如果找到了链接但没加进去，打印第一个看看是什么鬼
                    debug_first_item = None

                    for item in found_items:
                        try:
                            # 1. 提取 URL
                            txt = item.text
                            if not debug_first_item: debug_first_item = txt # 记录一下用于调试
                            
                            url_match = re.search(r'((?:http|https|rtmp|rtsp)://[^\s<>"\u4e00-\u9fa5]+)', txt)
                            if not url_match: continue
                            url = url_match.group(1)

                            # 2. 寻找日期和台名 (向上查找父级)
                            container = item
                            date_str = ""
                            channel_name = kw 
                            
                            for i in range(3):
                                container = container.parent()
                                if not container: break
                                
                                # 找日期 (YYYY-MM-DD 或 MM-DD-YYYY)
                                if not date_str:
                                    mat = re.search(r'(\d{2,4}-\d{1,2}-\d{2,4})', container.text)
                                    if mat: date_str = mat.group(1)
                                
                                # 找台名 (必须包含关键字)
                                full_text = container.text
                                if kw in full_text:
                                    # 简单的去噪
                                    temp_name = full_text.split('http')[0].split(date_str)[0].strip()
                                    if len(temp_name) > 0 and len(temp_name) < 50:
                                        channel_name = clean_channel_name(temp_name)

                            # 3. 校验日期
                            final_date = None
                            if date_str:
                                try:
                                    parts = date_str.split('-')
                                    if len(parts[0]) == 4: # YYYY-MM-DD
                                        final_date = datetime.strptime(date_str, '%Y-%m-%d')
                                    else: # MM-DD-YYYY
                                        final_date = datetime.strptime(date_str, '%m-%d-%Y')
                                except: pass
                            
                            # 4. 存入数据库
                            if final_date:
                                str_date = final_date.strftime('%Y-%m-%d')
                                
                                if url in all_data:
                                    # 更新旧数据
                                    old_date = datetime.strptime(all_data[url]['Date'], '%Y-%m-%d')
                                    if final_date > old_date:
                                        all_data[url]['Date'] = str_date
                                        if all_data[url]['Channel'] == kw and channel_name != kw:
                                            all_data[url]['Channel'] = channel_name
                                else:
                                    # 新增数据
                                    all_data[url] = {'Keyword': kw, 'Channel': channel_name, 'Date': str_date}
                                    new_count += 1
                        except: continue
                    
                    print(f"   -> Found {len(found_items)} raw links. Validated & Added: {new_count}")
                    
                    if len(found_items) > 0 and new_count == 0:
                         print(f"      ⚠️ Debug: First raw item text: {debug_first_item[:100]}...")

                else:
                    print("❌ Input not found (Page load error?)")

            except Exception as e:
                print(f"❌ Error processing {kw}: {e}")

    except Exception as e:
        print(f"❌ Global Error: {e}")
    finally:
        if page: page.quit()
        try: shutil.rmtree(temp_user_dir)
        except: pass

    # --- 清理与保存 ---
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
