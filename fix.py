import sys

with open('automation/real_irctc_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# We will just rewrite the select_train_and_class function completely to ensure it's correct.

def replace_func():
    global content
    # Find start of select_train_and_class
    start = content.find("    def select_train_and_class(")
    # Find start of fill_passenger_details
    end = content.find("    def fill_passenger_details(")
    
    if start == -1 or end == -1:
        print("Could not find functions")
        return
        
    new_func = \"\"\"    def select_train_and_class(self, train_num: str, cls_name: str):
        \"\"\"Results page -> click class -> book now\"\"\"
        cards = self.page.locator("app-train-avl-enq").all()
        for card in cards:
            if train_num in card.inner_text():
                # Locate availability table
                avail_table = card.locator("table").last
                
                # Check if we need to click the class td first
                class_tds = card.locator("td").all()
                for cls_td in class_tds:
                    if cls_name in cls_td.inner_text() and "Refresh" in cls_td.inner_text():
                        cls_td.click()
                        self.page.wait_for_timeout(500)
                
                date_tds = avail_table.locator("td").all()
                if len(date_tds) > 1:
                    first_date_td = date_tds[1]
                else:
                    first_date_td = avail_table.locator("td").first
                
                date_div = first_date_td.locator("div").first
                date_div.click(force=True)
                
                # Wait for Book Now button to be enabled (lose 'disable-book' class)
                try:
                    book_btn = card.locator("button:has-text('Book Now')").first
                    for _ in range(10):
                        if "disable-book" not in book_btn.get_attribute("class"):
                            break
                        import time
                        time.sleep(0.2)
                except Exception:
                    pass
                        
                book_btn = card.get_by_role("button", name="Book Now").first
                if book_btn.is_visible():
                    book_btn.click(force=True)
                    
                    # Handle possible confirmation dialogs (e.g. 'I Agree', 'Yes')
                    try:
                        dialog = self.page.locator("p-dialog, p-confirmdialog").first
                        dialog.wait_for(state="visible", timeout=3000)
                        if dialog.is_visible():
                            agree = self.page.locator("button:has-text('I Agree'), button:has-text('Yes')").first
                            if agree.is_visible():
                                agree.click()
                    except Exception:
                        pass
                    
                    return

\"\"\"
    
    new_content = content[:start] + new_func + content[end:]
    with open('automation/real_irctc_agent.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Fixed select_train_and_class")

replace_func()
