import json
import os
import httpx
import asyncio
from datetime import datetime

async def download_image(url, path):
    if not url:
        return False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                with open(path, 'wb') as f:
                    f.write(response.content)
                return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
    return False

async def process_keyword_results(keyword: str, new_data: list, total_keywords: int = 10):
    """
    处理单个关键词的抓取结果：下载图片、保存数据、更新进度
    """
    # 1. 确保目录存在
    os.makedirs("output/images", exist_ok=True)

    # 2. 下载图片并更新本地路径
    for i, item in enumerate(new_data):
        # 提取关键词前缀或从 item 中获取更准确的字段
        img_filename = f"{keyword}_{i+1}.jpg"
        img_path = os.path.join("output/images", img_filename)
        # 兼容两种字段名 image_url (process_result) 和 images (scraper)
        img_url = item.get('image_url') or (item.get('images', [None])[0] if item.get('images') else None)
        
        if img_url:
            success = await download_image(img_url, img_path)
            if success:
                item['local_image_path'] = img_path
                print(f"Downloaded: {img_filename}")
            else:
                item['local_image_path'] = None
        else:
            item['local_image_path'] = None

    # 3. 合并到主文件
    main_file = "output/data.json"
    history = []
    if os.path.exists(main_file):
        try:
            with open(main_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
                # Fail-safe: if history is not a list (e.g. corrupted or old format), reset it
                if not isinstance(history, list):
                    history = []
        except:
            history = []

    # 按 PRD 要求的平铺结构追加数据，而不是按关键词字典分组
    for item in new_data:
        if not isinstance(item, dict):
            continue
            
        item['keyword'] = keyword
        item['scraped_at'] = datetime.now().isoformat()
        
        # 检查重复 (基于 URL)
        # 确保 history 中的 h 也是字典
        is_duplicate = False
        for h in history:
            if isinstance(h, dict) and h.get('url') == item.get('url'):
                is_duplicate = True
                break
        
        if not is_duplicate:
            history.append(item)

    with open(main_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    # 4. 更新进度
    progress_file = "output/progress.json"
    progress = {"completed_keywords": [], "total_keywords": total_keywords}
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress = json.load(f)
                if not isinstance(progress, dict):
                     progress = {"completed_keywords": [], "total_keywords": total_keywords}
        except:
            pass
    
    if "completed_keywords" not in progress or not isinstance(progress["completed_keywords"], list):
        progress["completed_keywords"] = []
        
    if keyword not in progress["completed_keywords"]:
        progress["completed_keywords"].append(keyword)
    progress["total_keywords"] = total_keywords

    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

    print(f"Keyword '{keyword}' processed. Total progress: {len(progress['completed_keywords'])}/{total_keywords}")
    return progress

if __name__ == "__main__":
    # 为了保持脚本可独立运行进行简单测试，保留一个示例逻辑，但默认不执行大批量硬编码
    print("This script is now a module. Use automation_manager.py to run the full process.")
