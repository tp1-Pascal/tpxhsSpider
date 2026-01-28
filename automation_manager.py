import asyncio
import random
from pathlib import Path
from datetime import datetime
from browser_manager import BrowserManager
from scraper import extract_note_data, save_to_json, save_pending_urls, load_pending_urls
from process_result import process_keyword_results

# 配置
KEYWORDS_FILE = Path("keywords.md")
MAX_NOTES_PER_KEYWORD = 5 # Fallback default

def parse_keywords(file_path: Path):
    """解析关键词文件，支持 "关键词" 或 "关键词: 数量" 格式"""
    if not file_path.exists():
        return []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    keywords_data = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # 处理 Markdown 列表格式 "- 关键词"
        if line.startswith('- '):
            content = line[2:].strip()
        else:
            content = line
            
        # 解析数量 (例如 "失眠: 10")
        parts = content.split(':', 1)
        keyword = parts[0].strip()
        count = MAX_NOTES_PER_KEYWORD
        
        if len(parts) > 1:
            try:
                count = int(parts[1].strip())
            except ValueError:
                pass
                
        keywords_data.append({"keyword": keyword, "count": count})
            
    return keywords_data

async def run_automation():
    """主执行逻辑 - Standalone Version"""
    print("🚀 启动小红书自动抓取 (Standalone Mode)")
    
    # 1. 准备关键词
    all_keywords_data = parse_keywords(KEYWORDS_FILE)
    if not all_keywords_data:
        print("❌ 未能解析到关键词，请检查 keywords.md")
        return

    print(f"📋 共 {len(all_keywords_data)} 个关键词待处理。")
    
    # 2. 初始化浏览器
    # 建议首次运行使用 headless=False 以便观察和手动过验证
    browser = BrowserManager(headless=False) 
    await browser.start()
    
    # 3. 登录检查与交互
    print("⏳正在检查登录状态...")
    # Go to home page to check login status
    await browser.page.goto("https://www.xiaohongshu.com")
    is_logged_in = await browser.check_login_status()
    
    if not is_logged_in:
        print("\n⚠️  检测到未登录！")
        print("请在弹出的浏览器窗口中手动登录小红书账户。")
        print("登录完成后，请在下方输入 'yes' 继续...")
        
        while True:
            # Note: In an async loop, input() blocks. For a simple script this is fine.
            user_input = input(">> 是否已完成登录？(yes/no): ").strip().lower()
            if user_input == 'yes':
                print("⏳ 正在刷新页面以确认状态...")
                await browser.page.reload(wait_until="domcontentloaded")
                await asyncio.sleep(2) # Wait for hydration
                
                print("⏳ 正在再次校验登录状态...")
                is_logged_in = await browser.check_login_status()
                if is_logged_in:
                    print("✅ 校验成功！继续执行...")
                    break
                else:
                    print("❌ 检测到仍未登录，请确保页面显示已登录状态（如看到头像）。")
            elif user_input == 'no':
                print("退出程序。")
                await browser.close()
                return
    else:
        print("✅ 检测到已登录，自动继续...")
    
    try:
        for item in all_keywords_data:
            keyword = item['keyword']
            target_count = item['count']
            
            print(f"\n🔍 正在处理关键词: {keyword} (目标数量: {target_count})")
            
            try:
                # 3.1 进入搜索页
                await browser.goto_search_page(keyword)
                
                # 3.2 获取笔记链接
                urls = await browser.get_search_results(count=target_count)
                print(f"🔗 找到 {len(urls)} 个笔记链接")
                
                new_items = []
                for url in urls:
                    try:
                        # 3.3 抓取内容
                        # Go to detail page directly
                        data = await browser.extract_note_content(url)
                        if data:
                            data['url'] = url
                            new_items.append(data)
                            print(f"   ✅ Saved: {data.get('title', 'No Title')[:20]}...")
                        else:
                             print(f"   ⚠️ Failed to extract content from {url}")
                             
                    except Exception as e:
                        print(f"❌ Error scraping {url}: {e}")
                        continue
                
                if new_items:
                    print(f"📥 Processing images for {len(new_items)} items...")
                    process_keyword_results(keyword, new_items, total_keywords=len(all_keywords_data))
                
                wait_time = random.uniform(5, 10)
                print(f"💤 关键词间休息 {wait_time:.1f} 秒...")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                 print(f"❌ Error processing keyword '{keyword}': {e}")
                 # Try to recover navigation
                 try:
                     await browser.page.goto("https://www.xiaohongshu.com")
                 except: pass
                 continue
                
    except KeyboardInterrupt:
        print("\n🛑 用户终止了程序。")
    finally:
        await browser.close()
        print("🏁 任务完成")

if __name__ == "__main__":
    asyncio.run(run_automation())
