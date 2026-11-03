from typing import List, Dict, Any, Optional, Tuple
from config import BookingPreferences
import logging

logger = logging.getLogger(__name__)

class DecisionEngine:
    def __init__(self, preferences: BookingPreferences):
        self.preferences = preferences

    def select_best_option(self, train_results: List[Dict[str, Any]]) -> Optional[Tuple[str, str]]:
        """
        Returns a tuple of (train_number, class_name) or None if no suitable option is found.
        """
        logger.info(f"Decision Engine evaluating options.")
        logger.info(f"Preferences - Trains: {self.preferences.preferred_trains}, Classes: {self.preferences.preferred_classes}, Allow Waitlist: {self.preferences.allow_waitlist}")
        
        # Convert results list into a dictionary mapped by train_number for O(1) lookup
        results_map = {t["train_number"]: t for t in train_results}
        
        # Iterate over preferred trains in strict priority order
        for preferred_train in self.preferences.preferred_trains:
            if preferred_train not in results_map:
                logger.debug(f"Train {preferred_train} not found in search results. Skipping.")
                continue
                
            train_data = results_map[preferred_train]
            classes = {c["class"]: c for c in train_data.get("classes", [])}
            
            # Iterate over preferred classes in strict priority order
            for preferred_class in self.preferences.preferred_classes:
                if preferred_class not in classes:
                    logger.debug(f"Class {preferred_class} not offered on Train {preferred_train}. Skipping.")
                    continue
                    
                cls_info = classes[preferred_class]
                status = cls_info.get("status")
                
                if status == "available":
                    logger.info(f"Found best available option: Train {preferred_train}, Class {preferred_class}")
                    return (preferred_train, preferred_class)
                    
                if status == "waitlist" and self.preferences.allow_waitlist:
                    logger.info(f"Found best waitlist option (waitlist allowed): Train {preferred_train}, Class {preferred_class}")
                    return (preferred_train, preferred_class)
                
                logger.debug(f"Train {preferred_train}, Class {preferred_class} status is '{status}'. Skipping.")

        logger.warning("No suitable option found matching user preferences.")
        return None
