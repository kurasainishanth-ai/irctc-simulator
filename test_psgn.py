import time
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    page = browser.contexts[0].pages[0]
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if 'irctc.co.in' in pg.url:
                page = pg
                break
    
    # Fill details
    name_input = page.locator("app-passenger input[placeholder*='Name' i]").first
    name_input.fill("Test User")
    name_input.press("Tab")
    
    age_input = page.locator("app-passenger input[placeholder*='Age' i]").first
    age_input.fill("30")
    age_input.press("Tab")
    
    gender = page.locator("app-passenger select[formcontrolname='passengerGender']").first
    gender.select_option(value="M")
    
    time.sleep(1)
    # Check if there are still errors
    errors = page.locator(".ui-messages-error, .error, .ng-invalid, .ui-toast-message-content").all()
    for e in errors:
        if e.is_visible():
            text = e.inner_text().strip()
            if text:
                print("Error:", text)
                
    # Click continue
    btn = page.locator("button", has_text="Continue").first
    btn.click()
    print("Clicked Continue")
    
    try:
        page.wait_for_url("**/reviewBooking**", timeout=5000)
        print("Reached Review!")
    except:
        print("Failed to reach review. URL:", page.url)
