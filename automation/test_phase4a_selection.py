import logging
from browser import BrowserManager
from config import AgentConfig, SearchConfig, BookingPreferences, Passenger
from irctc_agent import IRCTCAgent
from decision_engine import DecisionEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def run_selection_test(test_name: str, preferred_trains: list, preferred_classes: list, 
                       expected_train: str, expected_class: str, allow_waitlist: bool = False):
    """Reusable helper: search → decide → select → verify passenger page."""
    logger.info(f"=== {test_name} ===")
    
    browser_manager = BrowserManager(headless=True, slow_mo=0)
    page = browser_manager.start()
    
    try:
        agent_config = AgentConfig(base_url="http://127.0.0.1:5001")
        search_config = SearchConfig(
            source="HYDERABAD",
            destination="NEW DELHI",
            journey_date="2026-10-15",
            class_pref="All Classes"
        )
        booking_prefs = BookingPreferences(
            preferred_trains=preferred_trains,
            preferred_classes=preferred_classes,
            passengers=[Passenger(name="Test User", age=30, gender="M")],
            allow_waitlist=allow_waitlist
        )
        
        agent = IRCTCAgent(page, agent_config)
        engine = DecisionEngine(booking_prefs)
        
        # Login → Search → Read Results
        agent.login(username="testuser", password="password")
        agent.search_journey(search_config)
        results = agent.get_train_results()
        
        # Decision Engine
        selection = engine.select_best_option(results)
        assert selection is not None, "Decision Engine returned None — no suitable option!"
        
        train_num, cls_name = selection
        assert train_num == expected_train, f"Expected train {expected_train}, got {train_num}"
        assert cls_name == expected_class, f"Expected class {expected_class}, got {cls_name}"
        logger.info(f"Decision: Train {train_num}, Class {cls_name}")
        
        # Phase 4A: Execute selection on the page
        agent.select_train_and_class(train_num, cls_name)
        
        logger.info(f"✅ {test_name} PASSED\n")
        
    except Exception as e:
        logger.error(f"❌ {test_name} FAILED: {e}\n")
        raise
    finally:
        browser_manager.stop()


def test_happy_path():
    """Preferred train 12723, preferred class SL — both available."""
    run_selection_test(
        test_name="Happy Path: 12723 SL",
        preferred_trains=["12723", "12615"],
        preferred_classes=["SL", "3A", "2A", "1A"],
        expected_train="12723",
        expected_class="SL"
    )

def test_class_fallback():
    """SL is preferred but we pretend 1A is first preference (unavailable on 12723).
    Decision Engine should fall back to 2A (waitlist) only if allowed, else skip to 3A."""
    # 1A is unavailable, 2A is waitlist (not allowed), so should pick 3A
    run_selection_test(
        test_name="Class Fallback: 12723 skip 1A+2A → 3A",
        preferred_trains=["12723"],
        preferred_classes=["1A", "2A", "3A", "SL"],
        expected_train="12723",
        expected_class="3A",
        allow_waitlist=False
    )

def test_waitlist_accepted():
    """2A on 12723 is WL 12. If waitlist is allowed and 2A is top preference, select it."""
    run_selection_test(
        test_name="Waitlist Accepted: 12723 2A (WL)",
        preferred_trains=["12723"],
        preferred_classes=["2A", "3A", "SL"],
        expected_train="12723",
        expected_class="2A",
        allow_waitlist=True
    )


if __name__ == "__main__":
    test_happy_path()
    test_class_fallback()
    test_waitlist_accepted()
    logger.info("🎉 All Phase 4A tests passed!")
