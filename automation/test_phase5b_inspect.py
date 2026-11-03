import logging
import argparse
from browser import BrowserManager
from irctc_agent import IRCTCAgent
from config import AgentConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def test_phase5b(cdp_url: str, target_url: str):
    logger.info("=== Phase 5B: Page State Inspection ===")
    
    manager = BrowserManager(cdp_url=cdp_url)
    
    try:
        page = manager.connect_to_tab(target_url)
        
        agent_config = AgentConfig(base_url="http://127.0.0.1:5001")
        agent = IRCTCAgent(page, agent_config)
        
        # Phase 5B: Inspect the page state without modifying anything
        report = agent.inspect_current_page()
        
        if report["state"].value != "unknown":
            logger.info("✅ Successfully recognized page state.")
        else:
            logger.warning("⚠️ Page state is UNKNOWN. (Check if URL matches expected patterns)")
            
    except Exception as e:
        logger.error(f"❌ Failed Phase 5B: {e}")
    finally:
        manager.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test connecting to a live browser tab and inspecting state.")
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222", help="CDP URL")
    parser.add_argument("--target", default="127.0.0.1:5001", help="Target URL substring")
    args = parser.parse_args()
    
    test_phase5b(args.cdp_url, args.target)
