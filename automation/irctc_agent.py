import logging
from typing import List, Dict, Any
from enum import Enum
from playwright.sync_api import Page, expect
from config import SearchConfig, AgentConfig

logger = logging.getLogger(__name__)

class PageState(Enum):
    LOGIN = "login"
    SEARCH = "search"
    RESULTS = "results"
    PASSENGER_DETAILS = "passenger_details"
    REVIEW = "review"
    PAYMENT = "payment"
    CAPTCHA = "captcha"
    UNKNOWN = "unknown"

class IRCTCAgent:
    def __init__(self, page: Page, config: AgentConfig):
        self.page = page
        self.config = config

    def inspect_current_page(self) -> Dict[str, Any]:
        """
        Inspect the live page to determine its state (search, results, passenger, etc.)
        and locate relevant elements without modifying the page state.
        """
        current_url = self.page.url
        title = self.page.title()
        
        state = PageState.UNKNOWN
        relevant_elements = []
        
        # Check for CAPTCHA first, as it could be an overlay or embedded
        has_captcha = self.page.locator("img[src*='captcha'], input[id*='captcha'], input[name*='captcha'], .captcha").count() > 0
        if has_captcha:
            state = PageState.CAPTCHA
            relevant_elements.append("captcha_image")
            relevant_elements.append("captcha_input")
            
        # If no CAPTCHA or it's just a small part, check main states
        # The URL structure and visible elements define the state
        if state != PageState.CAPTCHA:
            if "login" in current_url.lower() or self.page.locator("app-login").is_visible():
                state = PageState.LOGIN
                relevant_elements.extend(["username_input", "password_input", "login_button"])
                
            elif "train-list" in current_url.lower():
                state = PageState.RESULTS
                relevant_elements.extend(["train_cards", "class_buttons", "book_now_buttons"])
                
            elif "psgninput" in current_url.lower() or "passenger" in current_url.lower():
                state = PageState.PASSENGER_DETAILS
                relevant_elements.extend(["passenger_name", "passenger_age", "passenger_gender", "contact_number"])
                
            elif "reviewBooking" in current_url.lower() or "review" in current_url.lower():
                state = PageState.REVIEW
                relevant_elements.extend(["fare_summary", "continue_button"])
                
            elif "payment" in current_url.lower() or "bank" in current_url.lower():
                state = PageState.PAYMENT
                relevant_elements.extend(["payment_gateways", "pay_button"])
                
            elif "search" in current_url.lower() or self.page.locator("p-autocomplete[id='origin']").is_visible() or self.page.locator("p-autocomplete[id='destination']").is_visible():
                state = PageState.SEARCH
                relevant_elements.extend(["origin_input", "destination_input", "date_input", "search_button"])

        report = {
            "url": current_url,
            "title": title,
            "state": state,
            "relevant_elements": relevant_elements
        }
        
        logger.info(f"--- Page Inspection Report ---")
        logger.info(f"URL: {current_url}")
        logger.info(f"Title: {title}")
        logger.info(f"Detected State: {state.value.upper()}")
        logger.info(f"Relevant Elements: {', '.join(relevant_elements) if relevant_elements else 'None'}")
        
        return report

    def login(self, username: str, password: str):
        logger.info(f"Navigating to {self.config.base_url}/login")
        self.page.goto(f"{self.config.base_url}/login")
        
        logger.info(f"Logging in with username: {username}")
        self.page.locator("id=username").fill(username)
        self.page.locator("id=password").fill(password)
        self.page.locator("button#loginBtn").click()
        
        # Verify login success: search page has the "PLAN MY JOURNEY" card header
        expect(self.page.locator(".card-header")).to_contain_text("PLAN MY JOURNEY")
        logger.info("Login successful.")

    def search_journey(self, search_config: SearchConfig):
        logger.info(f"Searching trains from {search_config.source} to {search_config.destination} on {search_config.journey_date}")
        
        self.page.locator("id=from_station").fill(search_config.source)
        self.page.locator("id=to_station").fill(search_config.destination)
        self.page.locator("id=date").fill(search_config.journey_date)
        self.page.locator("id=class_pref").select_option(label=search_config.class_pref)
        
        self.page.locator("button#searchBtn").click()
        
        # Verify results page loaded: card header contains "TRAIN LIST"
        expect(self.page.locator(".card-header")).to_contain_text("TRAIN LIST")
        logger.info("Search successful. Reached results page.")

    def get_train_results(self) -> List[Dict[str, Any]]:
        logger.info("Extracting train results from the DOM.")
        
        self.page.wait_for_selector(".train-card", state="attached", timeout=5000)
        
        train_cards = self.page.locator(".train-card").all()
        results = []
        
        for card in train_cards:
            # Read data-train-number from the card itself
            train_number = card.get_attribute("data-train-number")
            
            # Read train identity from the header span.train-id
            header_text = card.locator(".train-id").inner_text()
            # header_text is e.g. "TELANGANA EXP (12723)"
            train_name = header_text.split("(")[0].strip()
            
            # Read schedule
            stations = card.locator(".train-schedule .station").all()
            departure_time = stations[0].locator(".time").inner_text() if len(stations) > 0 else ""
            arrival_time = stations[1].locator(".time").inner_text() if len(stations) > 1 else ""
            duration = card.locator(".train-schedule .duration").inner_text().strip()
            
            # Read class availability
            classes_info = []
            class_boxes = card.locator(".class-box").all()
            for box in class_boxes:
                cls_name = box.locator(".cls-name").inner_text().strip()
                availability = box.locator(".cls-avail").inner_text().strip()
                fare = box.locator(".cls-fare").inner_text().replace("₹", "").strip()
                
                status = "available"
                if "NOT AVAILABLE" in availability:
                    status = "unavailable"
                elif "WL" in availability:
                    status = "waitlist"
                    
                classes_info.append({
                    "class": cls_name,
                    "availability": availability,
                    "fare": fare,
                    "status": status
                })
            
            results.append({
                "train_name": train_name,
                "train_number": train_number,
                "departure": departure_time,
                "arrival": arrival_time,
                "duration": duration,
                "classes": classes_info
            })
            
        logger.info(f"Extracted {len(results)} trains.")
        return results

    def select_train_and_class(self, train_number: str, class_name: str):
        """
        On the results page, select the given class for the given train and click Book Now.
        Uses stable data attributes and element IDs from the simulator DOM.
        """
        logger.info(f"Selecting Train {train_number}, Class {class_name}")

        # Locate the specific train card by its data attribute
        train_card = self.page.locator(f'.train-card[data-train-number="{train_number}"]')
        expect(train_card).to_be_visible(timeout=5000)

        # Click the class radio button within that train card
        class_radio = train_card.locator(f'#cls_{train_number}_{class_name}')
        class_radio.click()
        logger.info(f"Clicked class radio: cls_{train_number}_{class_name}")

        # Click the Book Now button for this train
        book_btn = train_card.locator(f'#bookBtn_{train_number}')
        book_btn.click()
        logger.info(f"Clicked Book Now for train {train_number}")

        # Verify we reached the passenger details page
        expect(self.page.locator(".card-header").first).to_contain_text("JOURNEY DETAILS")
        logger.info("Successfully reached Passenger Details page.")
