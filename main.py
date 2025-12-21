from DrissionPage import ChromiumPage, ChromiumOptions
from datetime import datetime, timedelta
import re
import os
import time

def main():
    # --- GitHub Actions 专用配置 ---
    co = ChromiumOptions()
    co.set_argument('--headless=new')
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    
    # 👇【三重修复】同时加上这三个参数，确保万无一失
    co.set_argument('--remote-debugging-port=9222')
    co.set_argument('--remote-allow-origins=*')
    co.set_argument('--bind-address=0.0.0.0') 
    
    # 自动读取 GitHub Actions 设置的浏览器路径
    chrome_path = os.getenv('CHROME_PATH')
    if chrome_path:
        print(f"🔧 Using Chrome at: {chrome_path}")
        co.set_paths(browser_path=chrome_path)

    # 【调试】打印最终参数，确认修复是否生效
    print(f"🔧 Browser Args: {co.arguments}")

    try:
        page = ChromiumPage(co)
        print("✅ Browser launched successfully!")
    except Exception as e:
        print(f"❌ Browser Init Failed: {e}")
        # 如果还是失败，尝试不指定端口让它自己随机（最后的挣扎）
        return

    # --- 采集逻辑 ---
    keywords = ["无线新闻", "广东体育", "翡翠台"]
    days_limit = 60
    final_results = []
    time_threshold = datetime.now() - timedelta(days=days_limit)

    try:
        print(f"🚀 Start scraping...")
        page.get('http://tonkiang.us/')
        time.sleep(2)
        print(f"📄 Page Title: {page.title}")

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
                    print("❌ Input not found, refreshing...")
                    page.refresh()
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
                            # 日期解析
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
        page.quit()

    # --- 强制保存文件 ---
    print(f"💾 Saving {len(final_results)} items...")
    
    unique_data = list(dict.fromkeys(final_results))
    
    with open("tv.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        if not unique_data:
            f.write("# No data found in this run.\n")
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
