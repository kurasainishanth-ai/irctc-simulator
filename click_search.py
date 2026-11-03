from playwright.sync_api import sync_playwright
import time
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    page = browser.contexts[0].pages[0]
    
    if 'train-list' in page.url:
        if page.locator("text='12759'").count() == 0:
            print('Clicking Search')
            try:
                page.get_by_role('button', name='Modify Search').first.click(timeout=2000)
                time.sleep(1)
            except: pass
            try:
                page.get_by_role('button', name='Search').first.click(timeout=2000)
            except: pass
