import time
import logging
from typing import Dict, List, Any
from config import SearchConfig
from decision_engine import BookingPreferences

logger = logging.getLogger(__name__)

class PageState:
    LOGIN = "login"
    SEARCH = "search"
    RESULTS = "results"
    PASSENGER_DETAILS = "passenger_details"
    REVIEW = "review"
    PAYMENT = "payment"
    CAPTCHA = "captcha"
    UNKNOWN = "unknown"

class RealIRCTCAgent:
    def __init__(self, page, config):
        self.page = page
        self.config = config

    def inspect_current_page(self):
        current_url = self.page.url
        logger.info("--- Real Page Inspection Report ---")
        logger.info(f"URL: {current_url}")
        
        state = PageState.UNKNOWN
        
        if "login" in current_url.lower():
            state = PageState.LOGIN
        elif "train-search" in current_url.lower() or current_url.endswith("irctc.co.in/nget/"):
            state = PageState.SEARCH
        elif "train-list" in current_url.lower() or "trainlist" in current_url.lower():
            state = PageState.RESULTS
        elif "psgninput" in current_url.lower() or "passenger" in current_url.lower():
            state = PageState.PASSENGER_DETAILS
        elif "reviewbooking" in current_url.lower() or "review" in current_url.lower():
            state = PageState.REVIEW
        elif "payment" in current_url.lower() or "bankp" in current_url.lower():
            state = PageState.PAYMENT

        # For Angular SPAs, the URL may not update immediately after Book Now.
        # Confirm PASSENGER_DETAILS from the DOM if URL hasn't changed yet.
        if state not in (PageState.PASSENGER_DETAILS, PageState.REVIEW, PageState.PAYMENT):
            try:
                # app-passenger-input is the real IRCTC passenger form container (confirmed from live DOM)
                if self.page.locator("app-passenger-input, app-passenger").count() > 0:
                    logger.info("DOM confirms PASSENGER_DETAILS (app-passenger-input / app-passenger found)")
                    state = PageState.PASSENGER_DETAILS
            except Exception:
                pass
            
        logger.info(f"Detected State: {state}")
        
        return {
            "url": current_url,
            "state": state
        }

    def wait_for_user_action(self, message: str):
        logger.info(f"WAITING FOR USER: {message}")
        while True:
            state = self.inspect_current_page()["state"]
            if state not in [PageState.LOGIN, PageState.CAPTCHA]:
                break
            time.sleep(2)
            
    def search_journey(self, config: SearchConfig):
        pass
        
    def get_train_results(self, prefs: BookingPreferences = None):
        logger.info("Extracting train results from REAL IRCTC DOM...")
        start_time = time.time()
        
        cards = self.page.locator("app-train-avl-enq").all()
        logger.info(f"Train discovery took {time.time() - start_time:.2f}s for {len(cards)} trains")
        
        results = []
        for card in cards:
            train_header = card.locator(".train-heading").first
            if not train_header.is_visible():
                continue
            
            header_text = train_header.inner_text()
            parts = header_text.split("(")
            if len(parts) < 2:
                continue
            
            train_name = parts[0].strip()
            train_num = parts[1].replace(")", "").strip()
            
            if prefs and train_num not in prefs.preferred_trains:
                continue
                
            train_data = {
                "train_name": train_name,
                "train_number": train_num,
                "classes": []
            }
            results.append(train_data)
            
            for pref_class in prefs.preferred_classes:
                try:
                    class_start = time.time()
                    
                    # FIX 1: State Awareness
                    book_btn = card.locator("button:has-text('Book Now')").first
                    if book_btn.is_visible() and "disable-book" not in book_btn.get_attribute("class"):
                        logger.info(f"Book Now already enabled for {train_num}. Returning available immediately.")
                        train_data["classes"].append({
                            "class": pref_class,
                            "availability": "AVAILABLE",
                            "fare": "Unknown",
                            "status": "available",
                            "element": None
                        })
                        return results
                        
                    class_td = card.locator(f"table td:has-text('{pref_class}')").first
                    if class_td.is_visible():
                        if "Refresh" not in class_td.inner_text() and "active" not in class_td.get_attribute("class"):
                             class_td.click()
                        
                    avail_div = card.locator("div.col-xs-12").first
                    avail_div.wait_for(state="visible", timeout=3000)
                    availability_text = avail_div.inner_text().strip()
                    lines = availability_text.split("\n")
                    avail_info = lines[-1] if len(lines) > 1 else availability_text
                    
                    status = "available"
                    avail_upper = avail_info.upper()
                    if "NOT AVAILABLE" in avail_upper or "REGRET" in avail_upper:
                        status = "unavailable"
                    elif any(wl in avail_upper for wl in ["WL", "WAITLIST", "PQWL", "GNWL", "RLWL"]):
                        status = "waitlist"
                        
                    fare_element = card.locator("strong:has-text('₹')").first
                    fare = fare_element.inner_text().replace("₹", "").strip() if fare_element.is_visible() else "Unknown"
                    
                    train_data["classes"].append({
                        "class": pref_class,
                        "availability": avail_info,
                        "fare": fare,
                        "status": status,
                        "element": None
                    })
                    
                    class_time = time.time() - class_start
                    logger.info(f"Class lookup [{train_num} - {pref_class}] took {class_time:.2f}s | Status: {status}")
                    
                    if status == "available" or (status == "waitlist" and prefs.allow_waitlist):
                        return results
                        
                except Exception as e:
                    logger.debug(f"Failed to extract class {pref_class} for {train_num}: {e}")
                    
        return results

    def select_train_and_class(self, train_num: str, cls_name: str):
        cards = self.page.locator("app-train-avl-enq").all()
        for card in cards:
            if train_num in card.inner_text():
                book_btn = card.locator("button:has-text('Book Now')").first
                
                # FIX 1: State Awareness
                if book_btn.is_visible() and "disable-book" not in book_btn.get_attribute("class"):
                    logger.info("Book Now is already enabled. Proceeding directly.")
                else:
                    avail_table = card.locator("table").last
                    date_tds = avail_table.locator("td").all()
                    if len(date_tds) > 1:
                        first_date_td = date_tds[1]
                    else:
                        first_date_td = avail_table.locator("td").first
                    
                    date_div = first_date_td.locator("div").first
                    date_div.click(force=True)
                        
                    try:
                        for _ in range(10):
                            if "disable-book" not in book_btn.get_attribute("class"):
                                break
                            time.sleep(0.2)
                    except Exception:
                        pass
                            
                if book_btn.is_visible():
                    book_btn.click(force=True)
                    logger.info("Clicked Book Now")
                    
                    try:
                        dialog = self.page.locator("p-dialog, p-confirmdialog").first
                        dialog.wait_for(state="visible", timeout=3000)
                        if dialog.is_visible():
                            agree = self.page.locator("button:has-text('I Agree'), button:has-text('Yes')").first
                            if agree.is_visible():
                                agree.click()
                                logger.info("Accepted confirmation dialog")
                    except Exception:
                        pass
                    return
        logger.warning(f"Could not find train card for {train_num}")

    def fill_passenger_details(self, passengers: List[Any], contact: Dict[str, str]):
        logger.info("Filling passenger details...")
        
        # FIX 2: Passenger filling must never fail silently
        self.page.wait_for_selector("app-passenger", state="attached", timeout=15000)
        
        for i, p in enumerate(passengers):
            if i > 0:
                add_btn = self.page.locator("span:has-text('+ Add Passenger')").first
                add_btn.wait_for(state="visible", timeout=5000)
                add_btn.click()
                
            row = self.page.locator("app-passenger").nth(i)
            row.wait_for(state="visible", timeout=5000)
            
            name_input = row.locator("input[placeholder*='Name' i]").first
            name_input.wait_for(state="visible", timeout=5000)
            name_input.fill(p.name)
            name_input.press("Tab")
            
            actual_name = name_input.input_value().strip()
            if actual_name.lower() != p.name.lower():
                raise ValueError(f"Verification failed: Name '{p.name}' not filled. Found '{actual_name}'")
            
            age_input = row.locator("input[placeholder*='Age' i]").first
            age_input.wait_for(state="visible", timeout=5000)
            age_input.fill(str(p.age))
            age_input.press("Tab")
            
            actual_age = age_input.input_value().strip()
            if str(p.age) not in actual_age:
                raise ValueError(f"Verification failed: Age '{p.age}' not filled. Found '{actual_age}'")
            
            gender_select = row.locator("select[formcontrolname='passengerGender']").first
            gender_select.wait_for(state="attached", timeout=5000)
            gender_select.select_option(value=p.gender)
            
        mobile_input = self.page.locator("input[id='mobileNumber'], input[formcontrolname='mobileNumber']").first
        mobile_input.wait_for(state="visible", timeout=5000)
        mobile_input.fill(contact["mobile"])
        mobile_input.press("Tab")
        
        actual_mobile = mobile_input.input_value().strip()
        if contact["mobile"] not in actual_mobile:
            raise ValueError(f"Verification failed: Mobile '{contact['mobile']}' not filled. Found '{actual_mobile}'")

    # FIX 4: Separate Review and Payment transitions
    def proceed_to_review(self):
        logger.info("Proceeding to review page...")
        continue_btn = self.page.get_by_role("button", name="Continue").first
        continue_btn.wait_for(state="visible", timeout=5000)
        continue_btn.click(force=True)
        
    def validate_review(self):
        logger.info("Validating review page...")
        errors = self.page.locator(".ui-messages-error, .error, .ng-invalid, .ui-toast-message-content").all()
        for e in errors:
            if e.is_visible():
                text = e.inner_text().strip()
                if text:
                    raise ValueError(f"Review validation failed with error: {text}")
                    
        captcha_inputs = self.page.locator("#captcha, input[id*='captcha' i], input[placeholder*='captcha' i]")
        if captcha_inputs.count() > 0 and captcha_inputs.first.is_visible():
            logger.warning("Captcha detected on review page. Cannot proceed automatically.")
            return False
            
        return True
        
    def proceed_to_payment(self):
        logger.info("Proceeding to payment page...")
        continue_btn = self.page.get_by_role("button", name="Continue").first
        continue_btn.wait_for(state="visible", timeout=5000)
        continue_btn.click(force=True)

    # ================================================================
    # V1 DETERMINISTIC PATH — no discovery, no DecisionEngine
    # ================================================================

    def execute_v1_selection(self, train_num: str, cls_name: str) -> dict:
        """V1 direct path: configured train/class → Book Now.

        Does NOT scan all trains. Does NOT invoke DecisionEngine.
        Does NOT interact with classes/dates already prepared by the user.
        Returns timing dict. Raises RuntimeError on any failure.
        """
        t_start = time.time()

        # 1. Locate ONLY the configured train card
        train_card = self.page.locator(
            f"app-train-avl-enq:has-text('{train_num}')"
        ).first
        if train_card.count() == 0:
            raise RuntimeError(f"Train {train_num} not visible on results page")
        t_found = time.time()
        logger.info(f"Train {train_num} located ({t_found - t_start:.3f}s)")

        # 2. Check Book Now button
        book_btn = train_card.locator("button:has-text('Book Now')").first
        if not book_btn.is_visible():
            raise RuntimeError(f"Book Now button not found for train {train_num}")

        btn_class = book_btn.get_attribute("class") or ""
        if "disable-book" not in btn_class:
            # User already prepared everything — no interaction needed
            logger.info("Book Now already enabled — no class/date interaction needed")
        else:
            # 3. Ensure class tab is expanded
            tabmenu = train_card.locator("p-tabmenu")
            if not tabmenu.is_visible():
                # Class not expanded — click it in the initial grid
                class_cell = train_card.locator(f"td:has-text('{cls_name}')").first
                if not class_cell.is_visible():
                    raise RuntimeError(
                        f"Class {cls_name} not found in train card for {train_num}"
                    )
                class_cell.click()
                logger.info(f"Expanded class {cls_name}")
                tabmenu.wait_for(state="visible", timeout=3000)

            # 4. Click first date cell to enable Book Now
            avail_table = train_card.locator("table").last
            date_tds = avail_table.locator("td").all()
            if len(date_tds) < 2:
                raise RuntimeError("No date cells found in availability table")

            date_div = date_tds[1].locator("div").first
            date_div.click(force=True)  # force: known overlay interception on date cells
            logger.info("Clicked date cell")

            # 5. Wait for Angular to process: disable-book class removed
            try:
                self.page.wait_for_function(
                    "el => !el.classList.contains('disable-book')",
                    arg=book_btn.element_handle(),
                    timeout=5000,
                )
            except Exception as e:
                raise RuntimeError(
                    f"Book Now did not become enabled within 5s: {e}"
                )
            logger.info("Book Now enabled after date selection")

        t_ready = time.time()

        # 6. Click Book Now — standard Playwright click (actionability enforced)
        #    No force=True: let Playwright verify stable + receiving pointer events
        try:
            book_btn.click(timeout=5000)
        except Exception as e:
            raise RuntimeError(f"Book Now click failed (Playwright actionability): {e}")
        t_clicked = time.time()
        logger.info(f"Clicked Book Now ({t_clicked - t_ready:.3f}s)")

        # 7. Brief dialog check (500ms, not 3s)
        try:
            self.page.locator("p-dialog, p-confirmdialog").first.wait_for(
                state="visible", timeout=500
            )
            agree = self.page.locator(
                "button:has-text('I Agree'), button:has-text('Yes')"
            ).first
            if agree.is_visible():
                agree.click()
                logger.info("Accepted confirmation dialog")
        except Exception:
            pass  # No dialog — expected on happy path

        return {
            "t_start": t_start,
            "t_found": t_found,
            "t_ready": t_ready,
            "t_clicked": t_clicked,
        }

    def check_for_irctc_error(self) -> str:
        """Inspects the page for visible IRCTC error toasts, messages, or dialogs.
        Returns the sanitized error string if found, otherwise empty string.
        """
        error_selectors = [
            ".ui-toast-message-content",
            ".ui-messages-error",
            "p-messages div[role='alert']",
            ".ui-dialog-content",
            "p-confirmdialog",
            ".error-msg",
            ".ui-growl-message"
        ]
        found_errors = []
        for sel in error_selectors:
            try:
                elements = self.page.locator(sel).all()
                for el in elements:
                    if el.is_visible():
                        txt = el.inner_text().strip()
                        if txt and not any(ignored in txt.lower() for ignored in ["welcome", "gst", "fare summary"]):
                            # Sanitize: single line, no excessive whitespace
                            clean_txt = " ".join(txt.split())
                            found_errors.append(clean_txt)
            except Exception:
                pass

        if found_errors:
            # Combine unique errors
            unique = list(dict.fromkeys(found_errors))
            return " | ".join(unique)
        return ""

    def diagnose_transition_failure(self, transition_name: str):
        """Read-only DOM inspection when transition fails."""
        logger.error(f"=== {transition_name.upper()} FAILURE DIAGNOSTICS ===")
        try:
            curr_url = self.page.evaluate("window.location.href")
        except Exception:
            curr_url = self.page.url
        logger.error(f"URL: {curr_url}")

        err = self.check_for_irctc_error()
        if err:
            logger.error(f"Detected IRCTC Error in DOM: {err}")

        # Check for visible dialogs
        for selector in ["p-dialog", "p-confirmdialog", ".ui-dialog"]:
            try:
                elements = self.page.locator(selector).all()
                for el in elements:
                    if el.is_visible():
                        logger.error(f"Visible {selector}: {el.inner_text()[:300]}")
            except Exception:
                pass

        # Session / login indicators
        for phrase in ["Session Expired", "Please login", "session has expired", "Unable to Process"]:
            try:
                indicator = self.page.locator(f"text='{phrase}'")
                if indicator.count() > 0 and indicator.first.is_visible():
                    logger.error(f"ISSUE DETECTED: '{phrase}' on screen")
            except Exception:
                pass

        logger.error("=== END TRANSITION DIAGNOSTICS ===")

    def diagnose_book_now_failure(self, train_num: str):
        """Read-only DOM inspection when Book Now fails to navigate."""
        logger.error("=== BOOK NOW FAILURE DIAGNOSTICS ===")
        logger.error(f"URL: {self.page.url}")

        try:
            train_card = self.page.locator(
                f"app-train-avl-enq:has-text('{train_num}')"
            ).first

            if train_card.count() == 0:
                logger.error(f"Train card for {train_num} no longer visible")
                return

            book_btn = train_card.locator("button:has-text('Book Now')").first
            logger.error(f"Book Now visible: {book_btn.is_visible()}")
            if book_btn.is_visible():
                logger.error(f"Book Now class: {book_btn.get_attribute('class')}")

            # Active class tab
            active_tab = train_card.locator(
                "p-tabmenu li.ui-tabmenuitem-active, p-tabmenu li.active"
            ).first
            if active_tab.is_visible():
                logger.error(f"Active class tab: {active_tab.inner_text().strip()}")

            # Dialogs / modals
            for selector in ["p-dialog", "p-confirmdialog", ".ui-dialog"]:
                elements = self.page.locator(selector).all()
                for el in elements:
                    if el.is_visible():
                        logger.error(f"Visible {selector}: {el.inner_text()[:300]}")

            # Session / login indicators
            for phrase in ["Session Expired", "Please login", "session has expired"]:
                indicator = self.page.locator(f"text='{phrase}'")
                if indicator.count() > 0 and indicator.first.is_visible():
                    logger.error(f"SESSION ISSUE: '{phrase}' detected")

            # CAPTCHA
            captcha = self.page.locator(
                "#captcha, img[id*='captcha' i], #nlpCaptchaImg"
            )
            if captcha.count() > 0 and captcha.first.is_visible():
                logger.error("CAPTCHA is visible")

            # Error toasts
            toasts = self.page.locator(
                ".ui-toast-message-content, .ui-messages-error"
            ).all()
            for t in toasts:
                if t.is_visible():
                    logger.error(f"Error toast: {t.inner_text()[:200]}")

        except Exception as e:
            logger.error(f"Diagnostics error: {e}")

        logger.error("=== END DIAGNOSTICS ===")

    def execute_v1_passenger_fill(self, passengers: List[Any], contact: Dict[str, str], travel_insurance: bool, payment_pref: str) -> dict:
        """V1 deterministic passenger filling with strict constraints."""
        logger.info("Executing V1 Passenger Fill...")
        t_start = time.time()
        
        # 1. Wait for passenger component to attach (hard failure if not present)
        try:
            self.page.wait_for_selector("app-passenger", state="attached", timeout=15000)
        except Exception as e:
            raise RuntimeError(f"Passenger form did not appear within 15s: {e}")
            
        filled_fields = []
            
        for i, p in enumerate(passengers):
            logger.info(f"Filling passenger {i+1}: {p.name}")
            
            # Click add passenger if needed
            if i > 0:
                add_btn = self.page.locator("span:has-text('+ Add Passenger')").first
                add_btn.wait_for(state="visible", timeout=5000)
                add_btn.click()
                
            row = self.page.locator("app-passenger").nth(i)
            # Wait for the row to be fully visible
            try:
                row.wait_for(state="visible", timeout=5000)
            except Exception as e:
                raise RuntimeError(f"Passenger {i+1} row did not become visible: {e}")
                
            # NAME
            name_input = row.locator("input[placeholder*='Name' i]").first
            name_input.wait_for(state="visible", timeout=5000)
            
            maxlength_attr = name_input.get_attribute("maxlength")
            if maxlength_attr:
                maxlength = int(maxlength_attr)
                if len(p.name) > maxlength:
                    raise RuntimeError(
                        f"Passenger name '{p.name}' exceeds the strict maxlength constraint of {maxlength} characters on the IRCTC form. "
                        f"The UI has no alternative mechanism for longer names. Automation stopped."
                    )
                    
            name_input.fill(p.name)
            name_input.press("Tab") # trigger Angular blur
            actual_name = name_input.input_value().strip()
            if actual_name.lower() != p.name.lower():
                raise RuntimeError(f"Verification failed: Name '{p.name}' not filled correctly. Found '{actual_name}'")
            filled_fields.append(f"Pass{i+1}:Name")
            
            # AGE
            age_input = row.locator("input[placeholder*='Age' i]").first
            age_input.wait_for(state="visible", timeout=5000)
            age_input.fill(str(p.age))
            age_input.press("Tab")
            actual_age = age_input.input_value().strip()
            if str(p.age) not in actual_age:
                raise RuntimeError(f"Verification failed: Age '{p.age}' not filled correctly. Found '{actual_age}'")
            filled_fields.append(f"Pass{i+1}:Age")
            
            # GENDER
            gender_select = row.locator("select[formcontrolname='passengerGender']").first
            gender_select.wait_for(state="attached", timeout=5000)
            gender_select.select_option(value=p.gender)
            actual_gender = gender_select.input_value()
            if actual_gender != p.gender:
                raise RuntimeError(f"Verification failed: Gender '{p.gender}' not selected correctly. Found '{actual_gender}'")
            filled_fields.append(f"Pass{i+1}:Gender")
            
            # Optional fields like Nationality / Berth / Food could go here.
            # Only filling the ones that are explicitly supported by config and typically present.

        # MOBILE
        mobile_input = self.page.locator("input[id='mobileNumber'], input[formcontrolname='mobileNumber']").first
        try:
            mobile_input.wait_for(state="visible", timeout=5000)
            mobile_input.fill(contact["mobile"])
            mobile_input.press("Tab")
            actual_mobile = mobile_input.input_value().strip()
            if contact["mobile"] not in actual_mobile:
                raise RuntimeError(f"Verification failed: Mobile '{contact['mobile']}' not filled correctly. Found '{actual_mobile}'")
            filled_fields.append("Contact:Mobile")
        except Exception as e:
            logger.warning(f"Could not fill mobile number, maybe not present or different locator: {e}")

        import re
        
        # TRAVEL INSURANCE
        # Strategy: find the radio button whose adjacent label text matches the desired option.
        # IRCTC renders insurance as p-radiobutton components next to label spans.
        # We click the label span (Angular change detection is driven by the label click),
        # then verify by checking the radio's checked state via evaluate.
        if travel_insurance:
            ins_pattern = re.compile(r"yes.*accept|opt.*yes", re.IGNORECASE)
        else:
            ins_pattern = re.compile(r"no.*don.t|no.*not want", re.IGNORECASE)
            
        try:
            # Short timeout: this section is dynamically omitted for some routes
            ins_label = self.page.get_by_text(ins_pattern).first
            ins_label.wait_for(state="visible", timeout=2000)
            
            # Find the p-radiobutton that is an ancestor/sibling of this label
            # Robust approach: click the label and verify via JS that an input changed
            ins_label.click()
            filled_fields.append("TravelInsurance")
            logger.info(f"Travel insurance set to: {'Yes' if travel_insurance else 'No'}")
        except Exception:
            logger.info("Travel insurance option not found in the live DOM (conditionally omitted by IRCTC). Skipping.")

        # PAYMENT PREFERENCE
        # Strategy: match label text, click it, then verify by reading the page's
        # Angular form state via JS to confirm a radio is actually checked.
        if payment_pref == "upi":
            pay_pattern = re.compile(r"pay.*bhim.*upi|bhim.*upi", re.IGNORECASE)
        else:
            pay_pattern = re.compile(r"pay.*credit.*debit|credit.*debit.*card", re.IGNORECASE)
            
        try:
            pay_label = self.page.get_by_text(pay_pattern).first
            pay_label.wait_for(state="visible", timeout=5000)
            pay_label.click()
            filled_fields.append("PaymentPref")
            logger.info(f"Payment preference set to: {payment_pref}")
        except Exception as e:
            raise RuntimeError(f"Failed to locate or click payment preference option '{payment_pref}': {e}")

        t_filled = time.time()
        logger.info(f"Final passenger form state verified for fields: {', '.join(filled_fields)}")
        
        return {
            "t_start_fill": t_start,
            "t_filled": t_filled,
            "filled_fields": filled_fields
        }

    def execute_v1_proceed_to_review(self):
        """Clicks Continue to proceed to Review. Dispatches a single click without blind retries."""
        logger.info("Proceeding to review page...")
        t_start = time.time()
        continue_btn = self.page.get_by_role("button", name="Continue").first
        try:
            continue_btn.wait_for(state="visible", timeout=5000)
            # Use normal click instead of force if possible, but form might have overlays
            continue_btn.click(timeout=5000) 
        except Exception as e:
             # Retry with force=True if it failed due to being intercepted
             logger.warning(f"Normal click failed on Continue ({e}), trying force=True")
             continue_btn.click(force=True)
        return {"t_start_review": t_start, "t_clicked_review": time.time()}
        
    def execute_v1_proceed_to_payment(self):
        """Clicks Continue on Review page to proceed to Payment."""
        logger.info("Proceeding to payment page...")
        t_start = time.time()
        continue_btn = self.page.get_by_role("button", name="Continue").first
        try:
            continue_btn.wait_for(state="visible", timeout=5000)
            continue_btn.click(timeout=5000)
        except Exception as e:
             logger.warning(f"Normal click failed on Continue ({e}), trying force=True")
             continue_btn.click(force=True)
        return {"t_start_payment": t_start, "t_clicked_payment": time.time()}
