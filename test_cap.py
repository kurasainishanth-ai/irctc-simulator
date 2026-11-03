from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    page = browser.contexts[0].pages[0]
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if 'irctc.co.in' in pg.url:
                page = pg
                break
    captcha_inputs = page.locator("input[id*='captcha' i], input[placeholder*='captcha' i]").count()
    print('Captcha input count:', captcha_inputs)
