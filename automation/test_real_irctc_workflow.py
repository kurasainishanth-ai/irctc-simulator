import logging
import argparse
import time
from browser import BrowserManager
from real_irctc_agent import RealIRCTCAgent, PageState
from decision_engine import DecisionEngine
from config import AgentConfig, SearchConfig, BookingPreferences, Passenger

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def check_for_human_intervention(agent: RealIRCTCAgent):
    """Checks the page state. If it requires human interaction (e.g., CAPTCHA), wait."""
    report = agent.inspect_current_page()
    if report["state"] == PageState.CAPTCHA:
        agent.wait_for_user_action("CAPTCHA detected. Please solve it manually.")
    return report

def run_real_workflow(cdp_url: str, target_url: str, preferred_trains: list, preferred_classes: list):
    logger.info("=== Start Real IRCTC Automation Workflow ===")
    
    manager = BrowserManager(cdp_url=cdp_url)
    
    try:
        # 1. SCAN TABS & START
        logger.info(f"Scanning open tabs for: {target_url}")
        tabs = BrowserManager.list_tabs(cdp_url)
        target_found = any(target_url in tab['url'] for tab in tabs)
        
        if not target_found:
            logger.error(f"Could not find a tab matching '{target_url}'. Please open IRCTC in Chrome first.")
            return
            
        page = manager.connect_to_tab(target_url)
        agent = RealIRCTCAgent(page, AgentConfig(base_url="https://www.irctc.co.in"))
        
        # 2. LOGIN (or verify logged in state)
        report = check_for_human_intervention(agent)
        if report["state"] == PageState.LOGIN:
            logger.info("Automation currently does not handle live credentials automatically for security reasons.")
            agent.wait_for_user_action("Login required. Please login manually and reach the search page.")
            report = check_for_human_intervention(agent)
            
        # 3. JOURNEY SEARCH
        if report["state"] == PageState.SEARCH:
            search_config = SearchConfig(
                source="SECUNDERABAD JN - SC",
                destination="NEW DELHI - NDLS",
                journey_date="15/10/2026", # Real IRCTC format DD/MM/YYYY typically
                class_pref="All Classes"
            )
            agent.search_journey(search_config)
            
        # 4. READ TRAIN RESULTS & DECISION ENGINE
        report = check_for_human_intervention(agent)
        if report["state"] == PageState.RESULTS:
            # First, fetch trains without prefs to see what's on the page if we need fallback
            # We'll use a fast read-only mode in get_train_results if prefs is None
            fast_results = agent.get_train_results()
            if not fast_results:
                logger.error("No trains extracted from the page. DOM might have changed.")
                return
                
            # If no preferred trains were provided in CLI, fallback to the ones found on page
            if not preferred_trains:
                preferred_trains = [t["train_number"] for t in fast_results]
                logger.info(f"No preferred trains provided. Using dynamically extracted trains: {preferred_trains}")
                
            booking_prefs = BookingPreferences(
                preferred_trains=preferred_trains,
                preferred_classes=preferred_classes,
                passengers=[Passenger(name="Test User", age=30, gender="M")],
                allow_waitlist=False
            )
            
            # Now run the lazy extraction passing the preferences
            results = agent.get_train_results(prefs=booking_prefs)
            
            # Log the extracted results for visibility
            import json
            def _clean(obj):
                if isinstance(obj, list): return [_clean(i) for i in obj]
                if isinstance(obj, dict): return {k: _clean(v) for k,v in obj.items() if k != 'card_element'}
                return obj
            logger.info("Extracted Results Structure:\n" + json.dumps(_clean(results), indent=2))
            
            engine = DecisionEngine(booking_prefs)
            selection = engine.select_best_option(results)
            
            if not selection:
                logger.error("No suitable train/class found based on preferences.")
                return
                
            train_num, cls_name = selection
            
            # For this test, do NOT click Book Now yet as requested in Phase 5B parsing step
            # Just print the selection
            logger.info(f"Test selection complete: Would book Train {train_num}, Class {cls_name}")
            return
            
            # Below code is skipped for this run based on user instructions
            # 5. TRAIN + CLASS SELECTION
            # agent.select_train_and_class(train_num, cls_name)
            
        # 6. PASSENGER DETAILS & CONTACT DETAILS
        report = check_for_human_intervention(agent)
        if report["state"] == PageState.PASSENGER_DETAILS:
            agent.fill_passenger_details(booking_prefs.passengers, {"mobile": "9876543210"})
            agent.wait_for_user_action("Passenger details filled. Please verify and submit the form manually.")
            
        # 7. REVIEW
        report = check_for_human_intervention(agent)
        if report["state"] == PageState.REVIEW:
            # Let the user review, or attempt to click continue
            agent.proceed_to_payment()
            
        # 8. PAYMENT (STOP POINT)
        report = check_for_human_intervention(agent)
        if report["state"] == PageState.PAYMENT:
            logger.info("🛑 Reached final payment page. Automation stopped. User action required.")
            return

        logger.info("Workflow execution reached the end of its programmed sequence.")

    except Exception as e:
        logger.error(f"❌ Real IRCTC Automation Failed: {e}")
    finally:
        manager.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222")
    parser.add_argument("--target", default="irctc.co.in")
    parser.add_argument("--trains", nargs="*", default=[], help="List of preferred train numbers")
    parser.add_argument("--classes", nargs="*", default=["SL", "3A", "2A"], help="List of preferred classes")
    args = parser.parse_args()
    
    run_real_workflow(args.cdp_url, args.target, args.trains, args.classes)
