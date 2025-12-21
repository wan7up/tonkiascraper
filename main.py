from DrissionPage import ChromiumPage, ChromiumOptions
from datetime import datetime, timedelta
import re
import os
import time
import tempfile
import shutil

def handle_cloudflare(page):
    """
    专门处理 Cloudflare 'Just a moment...' 验证页面
    """
    print("🛡️ Checking for Cloudflare protection...")
    
    # 最多尝试 30 秒 (10次 x 3秒)
    for i in range(10):
        try:
            title = page.title
            print(f"   - Current title: {title}")
            
            # 如果标题不再包含 Cloudflare 的特征词，说明过盾成功
            if "Just a moment" not in title and "Attention Required" not in title and "Tonkiang" in title:
                print("✅ Cloudflare passed! (Title changed)")
                return True
            
            # 如果还在盾里，尝试点击验证框
            print(f"   - Waiting for Cloudflare redirect ({i+1}/10)...")
            
            # Cloudflare 的验证框通常在一个 ShadowRoot 里，或者是一个 iframe
            # 尝试点击复选框
            try:
                # 寻找可能的 verify 按钮 (DrissionPage 擅长穿透 Shadow DOM)
                cb = page.ele('@type=checkbox', timeout=1)
                if cb:
                    print("   - Found checkbox, trying to click...")
                    cb.click(by_js=True)
                else:
                    # 有时候是 iframe 里的 Turnstile
                    iframe = page.get_frame('@src^https://challenges.cloudflare.com')
                    if iframe:
                        btn = iframe.ele('@type=checkbox', timeout=1) or iframe.ele('css:.mark', timeout=1)
                        if btn:
                            print("   - Found Turnstile in iframe, clicking...")
                            btn.click(by_js=True)
            except: pass
                
        except: pass
        
        time.sleep(3)
    
    print("❌ Cloudflare bypass failed (Timeout).")
    return False

def main():
    # --- 配置环境 ---
    temp_user_dir = tempfile.mkdtemp()
    co = ChromiumOptions()
    co.headless(True)
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument(f'--user-data-dir={temp_user_dir}')
    co.set_argument('--remote-allow-origins=*')
    
    # 伪装成正常的 Windows Chrome 浏览器，降低被拦截概率
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

    # --- 采集逻辑 ---
    keywords = ["无线新闻", "广东体育", "翡翠台"]
    days_limit = 60 # 保持宽泛
    final_results = []
    time_threshold = datetime.now() - timedelta(days=days_limit)

    try:
        print(f"🚀 Start scraping...")
        page.get('http://tonkiang.us/')
        
        # 👇👇👇 核心：调用过盾逻辑 👇👇👇
        # 这里会循环等待，直到盾消失，或者超时
        if not handle_cloudflare(page):
            print("⚠️ Warning: Cloudflare might still be active, trying to proceed anyway...")
        
        # 再给一点时间让真正的页面渲染
        time.sleep(2)
        print(f"📄 Real Page Title: {page.title}")

        for kw in keywords:
            print(f"🔎 Checking: {kw}...")
            try:
                # 寻找输入框
                search_input = page.ele('tag:input@@type!=hidden', timeout=5)
                if search_input:
                    search_input.clear()
                    search_input.input(f"{kw}\n")
                    page.wait(3)
                else:
                    print("❌ Input not found (Still blocked?), skipping...")
                    # 如果还是找不到，可能还在盾里，尝试刷新再次触发过盾逻辑
                    page.refresh()
                    handle_cloudflare(page)
                    continue
            except: continue

            # 采集链接
            items = page.eles('text:://')
            print(f"   - Found {len(items)} links on page")
            
            for item in items:
                try:
                    txt = item.text
                    url_match = re.search(r'((?:http|https|rtmp|rtsp)://[^\s<>"\u4e00-\u9fa5]+)', txt)
                    if not url_match: continue
                    url = url_match.group(1)

                    container = item
                    for _ in range(3):
                        container = container.parent()
                        if not container: break
                        mat = re.search(r'(\d{2,4}-\d{1,2}-\d{2,4})', container.text)
                        if mat:
                            date_str = mat.group(1)
                            try:
                                if len(date_str.split('-')[0]) == 4:
                                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                                else:
                                    dt = datetime.strptime(date_str, '%m-%d-%Y')
                                
                                if dt >= time_threshold:
                                    final_results.append(f"{kw},{url}")
                                    print(f"     -> Valid: {date_str}")
                                    break
                            except: pass
                except: continue

    except Exception as e:
        print(f"❌ Global Error: {e}")
    finally:
        if page: page.quit()
        try: shutil.rmtree(temp_user_dir)
        except: pass

    # --- 保存文件 ---
    print(f"💾 Saving {len(final_results)} items...")
    unique_data = list(dict.fromkeys(final_results))
    
    with open("tv.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        if not unique_data:
            f.write("# No data found (Check Logs)\n")
        for item in unique_data:
            try:
                name, url = item.split(',')
                f.write(f"#EXTINF:-1,{name}\n{url}\n")
            except: pass

    with open("tv.txt", "w", encoding="utf-8") as f:
        if not unique_data:
            f.write("No data found.")
        else:
            f.write("\n".join(unique_data))

if __name__ == "__main__":
    main()
