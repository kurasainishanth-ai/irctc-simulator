from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    page = browser.contexts[0].pages[0]
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if 'irctc.co.in' in pg.url:
                page = pg
                break
    errors = page.locator('.ui-messages-error, .error, .ng-invalid, .ui-toast-message-content').all()
    for e in errors:
        if e.is_visible():
            print('Error:', e.inner_text().strip())
    
    captcha_box = page.locator('#captcha').all()
    for c in captcha_box:
        print('Captcha input:', c.evaluate('el => el.outerHTML'))
