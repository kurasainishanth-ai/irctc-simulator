import urllib.request
import json
import logging
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

logger = logging.getLogger(__name__)

class BrowserManager:
    def __init__(self, headless: bool = False, slow_mo: int = 500, cdp_url: str = None):
        self.headless = headless
        self.slow_mo = slow_mo
        self.cdp_url = cdp_url
        self.playwright = None
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
        # True when we attached to a user's existing Chrome via CDP.
        # In that case we must NOT close the browser or context on cleanup,
        # only stop the Playwright client process.
        self._cdp_attached = False

    @classmethod
    def list_tabs(cls, cdp_url="http://127.0.0.1:9222"):
        """Returns a list of available open tabs (pages) from the live browser."""
        try:
            req = urllib.request.urlopen(f"{cdp_url}/json/list", timeout=2)
            targets = json.loads(req.read().decode())
            tabs = []
            logger.info(f"BrowserManager.list_tabs saw {len(targets)} raw targets")
            for t in targets:
                if t.get('type') == 'page' and not t.get('url', '').startswith('chrome-extension') and 'devtools' not in t.get('url', ''):
                    tabs.append({
                        "id": t.get("id"),
                        "title": t.get("title", ""),
                        "url": t.get("url", ""),
                        "webSocketDebuggerUrl": t.get("webSocketDebuggerUrl")
                    })
            logger.info(f"BrowserManager.list_tabs returning {len(tabs)} filtered tabs")
            return tabs
        except Exception as e:
            logger.error(f"Error fetching tabs: {e}")
            return []

    def connect_to_tab(self, target_url: str) -> Page:
        """Connects via CDP to an existing tab that matches the target_url.

        IMPORTANT: This attaches to the user's existing Chrome instance.
        The browser and its tabs are NOT owned by this BrowserManager.
        Call disconnect() when done — NOT stop() — to avoid closing the user's tabs.
        """
        self._cdp_attached = True
        self.playwright = sync_playwright().start()
        try:
            req = urllib.request.urlopen(f"{self.cdp_url}/json/version", timeout=2)
            version = json.loads(req.read().decode())
            browser_ws = version['webSocketDebuggerUrl']
            
            logger.info(f"BrowserManager.connect_to_tab attaching to {browser_ws}")
            self.browser = self.playwright.chromium.connect_over_cdp(browser_ws)
            
            found_urls = []
            for ctx in self.browser.contexts:
                for p in ctx.pages:
                    found_urls.append(p.url)
                    if target_url in p.url:
                        logger.info(f"Matched target_url '{target_url}' with '{p.url}'")
                        self.page = p
                        self.context = ctx
                        break
                if self.page:
                    break
            
            logger.info(f"connect_to_tab observed URLs: {found_urls}")
            if not self.page:
                raise RuntimeError(f"Could not find a tab matching URL: {target_url} among {found_urls}")
            
            try:
                self.page.bring_to_front()
            except Exception as e:
                logger.info(f"Failed bring_to_front: {e}")
                pass
                
            return self.page
            
        except Exception as e:
            logger.error(f"Failed to connect to Chrome: {e}")
            self.disconnect()
            raise

    def start(self) -> Page:
        if self.cdp_url:
            # Requires target_url, use connect_to_tab instead. For backwards compat with tests:
            raise NotImplementedError("Use connect_to_tab for CDP connections.")
            
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=["--window-size=1280,720"]
        )
        self.context = self.browser.new_context(
            viewport={'width': 1280, 'height': 720}
        )
        self.page = self.context.new_page()
        return self.page

    def disconnect(self):
        """Disconnect the Playwright client from a CDP-attached browser.

        Stops the Playwright process WITHOUT closing the browser or any of its
        tabs. Use this after connect_to_tab() so the user's Chrome session is
        preserved for the next run.
        """
        logger.info("BrowserManager.disconnect(): stopping Playwright client only (browser/tabs preserved)")
        # Do not touch self.context or self.browser — they belong to the user's Chrome.
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception as e:
                logger.debug(f"playwright.stop() error during disconnect (non-fatal): {e}")
            finally:
                self.playwright = None
        self.page = None
        self.context = None
        self.browser = None

    def stop(self):
        if self._cdp_attached:
            # We attached to the user's browser — never close it.
            logger.warning(
                "BrowserManager.stop() called on a CDP-attached session. "
                "Redirecting to disconnect() to preserve the user's Chrome tabs."
            )
            self.disconnect()
            return

        if self.context:
            try:
                self.context.close()
            except Exception:
                pass
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass

