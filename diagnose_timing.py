import time
import json
import re
import urllib.request
from playwright.sync_api import sync_playwright
from config import Passenger, AgentConfig
from real_irctc_agent import RealIRCTCAgent

def get_cdp_urls():
    try:
        response = urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=2)
        targets = json.loads(response.read())
        # Return URLs for all pages
        return [t.get("url", "") for t in targets if t.get("type") == "page"]
    except Exception as e:
        return [f"Error: {e}"]

def run_diagnostic():
    with open("v1_config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
        
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        page = browser.contexts[0].pages[0]
        agent = RealIRCTCAgent(page, AgentConfig("https://www.irctc.co.in"))
        
        print(f"Initial URL: {page.url}")
        
        if "train-list" not in page.url:
            print(f"ERROR: Browser is on {page.url}. Please manually navigate to train-list and search the train before running this diagnostic.")
            return
            
        print(f"Starting at: {page.url}")
        print("Running Phase 1 selection...")
        agent.execute_v1_selection(cfg["train"], cfg["class"])
        
        page.wait_for_function(
            "() => /psgninput/i.test(window.location.href) || !!document.querySelector('app-passenger')", 
            timeout=10000
        )
        print("Reached Passenger Details.")
        
        passengers = [Passenger(**p) for p in cfg["passengers"]]
        print("Filling passenger and payment...")
        agent.execute_v1_passenger_fill(
            passengers, cfg["contact"], cfg["travel_insurance"], cfg["payment_preference"]
        )
        
        print("Clicking Continue...")
        continue_btn = page.get_by_role("button", name="Continue").first
        t_click = time.time()
        continue_btn.click(timeout=5000)
        
        print("Monitoring URLs for 120 seconds...")
        
        last_playwright_url = ""
        last_js_url = ""
        last_cdp_url = ""
        
        while time.time() - t_click < 120:
            elapsed = time.time() - t_click
            
            # 1. Playwright cached URL
            p_url = page.url
            
            # 2. JS evaluated URL
            try:
                js_url = page.evaluate("window.location.href")
            except Exception as e:
                js_url = f"Error: {e}"
                
            # 3. Raw CDP URL
            cdp_urls = get_cdp_urls()
            # Find the IRCTC one or just take the first page
            c_url = next((u for u in cdp_urls if "irctc" in u), cdp_urls[0] if cdp_urls else "None")
            
            # Log only on changes to avoid spam
            changed = False
            if p_url != last_playwright_url:
                print(f"[{elapsed:.1f}s] Playwright page.url CHANGED: {p_url}")
                last_playwright_url = p_url
                changed = True
            if js_url != last_js_url:
                print(f"[{elapsed:.1f}s] JS window.location.href CHANGED: {js_url}")
                last_js_url = js_url
                changed = True
            if c_url != last_cdp_url:
                print(f"[{elapsed:.1f}s] CDP Target URL CHANGED: {c_url}")
                last_cdp_url = c_url
                changed = True
                
            # Check if review reached
            if "review" in p_url.lower() or "review" in js_url.lower() or "review" in c_url.lower():
                print(f"[{elapsed:.1f}s] REVIEW PAGE REACHED!")
                print(f"Final Playwright URL: {p_url}")
                print(f"Final JS URL: {js_url}")
                print(f"Final CDP URL: {c_url}")
                break
                
            time.sleep(1.0)
            
        else:
            print("120 seconds elapsed. Did NOT reach review page.")
            
if __name__ == "__main__":
    run_diagnostic()
