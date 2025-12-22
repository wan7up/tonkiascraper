from DrissionPage import ChromiumPage, ChromiumOptions
import re
import time
import os

def main():
    co = ChromiumOptions()
    co.headless(True)
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
    
    # 你的环境配置
    chrome_path = os.getenv('CHROME_PATH')
    if chrome_path:
        co.set_paths(browser_path=chrome_path)

    page = ChromiumPage(co)
    print("✅ Debugger launched!")

    try:
        # 只测试 VIU 这个有问题的词
        kw = "VIU"
        print(f"🚀 Debugging keyword: {kw}...")
        
        page.get('http://tonkiang.us/')
        
        # 简单的过盾
        if "Just a moment" in page.title:
            time.sleep(5)
            
        search_input = page.ele('tag:input@@type!=hidden', timeout=5)
        if search_input:
            search_input.clear()
            search_input.input(kw)
            
            # 点击搜索
            try:
                btn = search_input.next('tag:button') or page.ele('tag:button@@type=submit')
                if btn: btn.click()
            except: pass
            
            time.sleep(3)
            
            # 获取链接元素
            items = page.eles('text:://')
            print(f"🔍 Found {len(items)} links. Analyzing the first 3 items...\n")
            
            # 只分析前 3 个，避免刷屏
            for index, item in enumerate(items[:3]):
                print(f"--- 🧪 Item {index+1} Analysis ---")
                print(f"   [Link Text]: {repr(item.text)}")
                
                # 向上找 3 层，看看台名藏在哪里
                container = item
                for i in range(1, 4):
                    container = container.parent()
                    if not container: break
                    
                    raw_text = container.text
                    # 使用 repr() 可以把换行符 \n 显示出来，让我们看到真实的排版
                    print(f"   [Parent Level {i} Raw Text]: {repr(raw_text)}")
                    
                    # 模拟之前的提取逻辑，看看结果是什么
                    url_match = re.search(r'((?:http|https|rtmp|rtsp)://[^\s<>"\u4e00-\u9fa5]+)', raw_text)
                    if url_match:
                        url = url_match.group(1)
                        # 尝试切割
                        split_text = raw_text.split('http')[0].strip()
                        print(f"      -> logic test (split by http): {repr(split_text)}")
                print("\n")
                
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        page.quit()

if __name__ == "__main__":
    main()
