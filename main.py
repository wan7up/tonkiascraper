def main():
    # --- 1. 环境配置 ---
    temp_user_dir = tempfile.mkdtemp()
    co = ChromiumOptions()
    co.headless(True)
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--window-size=1920,1080')
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

    # --- 2. 准备数据 ---
    all_data = load_history()
    current_date = datetime.now()
    cutoff_date = current_date - timedelta(days=DAYS_LIMIT)

    try:
        # --- 3. 循环搜索 ---
        for kw in KEYWORDS:
            print(f"\n🚀 Processing Keyword: {kw}")
            
            try:
                page.get('http://tonkiang.us/')
                
                # =========== 📸 调试代码开始 ===========
                # 强制截图，保存到当前目录，用于排查是否被屏蔽
                try:
                    page.get_screenshot(path='debug_proof.png', full_page=True)
                    print("📸 Debug screenshot saved as debug_proof.png")
                except Exception as shot_err:
                    print(f"⚠️ Screenshot failed: {shot_err}")
                # =========== 📸 调试代码结束 ===========

                handle_cloudflare(page) 
                
                search_input = page.ele('tag:input@@type!=hidden', timeout=5)
                if search_input:
                    search_input.clear()
                    search_input.input(kw)
                    
                    # 提交搜索
                    try:
                        search_btn = search_input.next('tag:button') or page.ele('tag:button@@type=submit')
                        if search_btn:
                            search_btn.click()
                        else:
                            search_input.input('\n')
                    except:
                        search_input.input('\n')
                    
                    page.wait(3) 

                else:
                    print(f"❌ Input box not found for {kw}, skipping.")
                    continue

                # --- 4. 通用提取逻辑 ---
                items = page.eles('text:://')
                new_found = 0
                
                for item in items:
                    try:
                        # 1. 提取 URL
                        txt = item.text
                        url_match = re.search(r'((?:http|https|rtmp|rtsp)://[^\s<>"\u4e00-\u9fa5]+)', txt)
                        if not url_match: continue
                        url = url_match.group(1)

                        # 2. 寻找完整信息块
                        container = item
                        full_text_block = ""
                        
                        for _ in range(3):
                            container = container.parent()
                            if not container: break
                            if "\n" in container.text:
                                full_text_block = container.text
                                break
                        
                        if not full_text_block:
                            full_text_block = container.text if container else ""

                        # 3. 按行解析
                        lines = [line.strip() for line in full_text_block.split('\n') if line.strip()]
                        
                        channel_name = "" 
                        date_str = ""
                        
                        for line in lines:
                            if "://" in line: continue
                            
                            mat = re.search(r'(\d{2,4}-\d{1,2}-\d{2,4})', line)
                            if mat:
                                date_str = mat.group(1)
                                continue 
                            
                            if not channel_name:
                                channel_name = line
                        
                        if not channel_name:
                            channel_name = kw

                        # 4. 存入数据
                        if date_str:
                            try:
                                if len(date_str.split('-')[0]) == 4:
                                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                                else:
                                    dt = datetime.strptime(date_str, '%m-%d-%Y')
                                str_date = dt.strftime('%Y-%m-%d')

                                if url in all_data:
                                    if channel_name != kw:
                                        all_data[url]['Channel'] = channel_name
                                    
                                    old_date = datetime.strptime(all_data[url]['Date'], '%Y-%m-%d')
                                    if dt > old_date:
                                        all_data[url]['Date'] = str_date
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
    
    # 只要有有效数据就保存 (即使没有新增，也要更新 M3U 头部)
    if len(valid_data) > 0:
        save_files(valid_data)
    else:
        print("⚠️ No valid data remaining! Skipping save.")
if __name__ == "__main__":
    main()
