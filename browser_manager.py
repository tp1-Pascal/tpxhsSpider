import asyncio
import random
from typing import List, Optional, Dict, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from scraper import SELECTORS, SEARCH_SELECTORS

class BrowserManager:
    """
    Manages Browser interactions using Playwright.
    Handles lifecycle, navigation, search, and data extraction.
    """
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
    async def start(self):
        """Initializes the browser session with persistent storage and manual stealth."""
        user_data_dir = "./browser_data"  # Path to store cookies/session
        self.playwright = await async_playwright().start()
        
        # Use launch_persistent_context to keep login state
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=self.headless,
            channel="chrome", # Try to use installed Chrome for better evasion
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='zh-CN',
            args=[
                '--disable-blink-features=AutomationControlled',
                '--start-maximized',
                '--no-default-browser-check'
            ]
        )
        
        # Manual Stealth Scripts
        # 1. Mask webdriver
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        # 2. Mock plugins
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
        """)
        
        # 3. Mask permissions
        await self.context.add_init_script("""
            const originalQuery = window.navigator.permissions.query;
            return window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        # 4. WebGL Vendor
        await self.context.add_init_script("""
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                // UNMASKED_VENDOR_WEBGL
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                // UNMASKED_RENDERER_WEBGL
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter(parameter);
            };
        """)

        if len(self.context.pages) > 0:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()
            
        print("🌐 Browser launched with persistent profile (Manual Stealth).")
        print("💡 Note: Please log in manually if prompted. Session will be saved.")

    async def close(self):
        """Closes the browser session."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("🛑 Browser closed.")

    async def human_delay(self, min_ms: int = 2000, max_ms: int = 5000):
        """Random delay to simulate human behavior."""
        await self.page.wait_for_timeout(random.randint(min_ms, max_ms))

    async def _simulate_human_behavior(self):
        """Simulates random mouse movements and scrolling."""
        # Random mouse move
        x = random.randint(100, 1000)
        y = random.randint(100, 800)
        await self.page.mouse.move(x, y, steps=10)
        await self.human_delay(500, 1000)
        
        # Random small scroll
        await self.page.mouse.wheel(0, random.randint(100, 300))
        await self.human_delay(1000, 2000)

    async def check_login_status(self) -> bool:
        """
        Checks if the user is logged in by looking for common logged-in elements.
        """
         # Selectors that indicate a logged-in state
        selectors = [
            ".user-container", 
            "#userAvatar", 
            ".avatar-wrapper", 
            "a[href*='/user/profile']", 
            ".side-bar .user",          
            "#creator-center",          
            ".publish-btn"              
        ]
        
        combined_selector = ", ".join(selectors)
        try:
            print("   (Checking for login indicators...)")
            await self.page.wait_for_selector(combined_selector, state='attached', timeout=5000)
            return True
        except:
            return False

    async def goto_search_page(self, keyword: str):
        """Navigates to the search page for a keyword."""
        # Clean keyword and encode
        import urllib.parse
        encoded_kw = urllib.parse.quote(keyword)
        url = f"https://www.xiaohongshu.com/search_result?keyword={encoded_kw}&source=web_search_result_notes"
        
        print(f"🔍 Navigating to search: {keyword}")
        
        # Set Referer to look legitimate
        await self.page.set_extra_http_headers({
            "Referer": "https://www.xiaohongshu.com/"
        })
        
        await self.page.goto(url, wait_until="domcontentloaded")
        await self._simulate_human_behavior()
        
        try:
            await self.page.wait_for_load_state('networkidle', timeout=8000)
        except:
            pass
            
        await self.human_delay(3000, 6000)

    async def get_search_results(self, count: int = 5) -> List[str]:
        """
        Extracts note URLs from the search result page.
        """
        urls = set()
        retries = 0
        max_retries = 5
        
        print(f"📃 collecting up to {count} URLs...")
        
        while len(urls) < count and retries < max_retries:
            # Scroll down
            await self.page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await self._simulate_human_behavior()
            
            # Robust Link Extraction
            links = await self.page.locator("a").evaluate_all("""
                elements => elements.map(e => {
                    return {
                        href: e.href,
                        text: e.innerText
                    }
                })
            """)
            
            original_count = len(urls)
            
            for item in links:
                link = item.get('href', '')
                if "/explore/" in link or "/discovery/item/" in link:
                    if "user/profile" not in link:
                        clean_link = link.split('?')[0]
                        full_link = f"https://www.xiaohongshu.com{clean_link}" if clean_link.startswith("/") else clean_link
                        urls.add(full_link)
            
            new_count = len(urls)
            print(f"   Found {new_count} unique URLs (added {new_count - original_count})")
            
            if len(urls) >= count:
                break
            
            if new_count == original_count:
                print("   No new items found, waiting longer...")
                await self.human_delay(2000, 4000)
                
            retries += 1
            
        return list(urls)[:count]
    
    async def extract_note_content(self, url: str) -> Dict[str, Any]:
        """
        Navigates to a note detail page and extracts content.
        """
        print(f"📄 Scraping Note: {url}")
        try:
            await self.page.goto(url, wait_until="domcontentloaded")
            await self.human_delay(2000, 4000)
            
            data = {}
            
            # Title
            for sel in SELECTORS["title"]:
                if await self.page.locator(sel).count() > 0:
                    data["title"] = await self.page.locator(sel).first.inner_text()
                    break
            
            # Content
            for sel in SELECTORS["content"]:
                if await self.page.locator(sel).count() > 0:
                    data["content"] = await self.page.locator(sel).first.inner_text()
                    break
            
            # Stats (Likes, Collects, Comments)
            for key in ["likes", "collects", "comments", "author"]:
                for sel in SELECTORS[key]:
                    if await self.page.locator(sel).count() > 0:
                        text = await self.page.locator(sel).first.inner_text()
                        data[key] = text
                        break
            
            # Images
            imgs = []
            for sel in SELECTORS["images"]:
                elements = await self.page.locator(sel).all()
                for el in elements:
                    src = await el.get_attribute("src")
                    # Handle background-image if needed
                    if src and "http" in src:
                        imgs.append(src)
                if imgs: 
                    break
            
            data["images"] = list(set(imgs))
            return data
            
        except Exception as e:
            print(f"❌ Error scraping {url}: {e}")
            return {}

    # Removing old methods to avoid confusion
    # async def goto_search_page...

