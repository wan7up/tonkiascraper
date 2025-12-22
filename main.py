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
            if "Just a moment" not in title and ("IPTV" in title or "Search" in title or "Tonkiang" in title):
                print(f"✅ Access Granted! (Title: {title})")
                return True
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
    # 你的原版关键词列表
    keywords = ["无线新闻", "广东体育", "翡翠台", "VIU", "tvb plus", "now SPORTS PRIME", "Now Sports 精選", "Discovery", "國家地理", "NatGeo", "HBO"]
    days_limit = 30
    time_threshold = datetime.now() - timedelta(days=days_limit)
    
    final_results = []
    seen_urls = set()

    try:
        # --- 3. 循环搜索关键词 ---
        for kw in keywords:
            print(f"\n🚀 Processing Keyword: {kw}")
            
            try:
                page.get('http://tonkiang.us/')
                handle_cloudflare(page) 
                
                # 寻找输入框
                search_input = page.ele('tag:input@@type!=hidden', timeout=5)
                if search_input:
                    search_input.clear()
                    # ⚠️ 修改点：只输入文字，不加回车 \n
                    search_input.input(kw)
                    print(f"   - Input keyword: {kw}")
                    
                    # ⚠️ 核心修复：显式寻找并点击搜索按钮
                    # 逻辑：找输入框后面的按钮，或者找 type=submit 的按钮
                    try:
                        search_btn = search_input.next('tag:button') or page.ele('tag:button@@type=submit')
                        if search_btn:
                            print("   - Clicking Search Button...")
                            search_btn.click()
                        else:
                            # 如果实在找不到按钮，再用回车兜底
                            print("   - Button not found, trying Enter...")
                            search_input.input('\n')
                    except Exception as e:
                        print(f"   - Click error: {e}, using Enter fallback.")
                        search_input.input('\n')

                    # 等待页面跳转和加载，给足时间
                    time.sleep(3) 
                    
                    # 检查是否还在首页 (通过链接数量判断)
                    # 如果还是8个，大概率失败了，多等一会儿
                    if len(page.eles('text:://')) <= 8:
                        print("   - Links count low, waiting 3 more seconds...")
                        time.sleep(3)

                else:
                    print(f"❌ Input box not found for {kw}, skipping.")
                    continue

                # 提取链接 (保持你原版的提取逻辑)
                items = page.eles('text:://')
                found_count = 0
                
                # 简单的日志，帮你看清到底是搜到了还是还在首页
                print(f"   - Page analysis: Found {len(items)} raw links.")

                for item in items:
                    try:
                        txt = item.text
                        url_match = re.search(r'((?:http|https|rtmp|rtsp)://[^\s<>"\u4e00-\u9fa5]+)', txt)
                        if not url_match: continue
                        url = url_match.group(1)

                        if url in seen_urls: continue

                        container = item
                        date_str = ""
                        for _ in range(3):
                            container = container.parent()
                            if not container: break
                            mat = re.search(r'(\d{2,4}-\d{1,2}-\d{2,4})', container.text)
                            if mat:
                                date_str = mat.group(1)
                                break
                        
                        if date_str:
                            try:
                                if len(date_str.split('-')[0]) == 4:
                                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                                else:
                                    dt = datetime.strptime(date_str, '%m-%d-%Y')
                                
                                if dt >= time_threshold:
                                    # 格式化一下名字，防止 csv 乱码
                                    final_results.append(f"{kw},{url}")
                                    seen_urls.add(url)
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

    # --- 4. 智能保存 (完全保留你原版的熔断机制) ---
    print(f"\n📊 --- Result Analysis ---")
    new_count = len(final_results)
    print(f"   New results found: {new_count}")

    old_count = 0
    if os.path.exists("tv.m3u"):
        with open("tv.m3u", "r", encoding="utf-8") as f:
            old_count = len([line for line in f if line.startswith("#EXTINF")])
    print(f"   Existing file count: {old_count}")

    threshold = int(old_count * 0.5)
    save_changes = False
    
    if new_count == 0:
        print("❌ No data found. Keeping previous file.")
    elif old_count > 0 and new_count < 5:
        print(f"❌ Result too low (Only {new_count}). Possible failure. Keeping previous file.")
    elif old_count > 0 and new_count < threshold:
        print(f"⚠️ Safety trigger! Count dropped from {old_count} to {new_count}. Keeping previous file.")
    else:
        save_changes = True
        print("✅ Data looks good. Updating file...")

    if save_changes:
        with open("tv.m3u", "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for item in final_results:
                try:
                    name, url = item.split(',')
                    f.write(f"#EXTINF:-1,{name}\n{url}\n")
                except: pass

        with open("tv.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(final_results))
            
        print(f"💾 Saved {new_count} items to tv.m3u and tv.txt")

if __name__ == "__main__":
    main()
