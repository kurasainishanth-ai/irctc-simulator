import os
import time
import json
import re
from typing import Dict, Any, List
from playwright.sync_api import sync_playwright, Request, Response
import sys

# Ensure imports work if executed from root or automation folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from config import AgentConfig, Passenger
    from real_irctc_agent import RealIRCTCAgent
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "automation"))
    from config import AgentConfig, Passenger
    from real_irctc_agent import RealIRCTCAgent


class NetworkMonitor:
    def __init__(self, page):
        self.page = page
        self.requests = {}
        
    def on_request(self, request: Request):
        # Filter sensitive URLs (e.g. passwords, OTP)
        if "captcha" in request.url.lower() or "otp" in request.url.lower():
            return
            
        self.requests[request] = {
            "url": request.url.split("?")[0], # strip query params to mask potential sensitive data
            "method": request.method,
            "resource_type": request.resource_type,
            "start": time.time(),
            "end": None,
            "duration": None,
            "status": None
        }

    def on_response(self, response: Response):
        req_data = self.requests.get(response.request)
        if req_data:
            req_data["end"] = time.time()
            req_data["duration"] = req_data["end"] - req_data["start"]
            req_data["status"] = response.status

    def attach(self):
        self.page.on("request", self.on_request)
        self.page.on("response", self.on_response)

    def detach(self):
        self.page.remove_listener("request", self.on_request)
        self.page.remove_listener("response", self.on_response)

    def get_slowest(self, n=10):
        # filter out incomplete
        completed = [r for r in self.requests.values() if r["duration"] is not None]
        completed.sort(key=lambda x: x["duration"], reverse=True)
        return completed[:n]
        
    def clear(self):
        self.requests.clear()


def wait_for_review(page):
    t_start = time.time()
    last_log = ""
    while time.time() - t_start < 90:
        try:
            curr = page.evaluate("window.location.href")
        except Exception:
            curr = page.url
        if curr != last_log:
            last_log = curr
        if "review" in curr.lower():
            return time.time()
        time.sleep(1.0)
    raise RuntimeError("Review page timeout")


def run_diagnostic():
    with open("v1_config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        page = browser.contexts[0].pages[0]
        
        agent = RealIRCTCAgent(page, AgentConfig("https://www.irctc.co.in"))
        monitor = NetworkMonitor(page)
        
        if "train-list" not in page.url:
            print(f"Browser is not on train-list. Currently on: {page.url}")
            return
            
        print("Executing Train Selection...")
        agent.execute_v1_selection(cfg["train"], cfg["class"])
        
        page.wait_for_function(
            "() => /psgninput/i.test(window.location.href) || !!document.querySelector('app-passenger')", 
            timeout=10000
        )
        print("Reached Passenger Details.")
        
        passengers = [Passenger(**p) for p in cfg["passengers"]]
        
        # --- FIRST TRANSITION ---
        print("\nFilling Passenger Data (Transition 1)...")
        agent.execute_v1_passenger_fill(
            passengers, cfg["contact"], cfg["travel_insurance"], cfg["payment_preference"]
        )
        
        print("Attaching Network Monitor...")
        monitor.attach()
        monitor.clear()
        
        continue_btn = page.get_by_role("button", name="Continue").first
        print("Clicking Continue (Transition 1)...")
        t_click_1 = time.time()
        continue_btn.click(timeout=5000)
        
        t_review_1 = wait_for_review(page)
        dur_1 = t_review_1 - t_click_1
        print(f"Reached Review in {dur_1:.3f}s")
        
        slowest_1 = monitor.get_slowest(10)
        monitor.detach()
        
        # --- PREPARE FOR SECOND TRANSITION ---
        print("\nNavigating Back to Passenger Details...")
        try:
            # We can use the 'Back' button provided by the IRCTC review page if it exists
            back_btn = page.locator("button:has-text('Back')").first
            if back_btn.is_visible(timeout=5000):
                back_btn.click()
            else:
                page.go_back()
        except Exception:
            page.go_back()
            
        page.wait_for_function(
            "() => /psgninput/i.test(window.location.href) || !!document.querySelector('app-passenger')", 
            timeout=10000
        )
        print("Back on Passenger Details.")
        time.sleep(2) # Give the form a moment to settle
        
        # --- SECOND TRANSITION ---
        print("\nForm is already filled from previous transition. Preparing to continue (Transition 2)...")
        
        print("Attaching Network Monitor...")
        monitor.attach()
        monitor.clear()
        
        continue_btn = page.get_by_role("button", name="Continue").first
        print("Clicking Continue (Transition 2)...")
        t_click_2 = time.time()
        continue_btn.click(timeout=5000)
        
        t_review_2 = wait_for_review(page)
        dur_2 = t_review_2 - t_click_2
        print(f"Reached Review in {dur_2:.3f}s")
        
        slowest_2 = monitor.get_slowest(10)
        monitor.detach()
        
        # --- REPORT ---
        print("\n==========================================")
        print("    PASSENGER TO REVIEW LATENCY REPORT    ")
        print("==========================================")
        print(f"FIRST TRANSITION")
        print(f"Continue -> Review: {dur_1:.3f}s")
        print("Slowest Requests:")
        for r in slowest_1:
            print(f"  [{r['method']}] {r['duration']:.3f}s ({r['status']}) - {r['url']}")
            
        print(f"\nSECOND TRANSITION")
        print(f"Continue -> Review: {dur_2:.3f}s")
        print("Slowest Requests:")
        for r in slowest_2:
            print(f"  [{r['method']}] {r['duration']:.3f}s ({r['status']}) - {r['url']}")
            
        print("\nCOMPARISON")
        print(f"First:  {dur_1:.3f}s")
        print(f"Second: {dur_2:.3f}s")
        print(f"Difference: {dur_1 - dur_2:.3f}s")
        print("==========================================\n")


if __name__ == "__main__":
    run_diagnostic()
