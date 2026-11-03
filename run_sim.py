from playwright.sync_api import sync_playwright
import time
import subprocess
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--remote-debugging-port=9222'])
    page = browser.new_page()
    page.goto('http://127.0.0.1:5001/login')
    page.fill('input[name="username"]', 'testuser')
    page.click('button[type="submit"]')
    page.wait_for_url('**/train-search')
    page.fill('input[name="source"]', 'HYDERABAD')
    page.fill('input[name="destination"]', 'NEW DELHI')
    page.click('button:has-text("Search")')
    page.wait_for_url('**/train-list')
    print("Browser prepared on Results page.")
    
    # Now run the test script
    result = subprocess.run(
        ["python", "automation/diagnose_review_performance.py"],
        capture_output=True, text=True
    )
    print("SCRIPT OUTPUT:\n" + result.stderr + "\n" + result.stdout)
    browser.close()
