from DrissionPage import ChromiumPage, ChromiumOptions
from datetime import datetime, timedelta
import re
import os

def main():
    # --- GitHub Actions 专用配置 ---
    co = ChromiumOptions()
    co.set_argument('--headless=new')
    co.set_argument('--no-sandbox') 
    co.set_argument('--disable-gpu')
    
    # 👇 自动读取 GitHub Actions 设置的浏览器路径
    chrome_path = os.getenv('CHROME_PATH')
    if chrome_path:
        print(f"🔧 Using Chrome at: {chrome_path}")
        co.set_paths(browser_path=chrome_path)
    
    try:
        page = ChromiumPage(co)
    except Exception as e:
        print(f"❌ Browser Init Failed: {e}")
        return
    
    # --- 你的核心逻辑 ---
    keywords = ["无线新闻", "广东体育", "翡翠台"] 
    days_limit = 30
    final_results = [] 
    time_threshold = datetime.now() - timedelta(days=days_limit)

    try:
        print(f"🚀 [GitHub Action] 启动采集 | 范围: 近 {days_limit} 天")
        page.get('http://tonkiang.us/')
        
        for kw in keywords:
            print(f"Checking: {kw}...")
            
            try:
                # 寻找输入框
                search_input = page.ele('tag:input@@type!=hidden', timeout=2)
                if search_input:
                    search_input.clear()
                    search_input.input(f"{kw}\n")
                    page.wait(3)
                else:
                    page.refresh()
                    continue
            except: continue

            # 采集链接
            items = page.eles('text:://')
            for item in items:
                try:
                    url_match = re.search(r'((?:http|https|rtmp|rtsp)://[^\s<>"\u4e00-\u9fa5]+)', item.text)
                    if not url_match: continue
                    url = url_match.group(1)

                    container = item
                    for _ in range(3):
                        container = container.parent()
                        if not container: break
                        mat = re.search(r'(\d{2,4}-\d{1,2}-\d{2,4})', container.text)
                        if mat:
                            date_str = mat.group(1)
                            if len(date_str.split('-')[0]) == 4:
                                dt = datetime.strptime(date_str, '%Y-%m-%d')
                            else:
                                dt = datetime.strptime(date_str, '%m-%d-%Y')
                            
                            if dt >= time_threshold:
                                final_results.append(f"{kw},{url}")
                                # 打印进度到日志
                                print(f"  found: {kw} -> {date_str}")
                                break
                except: continue
    
    except Exception as e:
        print(f"Error: {e}")
    finally:
        page.quit()

    # --- 保存文件 ---
    if final_results:
        unique_data = list(dict.fromkeys(final_results))
        with open("tv.m3u", "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for item in unique_data:
                try:
                    name, url = item.split(',')
                    f.write(f"#EXTINF:-1,{name}\n{url}\n")
                except: pass
        
        with open("tv.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(unique_data))
        print(f"✅ Success! Grabbed {len(unique_data)} items.")
    else:
        print("⚠️ No data found.")

if __name__ == "__main__":
    main()
