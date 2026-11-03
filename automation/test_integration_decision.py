import logging
from browser import BrowserManager
from config import AgentConfig, SearchConfig, BookingPreferences, Passenger
from irctc_agent import IRCTCAgent
from decision_engine import DecisionEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def test_integration_decision():
    logger.info("Starting Phase 3: Integration Test for Decision Engine")
    
    browser_manager = BrowserManager(headless=False, slow_mo=500)
    page = browser_manager.start()
    
    try:
        agent_config = AgentConfig(base_url="http://127.0.0.1:5001")
        search_config = SearchConfig(
            source="HYDERABAD",
            destination="NEW DELHI",
            journey_date="2026-10-15",
            class_pref="All Classes"
        )
        
        # User explicitly wants Telangana Exp, preferring SL > 3A > 2A > 1A
        # They do not want waitlist.
        booking_prefs = BookingPreferences(
            preferred_trains=["12723", "12615"],
            preferred_classes=["SL", "3A", "2A", "1A"],
            passengers=[Passenger(name="Test User", age=30, gender="M")],
            allow_waitlist=False
        )
        
        agent = IRCTCAgent(page, agent_config)
        decision_engine = DecisionEngine(booking_prefs)
        
        # Execute Flow
        agent.login(username="testuser", password="password")
        agent.search_journey(search_config)
        
        # Read Results
        results = agent.get_train_results()
        assert len(results) > 0, "No trains found in results!"
        
        # Run Decision Engine
        selection = decision_engine.select_best_option(results)
        
        if selection:
            train_num, cls_name = selection
            logger.info(f"✅ Decision Engine Selected -> Train: {train_num}, Class: {cls_name}")
            
            # Since we know the simulator's mock data for 12723 has SL as AVAILABLE,
            # it should pick 12723 / SL.
            assert train_num == "12723", f"Expected train 12723, got {train_num}"
            assert cls_name == "SL", f"Expected class SL, got {cls_name}"
        else:
            logger.info("❌ Decision Engine found NO SUITABLE OPTION.")
            assert False, "Expected a valid option based on simulator data!"
            
    except Exception as e:
        logger.error(f"❌ Integration test failed: {str(e)}")
        raise e
    finally:
        browser_manager.stop()
        logger.info("Browser closed.")

if __name__ == "__main__":
    test_integration_decision()
