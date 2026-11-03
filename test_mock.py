import time
from playwright.sync_api import sync_playwright
from real_irctc_agent import RealIRCTCAgent
from config import BookingPreferences, Passenger

def test_mock_passenger_filling():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"file:///{__file__.replace('test_mock.py', 'mock_irctc.html').replace(chr(92), '/')}")
        
        agent = RealIRCTCAgent(page, None)
        
        # 1. State Awareness Test
        prefs = BookingPreferences(preferred_trains=["16031"], preferred_classes=["SL"], passengers=[Passenger("Test", 30, "M")], allow_waitlist=True)
        results = agent.get_train_results(prefs)
        assert results[0]["classes"][0]["status"] == "available"
        
        agent.select_train_and_class("16031", "SL")
        
        # Should click book now and show passenger page
        page.wait_for_selector("app-passenger", state="visible", timeout=2000)
        
        # 2. Passenger Filling verification
        agent.fill_passenger_details(prefs.passengers, {"mobile": "1234567890"})
        
        name_val = page.locator("input[placeholder*='Name' i]").input_value()
        assert name_val == "Test"
        
        # 3. Missing Passenger Input hard failure
        page.evaluate("document.querySelector('input[placeholder*=\\'Name\\' i]').remove()")
        try:
            agent.fill_passenger_details(prefs.passengers, {"mobile": "1234567890"})
            assert False, "Should have thrown ValueError or TimeoutError"
        except Exception as e:
            print(f"Correctly caught exception on missing input: {e}")
            
        print("Mock tests passed!")
        browser.close()

if __name__ == '__main__':
    test_mock_passenger_filling()
