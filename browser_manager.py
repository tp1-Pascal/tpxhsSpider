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

    async def _handle_popups(self):
        """
        Detects and closes obstructing popups (Login, Welcome, Masks).
        """
        try:
            # Check for mask
            mask = self.page.locator(".reds-mask, .mask").first
            if await mask.is_visible():
                print("     🚧 Detected overlay mask/popup. Trying to close...")
                await self.page.keyboard.press("Escape")
                await self.human_delay(500, 1000)
                
                # Try clicking close buttons if ESC didn't work (mask still visible)
                if await mask.is_visible():
                    close_btns = [
                        ".close-circle", ".close-icon", ".icon-close", 
                        "div[aria-label='Close']", ".login-close"
                    ]
                    for sel in close_btns:
                        btn = self.page.locator(sel).first
                        if await btn.is_visible():
                            await btn.click()
                            print(f"     ✅ Clicked close button: {sel}")
                            await self.human_delay(500, 1000)
                            return
        except:
            pass

    async def search_keyword_interactive(self, keyword: str):
        """
        Simulates human search behavior: Go to Home -> Click Input -> Type -> Enter.
        Then applies filters via the "Screening" (筛选) menu as requested.
        """
        print(f"🔍 Searching interactively for: {keyword}")
        
        try:
            # 1. Go to Home
            print("   → Navigating to homepage...")
            await self.page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded")
            await self.human_delay(2000, 4000)
            
            # Handle initial popups
            await self._handle_popups()
            
            # 2. Find Search Input
            print("   → Finding search input...")
            search_input = self.page.locator("input.search-input, input[type='text']").first
            await search_input.wait_for(state='visible', timeout=15000)
            await search_input.click()
            await self.human_delay(500, 1000)
            
            # 3. Clear & Type
            await search_input.fill("")
            await self.human_delay(200, 500)
            print(f"   → Typing '{keyword}'...")
            await search_input.type(keyword, delay=random.randint(100, 300))
            await self.human_delay(1000, 2000)
            
            # 4. Press Enter
            print("   → Pressing Enter...")
            await self.page.keyboard.press("Enter")
            
            # 5. Wait for initial results
            print("   → Waiting for results to load...")
            result_selector = "section.note-item, .feeds-container .note-item"
            await self.page.wait_for_selector(result_selector, timeout=30000)
            await self.human_delay(2000, 3000)

            # 6. Apply Filters (New Logic: Always open menu)
            print("   → Applying filters (Menu Mode)...")
            await self._handle_popups() # Check before filtering
            
            # 6.1 Open Filter Menu
            # Try to pinpoint the filter button more aggressively
            filter_btn = None
            potential_locators = [
                self.page.locator(".filter-box .filter-entry"), # Common class
                self.page.locator("div, span").filter(has_text="筛选"), # Text based
                self.page.locator("[aria-label='筛选']"), # Accessibility
            ]
            
            for loc in potential_locators:
                count = await loc.count()
                for i in range(count):
                    btn = loc.nth(i)
                    if await btn.is_visible():
                        filter_btn = btn
                        break
                if filter_btn: break

            if filter_btn:
                print("     Clicking [筛选] to expand menu...")
                await filter_btn.click()
                await self.human_delay(1000, 2000)
                
                # 6.2 Click "最多点赞" (Most Likes)
                hot_btn = self.page.locator("span, div").filter(has_text="最多点赞").last
                if await hot_btn.is_visible():
                    print("     Clicking [最多点赞]...")
                    await hot_btn.click()
                    await self.human_delay(1500, 3000) # Wait for sort to apply
                else:
                    print("     ⚠️ [最多点赞] option not found in menu (maybe already active?).")

                # 6.3 Click "一周内" (One Week)
                week_btn = self.page.locator("span, div").filter(has_text="一周内").last
                if await week_btn.is_visible():
                    print("     Clicking [一周内]...")
                    await week_btn.click()
                    await self.human_delay(3000, 5000)
                else:
                    print("     ⚠️ [一周内] option not found in menu.")
                
                # 6.4 Collapse menu
                close_btn = self.page.locator("div, span").filter(has_text="收起").last
                if await close_btn.is_visible():
                    await close_btn.click()
                else:
                    # Click body to close if "收起" not found
                    await self.page.mouse.click(0, 0)
                    
                print("     ✅ Filters applied. Waiting for list update...")
                await self.human_delay(2000, 4000)
                
            else:
                print("     ⚠️ [筛选] button not found/visible.")

        except Exception as e:
            print(f"❌ Error during search/filter: {e}")
            raise e

    async def scrape_search_results_interactive(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        New V3 Logic:
        1. Find card.
        2. Command+Click (Mac) to open in NEW TAB.
        3. Switch to new tab, scrape, close tab.
        4. Repeat.
        """
        scraped_data = []
        processed_urls = set()
        
        print(f"📃 Starting New-Tab scraping for {count} items...")
        card_selector = "section.note-item, .feeds-container .note-item"
        
        attempts = 0
        
        while len(scraped_data) < count and attempts < 20:
            await self._handle_popups() # Clear masks before clicking
            
            cards = await self.page.locator(card_selector).all()
            
            for i, card in enumerate(cards):
                if len(scraped_data) >= count:
                    break
                
                try:
                    # Get basic info to dedup
                    link_el = card.locator("a").first
                    # Check if link exists but don't force it to be the click target if unstable
                    if not await link_el.count(): continue
                    
                    href = await link_el.get_attribute("href")
                    if not href or "user/profile" in href: continue
                    
                    full_url = "https://www.xiaohongshu.com" + href if href.startswith("/") else href
                    
                    if full_url in processed_urls:
                        continue
                        
                    print(f"👆 Opening note {len(scraped_data)+1}/{count}: {full_url}")
                    processed_urls.add(full_url)
                    
                    await card.scroll_into_view_if_needed()
                    await self.human_delay(500, 1000)
                    
                    # OPEN IN NEW TAB (Command+Click for Mac)
                    # Use card click but ensure masks are cleared
                    async with self.context.expect_page() as new_page_info:
                        await card.click(modifiers=["Meta"])
                    
                    new_page = await new_page_info.value
                    await new_page.wait_for_load_state("domcontentloaded")
                    await self.human_delay(2000, 4000)
                    
                    # SCRAPE
                    try:
                        note_data = await self._scrape_page_content(new_page)
                        note_data['url'] = full_url
                        if note_data:
                            scraped_data.append(note_data)
                            print(f"   ✅ Scraped: {note_data.get('title', 'No Title')[:20]}...")
                    except Exception as e:
                        print(f"   ⚠️ Failed to scrape page: {e}")
                    
                    # CLOSE
                    await new_page.close()
                    await self.page.bring_to_front()
                    await self.human_delay(1000, 2000)
                    
                except Exception as e:
                    print(f"   ⚠️ Error processing card: {e}")
                    continue
            
            if len(scraped_data) < count:
                print("⬇️ Scrolling for more results...")
                await self.page.evaluate("window.scrollBy(0, window.innerHeight * 1.5)")
                await self.human_delay(3000, 5000)
                attempts += 1
                
        return scraped_data

    async def _scrape_page_content(self, target_page) -> Dict[str, Any]:
        """
        Helper to scrape content from a specific Page object (tab).
        """
        data = {}
        try:
             # Title
            for sel in SELECTORS["title"]:
                if await target_page.locator(sel).count() > 0:
                    data["title"] = await target_page.locator(sel).first.inner_text()
                    break
            
            # Content
            for sel in SELECTORS["content"]:
                if await target_page.locator(sel).count() > 0:
                    data["content"] = await target_page.locator(sel).first.inner_text()
                    break
            
             # Stats
            for key in ["likes", "collects", "comments", "author"]:
                for sel in SELECTORS[key]:
                    if await target_page.locator(sel).count() > 0:
                        data[key] = await target_page.locator(sel).first.inner_text()
                        break
                        
            # Images
            imgs = []
            for sel in SELECTORS["images"]:
                elements = await target_page.locator(sel).all()
                for el in elements:
                    src = await el.get_attribute("src") or await el.get_attribute("style")
                    if src and "http" in src:
                        if "url(" in src:
                            src = src.split('("')[1].split('")')[0]
                        imgs.append(src)
                if imgs: 
                    break
            data["images"] = list(set(imgs))
            return data
        except Exception as e:
            print(f"Error extracting data from page: {e}")
            return {}

    # Removing old methods to avoid confusion
    # async def goto_search_page...

