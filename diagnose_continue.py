import time
import json
import re
from playwright.sync_api import sync_playwright
from config import Passenger, AgentConfig
from real_irctc_agent import RealIRCTCAgent, PageState
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def run_diagnostic():
    with open("v1_config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
        
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        page = browser.contexts[0].pages[0]
        agent = RealIRCTCAgent(page, AgentConfig("https://www.irctc.co.in"))
        
        print(f"Initial URL: {page.url}")
        
        # Ensure we start from Results
        while "train-list" not in page.url:
            print(f"Currently on {page.url}. Going back to train-list to avoid stale session...")
            page.go_back()
            time.sleep(2)
            if "login" in page.url or "home" in page.url:
                raise RuntimeError("Went too far back or got kicked out!")
            
        print(f"URL before selection: {page.url}")
        
        if "train-list" in page.url:
            # 1. Reproduce flow up to Passenger Details
            print("Running Phase 1 selection...")
            agent.execute_v1_selection(cfg["train"], cfg["class"])
            
            page.wait_for_function(
                "() => /psgninput/i.test(window.location.href) || !!document.querySelector('app-passenger')", 
                timeout=10000
            )
            print("Reached Passenger Details.")
            
        # 2 & 3. Fill passenger and payment
        passengers = [Passenger(**p) for p in cfg["passengers"]]
        print("Filling passenger and payment...")
        agent.execute_v1_passenger_fill(
            passengers, cfg["contact"], cfg["travel_insurance"], cfg["payment_preference"]
        )
        
        # 4. Click Continue
        print("Clicking Continue...")
        continue_btn = page.get_by_role("button", name="Continue").first
        continue_btn.click(timeout=5000)
        
        # 5. Monitor page
        print("Monitoring page for 60 seconds...")
        t_start = time.time()
        last_overlay = False
        
        while time.time() - t_start < 60:
            url = page.url
            if "review" in url.lower():
                print(f"[{time.time()-t_start:.1f}s] Reached Review page successfully!")
                break
                
            # Check for overlay
            overlay_visible = page.locator(".blockUI.blockOverlay, .irctc-loader").count() > 0 or page.locator("text='Please Wait'").is_visible()
            
            if overlay_visible:
                if not last_overlay:
                    print(f"[{time.time()-t_start:.1f}s] 'Please Wait' overlay APPEARED.")
                    last_overlay = True
            else:
                if last_overlay:
                    print(f"[{time.time()-t_start:.1f}s] 'Please Wait' overlay DISAPPEARED.")
                    # 6. Capture state immediately
                    time.sleep(1) # wait a moment for DOM to settle
                    print("\n--- DIAGNOSTIC CAPTURE ---")
                    print(f"Current URL: {page.url}")
                    
                    # Errors/Toasts
                    errors = page.locator(".ui-messages-error, .error, .ng-invalid.ng-touched").all_inner_texts()
                    if errors:
                        print(f"Validation Errors: {errors}")
                    
                    toasts = page.locator(".ui-toast-message-content").all_inner_texts()
                    if toasts:
                        print(f"Toasts/Modals: {toasts}")
                        
                    dialogs = page.locator(".ui-dialog-content").all_inner_texts()
                    if dialogs:
                        print(f"Dialogs: {dialogs}")
                    
                    # Continue button state
                    cont_btn = page.get_by_role("button", name="Continue").first
                    if cont_btn.is_visible():
                        print(f"Continue Button: Visible, Enabled={cont_btn.is_enabled()}")
                    else:
                        print("Continue Button: Not visible.")
                    
                    print("--------------------------\n")
                    last_overlay = False
                    
            time.sleep(0.5)
            
        print("Diagnostic finished.")

if __name__ == "__main__":
    run_diagnostic()
