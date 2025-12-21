from DrissionPage import ChromiumPage, ChromiumOptions
from datetime import datetime, timedelta
import re
import os
import time
import tempfile
import shutil

def handle_cloudflare(page):
    """
    智能处理 Cloudflare，检测到已进入首页则立即放行
    """
    print("🛡️ Checking Cloudflare status...")
    
    for i in range(10):
        try:
            title = page.title
            # 如果标题包含 Tonkiang 的特征词，或者 IPTV Search，说明已经进去了
            if "Just a moment" not in title and ("IPTV" in title or "Search" in title or "Tonkiang" in title):
                print(f"✅ Access Granted! (Title: {title})")
                return True
            
            print(f"   - Still in waiting room... ({i+1}/10)")
            time.sleep(3)
        except:
            time.sleep(3)
    
    print("⚠️ Cloudflare check timed out (trying to proceed anyway)")
    return False

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

    # --- 2. 采集配置 ---
    keywords = ["无线新闻", "广东体育", "翡翠台"]
    days_limit = 30  # 恢复到 30 天，过滤陈旧源
    time_threshold = datetime.now() - timedelta(days=days_limit)
    
    # 用于存储最终结果
    final_results = []
    # 用于去重，防止同一个 URL 出现多次
    seen_urls = set()

    try:
        # --- 3. 循环搜索关键词 ---
        for kw in keywords:
            print(f"\n🚀 Processing Keyword: {kw}")
            
            # 【核心修改】每次搜新词都重新打开首页，确保环境干净
            try:
                page.get('http://tonkiang.us/')
                handle_cloudflare(page) # 每次都检查一下盾
                
                # 寻找输入框
                search_input = page.ele('tag:input@@type!=hidden', timeout=5)
                if search_input:
                    search_input.clear()
                    search_input.input(f"{kw}\n")
                    print(f"   - Searching for {kw}...")
                    page.wait(3) # 等待结果加载
                else:
                    print(f"❌ Input box not found for {kw}, skipping.")
                    continue

                # 提取链接
                items = page.eles('text:://')
                found_count = 0
                
                for item in items:
                    try:
                        # 1. 提取 URL
                        txt = item.text
                        url_match = re.search(r'((?:http|https|rtmp|rtsp)://[^\s<>"\u4e00-\u9fa5]+)', txt)
                        if not url_match: continue
                        url = url_match.group(1)

                        # 【核心修改】去重：如果这个链接已经抓过，就跳过
                        if url in seen_urls:
                            continue

                        # 2. 提取并检查日期
                        container = item
                        date_str = ""
                        # 向上找 3 层父级元素看看有没有日期
                        for _ in range(3):
                            container = container.parent()
                            if not container: break
                            mat = re.search(r'(\d{2,4}-\d{1,2}-\d{2,4})', container.text)
                            if mat:
                                date_str = mat.group(1)
                                break
                        
                        # 3. 验证日期有效性
                        if date_str:
                            try:
                                if len(date_str.split('-')[0]) == 4:
                                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                                else:
                                    dt = datetime.strptime(date_str, '%m-%d-%Y')
                                
                                if dt >= time_threshold:
                                    # 只有日期符合才加入
                                    final_results.append(f"{kw},{url}")
                                    seen_urls.add(url) # 标记为已抓取
                                    found_count += 1
                                    print(f"     -> Found: {date_str} | {url[:30]}...")
                            except: pass
                    except: continue
                
                print(f"   - {kw}: Added {found_count} new unique links.")

            except Exception as e:
                print(f"❌ Error scraping {kw}: {e}")
                continue

    except Exception as e:
        print(f"❌ Global Error: {e}")
    finally:
        if page: page.quit()
        try: shutil.rmtree(temp_user_dir)
        except: pass

    # --- 4. 保存文件 ---
    print(f"\n💾 Saving {len(final_results)} total items...")
    
    with open("tv.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        if not final_results:
            f.write("# No data found.\n")
        for item in final_results:
            try:
                name, url = item.split(',')
                f.write(f"#EXTINF:-1,{name}\n{url}\n")
            except: pass

    with open("tv.txt", "w", encoding="utf-8") as f:
        if not final_results:
            f.write("No data found.")
        else:
            f.write("\n".join(final_results))

if __name__ == "__main__":
    main()
