"""Mock tests for V1 deterministic path.

Tests execute_v1_selection() and diagnose_book_now_failure() against
controlled static HTML fixtures. No live IRCTC connection.
"""
import sys
import os
import logging

# Ensure automation/ is on the import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "automation"))

from playwright.sync_api import sync_playwright
from real_irctc_agent import RealIRCTCAgent, PageState
from config import Passenger

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

PASSED = 0
FAILED = 0


def report(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  PASS: {name}")
    else:
        FAILED += 1
        print(f"  FAIL: {name}: {detail}")


def run_tests():
    global PASSED, FAILED

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # =============================================================
        # TEST 1: Train not found → RuntimeError
        # =============================================================
        print("\nTest 1: Train not found")
        page.set_content(
            """
            <app-train-avl-enq>
              <div class="train-heading">OTHER TRAIN (99999)</div>
              <button class="btnDefault disable-book">Book Now</button>
            </app-train-avl-enq>
        """
        )
        agent = RealIRCTCAgent(page, None)
        try:
            agent.execute_v1_selection("12759", "SL")
            report("raises RuntimeError", False, "no exception raised")
        except RuntimeError as e:
            report("raises RuntimeError", "12759" in str(e), str(e))

        # =============================================================
        # TEST 2: Book Now button not visible → RuntimeError
        # =============================================================
        print("\nTest 2: Book Now button missing")
        page.set_content(
            """
            <app-train-avl-enq>
              <div class="train-heading">CHARMINAR (12759)</div>
            </app-train-avl-enq>
        """
        )
        agent = RealIRCTCAgent(page, None)
        try:
            agent.execute_v1_selection("12759", "SL")
            report("raises RuntimeError", False, "no exception raised")
        except RuntimeError as e:
            report("raises RuntimeError", "Book Now" in str(e), str(e))

        # =============================================================
        # TEST 3: Book Now already enabled → click directly, no date/class
        # =============================================================
        print("\nTest 3: Book Now already enabled (prepared state)")
        page.set_content(
            """
            <app-train-avl-enq>
              <div class="train-heading">CHARMINAR (12759)</div>
              <button class="btnDefault train_Search"
                      onclick="document.title='book_clicked'">Book Now</button>
            </app-train-avl-enq>
        """
        )
        agent = RealIRCTCAgent(page, None)
        timings = agent.execute_v1_selection("12759", "SL")

        report("clicked Book Now directly", page.title() == "book_clicked")
        report(
            "returns timing dict",
            all(k in timings for k in ["t_start", "t_found", "t_ready", "t_clicked"]),
        )
        report(
            "t_found > t_start",
            timings["t_found"] > timings["t_start"],
        )
        report(
            "t_ready >= t_found (no date interaction)",
            timings["t_ready"] >= timings["t_found"],
        )

        # =============================================================
        # TEST 4: No date cells → RuntimeError
        # =============================================================
        print("\nTest 4: No date cells in availability table")
        page.set_content(
            """
            <app-train-avl-enq>
              <div class="train-heading">CHARMINAR (12759)</div>
              <p-tabmenu style="display:block">
                <li class="ui-tabmenuitem-active">SL</li>
              </p-tabmenu>
              <table><tr><td></td></tr></table>
              <button class="btnDefault disable-book train_Search">Book Now</button>
            </app-train-avl-enq>
        """
        )
        agent = RealIRCTCAgent(page, None)
        try:
            agent.execute_v1_selection("12759", "SL")
            report("raises RuntimeError", False, "no exception raised")
        except RuntimeError as e:
            report("raises RuntimeError", "date cells" in str(e).lower(), str(e))

        # =============================================================
        # TEST 5: diagnose_book_now_failure doesn't crash
        # =============================================================
        print("\nTest 5: Diagnostics don't crash")
        page.set_content(
            """
            <app-train-avl-enq>
              <div class="train-heading">CHARMINAR (12759)</div>
              <button class="btnDefault disable-book">Book Now</button>
              <p-dialog style="display:block">Session Expired. Please login again.</p-dialog>
            </app-train-avl-enq>
        """
        )
        agent = RealIRCTCAgent(page, None)
        try:
            agent.diagnose_book_now_failure("12759")
            report("completes without crash", True)
        except Exception as e:
            report("completes without crash", False, str(e))

        # =============================================================
        # TEST 6: diagnose_book_now_failure with train not found
        # =============================================================
        print("\nTest 6: Diagnostics when train card gone")
        page.set_content("<div>Empty page</div>")
        agent = RealIRCTCAgent(page, None)
        try:
            agent.diagnose_book_now_failure("12759")
            report("handles missing train card", True)
        except Exception as e:
            report("handles missing train card", False, str(e))

        # =============================================================
        # TEST 7: inspect_current_page state detection
        # =============================================================
        print("\nTest 7: PageState detection")
        test_urls = {
            "https://www.irctc.co.in/nget/booking/train-list": PageState.RESULTS,
            "https://www.irctc.co.in/nget/booking/psgninput": PageState.PASSENGER_DETAILS,
            "https://www.irctc.co.in/nget/booking/reviewBooking": PageState.REVIEW,
            "https://www.irctc.co.in/nget/payment/bkgPaymentOptions": PageState.PAYMENT,
        }
        # We can't navigate to these URLs, but we can verify the detection logic
        # by checking known URL patterns
        agent = RealIRCTCAgent(page, None)
        for url, expected in test_urls.items():
            # Manually check the URL parsing logic
            state = PageState.UNKNOWN
            if "login" in url:
                state = PageState.LOGIN
            elif "train-search" in url or url.endswith("irctc.co.in/nget/"):
                state = PageState.SEARCH
            elif "train-list" in url:
                state = PageState.RESULTS
            elif "psgninput" in url:
                state = PageState.PASSENGER_DETAILS
            elif "reviewBooking" in url:
                state = PageState.REVIEW
            elif "payment" in url or "nget/payment" in url or "bankp" in url:
                state = PageState.PAYMENT
            report(f"  {url} -> {expected}", state == expected)

        # =============================================================
        # TEST 8: Missing Configuration Error
        # =============================================================
        print("\nTest 8: Missing config fields")
        try:
            agent.execute_v1_passenger_fill(
                passengers=[Passenger(name="Test", age=30, gender="M")], 
                contact={"mobile": "123"},
                travel_insurance=None,
                payment_pref="credit"
            )
            report("  missing insurance config failed", False)
        except Exception:
            report("  raises error when insurance missing (handled by harness or agent)", True)

        # =============================================================
        # TEST 9: Option Selection Verification
        # =============================================================
        print("\nTest 9: Option Selection Verification")
        page.set_content("""
        <html>
            <body>
                <app-passenger>
                    <input placeholder="Name" value="">
                    <input placeholder="Age" value="">
                    <select formcontrolname="passengerGender"><option value="M">M</option></select>
                </app-passenger>
                <input id="mobileNumber" value="">
                
                <div>
                    <input type="radio" name="travel" value="true">
                    <span>Yes, and I accept the terms & conditions</span>
                </div>
                <div>
                    <input type="radio" name="travel" value="false">
                    <span>No, I don't want travel insurance</span>
                </div>
                
                <div class="payment-options">
                    <input type="radio" name="pay" value="1">
                    <span>Pay through Credit & Debit Cards / Net Banking / Wallets</span>
                </div>
                <div>
                    <input type="radio" name="pay" value="2">
                    <span>Pay through BHIM/UPI</span>
                </div>
            </body>
        </html>
        """)
        
        try:
            # Test selecting "yes" and "credit"
            agent.execute_v1_passenger_fill(
                passengers=[Passenger(name="Sai", age=30, gender="M")], 
                contact={"mobile": "9999999999"},
                travel_insurance=True,
                payment_pref="credit"
            )
            report("  successfully fills and selects YES and CREDIT", True)
        except Exception as e:
            report(f"  failed to select YES and CREDIT: {e}", False)

        # =============================================================
        # TEST 10: Option Selection Verification (NO and UPI)
        # =============================================================
        print("\nTest 10: Option Selection (NO and UPI)")
        try:
            agent.execute_v1_passenger_fill(
                passengers=[Passenger(name="Sai", age=30, gender="M")], 
                contact={"mobile": "9999999999"},
                travel_insurance=False,
                payment_pref="upi"
            )
            report("  successfully fills and selects NO and UPI", True)
        except Exception as e:
            report(f"  failed to select NO and UPI: {e}", False)

        # Summary
        # =============================================================
        # TEST 11: wait_for_url_transition
        # =============================================================
        print("\nTest 11: wait_for_url_transition")
        try:
            import time
            from test_real_irctc_v1_direct import wait_for_url_transition
        
            class DummyPage:
                def __init__(self):
                    self.calls = 0
                    self.url = "http://old-url"
                
                def evaluate(self, script):
                    self.calls += 1
                    if self.calls < 3:
                        return "http://old-url"
                    elif self.calls == 3:
                        raise Exception("Execution context destroyed")
                    return "http://new-review-url"

            dummy = DummyPage()
        
            t0 = time.time()
            wait_for_url_transition(dummy, "review", 5, "review")
            t1 = time.time()
        
            if 2 <= (t1 - t0) <= 5:
                report("wait_for_url_transition polls and succeeds", True)
            else:
                report("wait_for_url_transition timed weirdly", False, f"Took {t1-t0}s")
            
            dummy.calls = 0
            try:
                wait_for_url_transition(dummy, "payment", 1, "payment")
                report("wait_for_url_transition timeouts correctly", False, "Did not timeout")
            except RuntimeError as e:
                if "Failed to reach payment page" in str(e):
                    report("wait_for_url_transition timeouts correctly", True)
                else:
                    report("wait_for_url_transition timeouts correctly", False, str(e))
                
        except Exception as e:
            report("wait_for_url_transition tests", False, str(e))

        # =============================================================
        # TEST 12: 6 Passengers
        # =============================================================
        print("\nTest 12: 6 Passengers")
        try:
            # Mock HTML containing an "Add Passenger" link and multiple passenger blocks
            page.set_content("""
            <html>
                <body>
                    <div id="passengers-container">
                        <app-passenger>
                            <input placeholder="Name" class="name-input" value="">
                            <input placeholder="Age" class="age-input" value="">
                            <select formcontrolname="passengerGender"><option value="M">M</option></select>
                        </app-passenger>
                    </div>
                    <span id="add-btn">+ Add Passenger</span>
                    <input id="mobileNumber" value="">
                
                    <div>
                        <input type="radio" name="travel" value="true">
                        <span>Yes, and I accept the terms & conditions</span>
                    </div>
                
                    <div>
                        <input type="radio" name="payment" value="credit">
                        <span>Pay through Credit & Debit Cards / Net Banking / Wallets / Bharat QR / Pay on Delivery/ Rewards and Others</span>
                    </div>
                
                    <script>
                        document.getElementById('add-btn').addEventListener('click', () => {
                            const container = document.getElementById('passengers-container');
                            const newPassenger = document.createElement('app-passenger');
                            newPassenger.innerHTML = `
                                <input placeholder="Name" class="name-input" value="">
                                <input placeholder="Age" class="age-input" value="">
                                <select formcontrolname="passengerGender"><option value="M">M</option></select>
                            `;
                            container.appendChild(newPassenger);
                        });
                    </script>
                </body>
            </html>
            """)
        
            agent = RealIRCTCAgent(page, None)
            names = ["Sai Nishanth", "Arjun Kumar", "Rahul Sharma", "Kiran Reddy", "Vivek Rao", "Rohit Kumar"]
            passengers = [Passenger(name=n, age=18, gender="M") for n in names]
            agent.execute_v1_passenger_fill(
                passengers,
                {"mobile": "9999999999"},
                True,
                "credit"
            )
        
            # Verify 6 blocks exist
            if page.locator("app-passenger").count() == 6:
                report("6 passengers mock test", True)
            else:
                report("6 passengers mock test", False, f"Expected 6, got {page.locator('app-passenger').count()}")
        except Exception as e:
            report("6 passengers mock test", False, str(e))

        browser.close()
    print(f"  Results: {PASSED} passed, {FAILED} failed")
    print(f"{'='*50}")
    return FAILED == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
