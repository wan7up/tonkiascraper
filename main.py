from DrissionPage import ChromiumPage, ChromiumOptions
from datetime import datetime, timedelta
import re
import os

def main():
    # --- GitHub Actions 专用配置 ---
    co = ChromiumOptions()
    # 强制开启无头模式 (在服务器上必须开启)
    co.set_argument('--headless=new')
    # Linux/Docker 环境必须参数，防止权限报错
    co.set_argument('--no-sandbox') 
    co.set_argument('--disable-gpu')
    
    # 👇【关键修改】自动读取 GitHub Actions 设置的浏览器路径
    # 如果环境变量里有 CHROME_PATH (在云端)，就用它；如果没有 (在本地)，就自动找
    chrome_path = os.getenv('CHROME_PATH')
    if chrome_path:
        print(f"🔧 Using Chrome at: {chrome_path}")
        co.set_paths(browser_path=chrome_path)
    
    try:
        page = ChromiumPage(co)
    except Exception as e:
        print(f"❌ Browser Init Failed: {e}")
        return
    
    # 自动管理浏览器路径 (DrissionPage 会自动寻找或下载)
    page = ChromiumPage(co)
    
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
            
            # 简化的广告处理 (无头模式下通常不需要点击关闭，因为没有视觉渲染，但为了保险保留逻辑)
            # ... (此处省略复杂的点击逻辑，无头模式下脚本通常能直接穿透) ...
            
            # 直接尝试搜索
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
                    # 提取链接
                    url_match = re.search(r'((?:http|https|rtmp|rtsp)://[^\s<>"\u4e00-\u9fa5]+)', item.text)
                    if not url_match: continue
                    url = url_match.group(1)

                    # 向上找日期
                    container = item
                    for _ in range(3):
                        container = container.parent()
                        if not container: break
                        mat = re.search(r'(\d{2,4}-\d{1,2}-\d{2,4})', container.text)
                        if mat:
                            date_str = mat.group(1)
                            # 简单的日期解析
                            if len(date_str.split('-')[0]) == 4:
                                dt = datetime.strptime(date_str, '%Y-%m-%d')
                            else:
                                dt = datetime.strptime(date_str, '%m-%d-%Y')
                            
                            if dt >= time_threshold:
                                final_results.append(f"{kw},{url}")
                                break
                except: continue
    
    except Exception as e:
        print(f"Error: {e}")
    finally:
        page.quit()

    # --- 保存文件 ---
    if final_results:
        # 去重
        unique_data = list(dict.fromkeys(final_results))
        
        # 写入 tv.m3u (文件名改短点方便引用)
        with open("tv.m3u", "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for item in unique_data:
                try:
                    name, url = item.split(',')
                    f.write(f"#EXTINF:-1,{name}\n{url}\n")
                except: pass
        
        # 写入 txt
        with open("tv.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(unique_data))
            
        print(f"✅ Success! Grabbed {len(unique_data)} items.")
    else:
        print("⚠️ No data found.")

if __name__ == "__main__":
    main()
