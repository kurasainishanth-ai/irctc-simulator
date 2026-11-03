import logging
import argparse
from browser import BrowserManager
from irctc_agent import IRCTCAgent
from config import AgentConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def test_phase5a(cdp_url: str, target_url: str):
    logger.info("=== Phase 5A: Scan and Target Tab ===")
    
    # 1. Scan available tabs
    logger.info(f"Scanning for open tabs on {cdp_url}...")
    tabs = BrowserManager.list_tabs(cdp_url)
    
    if not tabs:
        logger.error(f"No tabs found or could not connect to {cdp_url}. Ensure Chrome is running with --remote-debugging-port=9222")
        return
        
    logger.info(f"Found {len(tabs)} open tabs:")
    for i, tab in enumerate(tabs):
        logger.info(f"  [{i+1}] {tab['title']} ({tab['url']})")
        
    # 2. Check if target exists in list
    target_found = any(target_url in tab['url'] for tab in tabs)
    if not target_found:
        logger.warning(f"Target URL '{target_url}' not found in the list of open tabs.")
        logger.info("You must open this URL in Chrome first before attaching.")
        return
        
    # 3. Connect to target tab
    logger.info(f"Connecting Playwright to target tab matching: {target_url}")
    manager = BrowserManager(cdp_url=cdp_url)
    
    try:
        page = manager.connect_to_tab(target_url)
        
        # 4. Verify and read state
        current_url = page.url
        current_title = page.title()
        
        logger.info(f"✅ Successfully attached to tab!")
        logger.info(f"Current URL: {current_url}")
        logger.info(f"Current Title: {current_title}")
        
        # Verify it's actually the IRCTC or Simulator site (basic check)
        if "irctc.co.in" in current_url or "127.0.0.1:5001" in current_url:
            logger.info("✅ Verified target tab is an IRCTC environment.")
        else:
            logger.warning("⚠️ Target tab does not appear to be IRCTC (or simulator).")
            
        logger.info("Phase 5A complete. Not modifying page state.")
        
    except Exception as e:
        logger.error(f"❌ Failed to connect to tab: {e}")
    finally:
        manager.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test connecting to a live browser tab.")
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222", help="CDP URL (default: http://127.0.0.1:9222)")
    parser.add_argument("--target", default="127.0.0.1:5001", help="Target URL substring to attach to")
    args = parser.parse_args()
    
    test_phase5a(args.cdp_url, args.target)
