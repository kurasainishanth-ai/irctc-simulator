import logging
from browser import BrowserManager
from config import AgentConfig, SearchConfig
from irctc_agent import IRCTCAgent

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def test_search_and_validate_results():
    logger.info("Starting Phase 2: First Automation Flow")
    
    # 1. Initialize Browser
    browser_manager = BrowserManager(headless=False, slow_mo=500)
    page = browser_manager.start()
    
    try:
        # 2. Setup Configs
        agent_config = AgentConfig(base_url="http://127.0.0.1:5001")
        search_config = SearchConfig(
            source="HYDERABAD",
            destination="NEW DELHI",
            journey_date="2026-10-15",
            class_pref="All Classes"
        )
        
        agent = IRCTCAgent(page, agent_config)
        
        # 3. Execute Flow
        agent.login(username="testuser", password="password")
        agent.search_journey(search_config)
        
        # 4. Read Results
        results = agent.get_train_results()
        
        # 5. Validation Assertions
        assert len(results) > 0, "No trains found in results!"
        
        train_numbers = [t["train_number"] for t in results]
        logger.info(f"Trains found: {train_numbers}")
        
        assert "12723" in train_numbers, "Telangana Exp (12723) is missing from results!"
        assert "12615" in train_numbers, "GT Express (12615) is missing from results!"
        
        logger.info("✅ All validations passed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Automation failed: {str(e)}")
        raise e
    finally:
        browser_manager.stop()
        logger.info("Browser closed.")

if __name__ == "__main__":
    test_search_and_validate_results()
