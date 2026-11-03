"""V1 Phase 1 & 2: RESULTS → Passenger Details → Review → Payment.

Hard failures on any transition that does not complete.
Stops immediately after reaching Payment.
"""
import logging
import argparse
import time
import json
import re
from browser import BrowserManager
from real_irctc_agent import RealIRCTCAgent, PageState
from config import AgentConfig, Passenger

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def wait_for_url_transition(page, pattern, timeout, name, agent=None):
    t_wait_start = time.time()
    reached = False
    last_log_url = ""
    while time.time() - t_wait_start < timeout:
        try:
            current_url = page.evaluate("window.location.href")
        except Exception:
            current_url = page.url
            
        if current_url != last_log_url:
            logger.info(f"Waiting for {name}... Current URL: {current_url}")
            last_log_url = current_url
            
        if re.search(pattern, current_url, re.IGNORECASE):
            reached = True
            break

        # Check for visible IRCTC errors during wait (e.g. "Unable to Process Request!!", session expired)
        if agent is not None:
            err_msg = agent.check_for_irctc_error()
            if err_msg:
                agent.diagnose_transition_failure(name)
                raise RuntimeError(f"IRCTC error during transition to {name}: {err_msg}")

        time.sleep(1.0)
        
    if not reached:
        if agent is not None:
            agent.diagnose_transition_failure(name)
        raise RuntimeError(f"Failed to reach {name} page within {timeout}s.")


def run_v1_to_payment(cdp_url: str, target_url: str, config_path: str):
    logger.info("=== V1 Phase 1 & 2: RESULTS → PAYMENT ===")
    t_start = time.time()

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    if "travel_insurance" not in cfg or not isinstance(cfg["travel_insurance"], bool):
        raise ValueError("Config must contain explicitly boolean 'travel_insurance'")
        
    if "payment_preference" not in cfg or cfg["payment_preference"] not in ["credit", "upi"]:
        raise ValueError("Config must contain 'payment_preference' as either 'credit' or 'upi'")

    train = cfg["train"]
    cls = cfg["class"]
    passengers = [Passenger(**p) for p in cfg["passengers"]]
    contact_info = cfg["contact"]
    travel_insurance = cfg["travel_insurance"]
    payment_pref = cfg["payment_preference"]
    
    logger.info(f"Config: train={train}, class={cls}, insurance={travel_insurance}, payment={payment_pref}")

    manager = BrowserManager(cdp_url=cdp_url)

    try:
        page = manager.connect_to_tab(target_url)
        agent = RealIRCTCAgent(page, AgentConfig("https://www.irctc.co.in"))

        report = agent.inspect_current_page()
        state = report["state"]

        if state == PageState.LOGIN:
            raise RuntimeError("Session not logged in.")

        timings = {}
        t_passenger = None

        if state == PageState.RESULTS:
            # Execute Phase 1
            sel_timings = agent.execute_v1_selection(train, cls)
            timings.update(sel_timings)
            
            try:
                # Wait for passenger URL regex OR the passenger component in the DOM
                page.wait_for_function(
                    "() => /psgninput/i.test(window.location.href) || !!document.querySelector('app-passenger')", 
                    timeout=10000
                )
            except Exception:
                agent.diagnose_book_now_failure(train)
                raise RuntimeError("Failed to reach passenger page.")
            t_passenger = time.time()
            # Re-inspect to ensure we are now on Passenger Details
            state = agent.inspect_current_page()["state"]
        else:
            t_passenger = t_start
            state = report["state"]

        if state != PageState.PASSENGER_DETAILS:
            raise RuntimeError(f"Expected PASSENGER_DETAILS, got {state}")

        # Phase 2: Passenger Filling
        fill_timings = agent.execute_v1_passenger_fill(
            passengers, contact_info, travel_insurance, payment_pref
        )
        timings.update(fill_timings)
        
        # Proceed to Review
        rev_timings = agent.execute_v1_proceed_to_review()
        timings.update(rev_timings)
        
        # Robust Review detection with hard 90s timeout and error detection
        wait_for_url_transition(page, r"review", 90, "review", agent=agent)
            
        t_review = time.time()
        report = agent.inspect_current_page()
        if report["state"] != PageState.REVIEW:
            raise RuntimeError(f"Expected REVIEW, got {report['state']}")

        # Validate Review (Check for Captcha/Errors)
        if not agent.validate_review():
             raise RuntimeError("Review validation failed (Captcha or error detected).")

        # Proceed to Payment
        pay_timings = agent.execute_v1_proceed_to_payment()
        timings.update(pay_timings)
        
        # Robust Payment detection with hard 90s timeout and error detection
        wait_for_url_transition(page, r"payment|bankp", 90, "payment", agent=agent)
            
        t_payment = time.time()
        report = agent.inspect_current_page()
        if report["state"] != PageState.PAYMENT:
            raise RuntimeError(f"Expected PAYMENT, got {report['state']}")

        # Report
        logger.info("")
        logger.info("==========================================")
        logger.info("  V1 TIMING: RESULTS → PAYMENT            ")
        logger.info("==========================================")
        logger.info(f"START → Passenger Page        : {t_passenger - t_start:.3f}s")
        logger.info(f"Fill Passenger Data           : {timings['t_filled'] - timings['t_start_fill']:.3f}s")
        logger.info(f"Passenger Form → Review Page  : {t_review - timings['t_filled']:.3f}s")
        logger.info(f"Review Page → Payment Page    : {t_payment - t_review:.3f}s")
        logger.info("──────────────────────────────────────────")
        logger.info(f"TOTAL START → PAYMENT         : {t_payment - t_start:.3f}s")
        logger.info("==========================================")
        logger.info("✅ Successfully reached Payment Page")
        logger.info(f"Final URL: {page.url}")
        logger.info(f"Filled fields: {', '.join(timings['filled_fields'])}")
        logger.info("Stopping. Payment automation is not enabled.")

    except RuntimeError as e:
        logger.error(f"[STAGE FAILURE] {e}")
        raise
    except Exception as e:
        logger.error(f"[UNEXPECTED ERROR] {e}", exc_info=True)
        raise
    finally:
        # Disconnect the Playwright client WITHOUT closing the user's Chrome tabs.
        # The IRCTC tab must remain open so subsequent runs can reconnect.
        manager.disconnect()
        logger.info("Playwright client disconnected. Chrome tabs preserved.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222")
    parser.add_argument("--target", default="irctc.co.in")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    run_v1_to_payment(args.cdp_url, args.target, args.config)
