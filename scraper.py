# -*- coding: utf-8 -*-
"""
小红书详情页内容抓取器 - Phase 1
用于提取小红书笔记详情页的关键信息并保存到JSON文件
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


# 数据保存路径
DATA_FILE = Path(__file__).parent / "xiaohongshu_data.json"


def is_xiaohongshu_detail_page(url: str) -> bool:
    """
    检测URL是否为小红书笔记详情页
    
    支持的URL格式:
    - https://www.xiaohongshu.com/explore/xxxxx
    - https://www.xiaohongshu.com/discovery/item/xxxxx
    """
    if not url:
        return False
    
    patterns = [
        r'xiaohongshu\.com/explore/[a-zA-Z0-9]+',
        r'xiaohongshu\.com/discovery/item/[a-zA-Z0-9]+',
    ]
    
    return any(re.search(pattern, url) for pattern in patterns)


def parse_count(text: str) -> int:
    """
    解析数字文本，支持 "1.2万" 这种格式
    """
    if not text:
        return 0
    
    text = text.strip()
    
    # 移除非数字字符（保留小数点和万/亿）
    if '万' in text:
        num = re.search(r'[\d.]+', text)
        if num:
            return int(float(num.group()) * 10000)
    elif '亿' in text:
        num = re.search(r'[\d.]+', text)
        if num:
            return int(float(num.group()) * 100000000)
    else:
        num = re.search(r'\d+', text)
        if num:
            return int(num.group())
    
    return 0


def extract_note_data(url: str, dom_content: dict) -> dict:
    """
    从DOM内容中提取笔记数据
    
    参数:
        url: 页面URL
        dom_content: 包含各字段的字典
        
    返回:
        笔记数据字典
    """
    return {
        "url": url,
        "title": dom_content.get("title", ""),
        "content": dom_content.get("content", ""),
        "likes": parse_count(dom_content.get("likes", "0")),
        "collects": parse_count(dom_content.get("collects", "0")),
        "comments": parse_count(dom_content.get("comments", "0")),
        "author": dom_content.get("author", ""),
        "images": dom_content.get("images", []),
        "scraped_at": datetime.utcnow().isoformat() + "Z"
    }


def load_existing_data() -> list:
    """
    加载已有的JSON数据
    """
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_to_json(note_data: dict) -> tuple[bool, str]:
    """
    保存笔记数据到JSON文件（去重追加）
    
    返回:
        (是否成功保存, 消息)
    """
    existing_data = load_existing_data()
    
    # 检查是否重复（根据URL判断）
    existing_urls = {item.get("url") for item in existing_data}
    if note_data["url"] in existing_urls:
        return False, "该笔记已存在，跳过保存"
    
    # 追加新数据
    existing_data.append(note_data)
    
    # 保存到文件
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)
    
    return True, f"共 {len(existing_data)} 条"


def format_success_message(title: str, total_count: int) -> str:
    """
    格式化成功消息
    """
    # 标题截取前20个字符
    short_title = title[:20] + "..." if len(title) > 20 else title
    return f"✅ 已保存：{short_title} 共 {total_count} 条"


def format_error_message(message: str) -> str:
    """
    格式化错误消息
    """
    return f"⚠️ {message}"


# DOM选择器配置（供browser_subagent参考）
SELECTORS = {
    "title": [
        "#detail-title",
        ".note-content .title",
        "[class*='title']"
    ],
    "content": [
        "#detail-desc",
        ".note-text",
        ".desc",
        "[class*='desc']"
    ],
    "likes": [
        ".like-wrapper span",
        "[class*='like'] span",
        ".engage-bar .like span"
    ],
    "collects": [
        ".collect-wrapper span", 
        "[class*='collect'] span",
        ".engage-bar .collect span"
    ],
    "comments": [
        ".chat-wrapper span",
        "[class*='comment'] span",
        ".engage-bar .chat span"
    ],
    "author": [
        ".author-wrapper .name",
        ".user-info .name",
        "[class*='author'] .name"
    ],
    "images": [
        ".carousel img",
        ".swiper-slide img",
        ".note-slider img",
        "[class*='slider'] img"
    ]
}


# ============== Phase 2: 批量抓取功能 ==============

# 待抓取列表文件路径
PENDING_FILE = Path(__file__).parent / "pending_urls.json"


def is_xiaohongshu_search_page(url: str) -> bool:
    """
    检测URL是否为小红书搜索结果页
    
    支持的URL格式:
    - https://www.xiaohongshu.com/search_result?keyword=xxx
    - https://www.xiaohongshu.com/search_result/xxx
    """
    if not url:
        return False
    
    patterns = [
        r'xiaohongshu\.com/search_result',
    ]
    
    return any(re.search(pattern, url) for pattern in patterns)


def load_pending_urls() -> dict:
    """
    加载待抓取URL列表
    """
    if PENDING_FILE.exists():
        try:
            with open(PENDING_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (json.JSONDecodeError, IOError):
            pass
    
    return {
        "keyword": "",
        "created_at": "",
        "urls": [],
        "scraped_urls": []
    }


def save_pending_urls(data: dict) -> None:
    """
    保存待抓取URL列表
    """
    with open(PENDING_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_urls_to_pending(urls: list, keyword: str = "") -> tuple[int, int]:
    """
    添加URL到待抓取列表（去重）
    
    返回:
        (新增数量, 总数量)
    """
    pending = load_pending_urls()
    
    # 更新关键词和时间
    if keyword:
        pending["keyword"] = keyword
    if not pending["created_at"]:
        pending["created_at"] = datetime.utcnow().isoformat() + "Z"
    
    # 获取已存在的URL集合
    existing_urls = set(pending.get("urls", []))
    scraped_urls = set(pending.get("scraped_urls", []))
    
    # 同时检查已抓取的数据
    existing_data = load_existing_data()
    scraped_data_urls = {normalize_url(item.get("url", "")) for item in existing_data}
    
    # 添加新URL（去重）
    new_count = 0
    for url in urls:
        normalized = normalize_url(url)
        if normalized and normalized not in existing_urls and normalized not in scraped_urls and normalized not in scraped_data_urls:
            pending["urls"].append(url)
            existing_urls.add(normalized)
            new_count += 1
    
    save_pending_urls(pending)
    
    return new_count, len(pending["urls"])


def normalize_url(url: str) -> str:
    """
    标准化URL，去除查询参数以便比较
    """
    if not url:
        return ""
    
    # 提取主要部分（去除token等参数）
    match = re.search(r'(xiaohongshu\.com/explore/[a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    
    match = re.search(r'(xiaohongshu\.com/discovery/item/[a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    
    return url


def mark_url_as_scraped(url: str) -> None:
    """
    将URL标记为已抓取
    """
    pending = load_pending_urls()
    normalized = normalize_url(url)
    
    # 从待抓取列表中移除
    pending["urls"] = [u for u in pending["urls"] if normalize_url(u) != normalized]
    
    # 添加到已抓取列表
    if "scraped_urls" not in pending:
        pending["scraped_urls"] = []
    if normalized not in pending["scraped_urls"]:
        pending["scraped_urls"].append(normalized)
    
    save_pending_urls(pending)


def is_url_in_pending(url: str) -> bool:
    """
    检查URL是否在待抓取列表中
    """
    pending = load_pending_urls()
    normalized = normalize_url(url)
    
    for pending_url in pending.get("urls", []):
        if normalize_url(pending_url) == normalized:
            return True
    
    return False


def get_progress() -> dict:
    """
    获取抓取进度
    """
    pending = load_pending_urls()
    existing_data = load_existing_data()
    
    return {
        "pending": len(pending.get("urls", [])),
        "scraped": len(pending.get("scraped_urls", [])),
        "total_data": len(existing_data),
        "keyword": pending.get("keyword", "")
    }


def format_progress_message(title: str, scraped: int, total: int) -> str:
    """
    格式化进度消息（Phase 2格式）
    """
    short_title = title[:15] + "..." if len(title) > 15 else title
    return f"✅ 已抓取 {scraped}/{total}：{short_title}"


def format_not_in_list_message() -> str:
    """
    格式化非列表链接提示
    """
    return "⚠️ 这个链接不在待抓取列表中，是否仍要抓取？"


# 搜索结果页的链接选择器（供browser_subagent参考）
SEARCH_SELECTORS = {
    "note_links": [
        "a[href*='/explore/']",
        "a[href*='/discovery/item/']",
        ".note-item a",
        ".feeds-container a[href*='explore']"
    ]
}

