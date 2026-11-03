import unittest
import logging
from config import BookingPreferences, Passenger
from decision_engine import DecisionEngine

# Disable logging output for cleaner test results
logging.getLogger("decision_engine").setLevel(logging.CRITICAL)

class TestDecisionEngine(unittest.TestCase):
    def setUp(self):
        self.dummy_passengers = [Passenger(name="Test", age=30, gender="M")]
        
    def test_preferred_train_and_class_available(self):
        """Scenario 1: Preferred train and class available"""
        prefs = BookingPreferences(
            preferred_trains=["12723", "12615"],
            preferred_classes=["SL", "3A", "2A", "1A"],
            passengers=self.dummy_passengers
        )
        engine = DecisionEngine(prefs)
        
        train_results = [
            {
                "train_number": "12723",
                "classes": [
                    {"class": "SL", "status": "available"},
                    {"class": "3A", "status": "available"},
                    {"class": "2A", "status": "waitlist"},
                    {"class": "1A", "status": "unavailable"}
                ]
            },
            {
                "train_number": "12615",
                "classes": [{"class": "SL", "status": "unavailable"}]
            }
        ]
        
        result = engine.select_best_option(train_results)
        self.assertEqual(result, ("12723", "SL"))

    def test_preferred_class_unavailable_fallback(self):
        """Scenario 2: Preferred class unavailable -> fallback class"""
        prefs = BookingPreferences(
            preferred_trains=["12723"],
            preferred_classes=["SL", "3A", "2A", "1A"],
            passengers=self.dummy_passengers
        )
        engine = DecisionEngine(prefs)
        
        train_results = [
            {
                "train_number": "12723",
                "classes": [
                    {"class": "SL", "status": "unavailable"},
                    {"class": "3A", "status": "available"},
                    {"class": "2A", "status": "waitlist"},
                    {"class": "1A", "status": "unavailable"}
                ]
            }
        ]
        
        result = engine.select_best_option(train_results)
        self.assertEqual(result, ("12723", "3A"))

    def test_waitlist_not_allowed(self):
        """Scenario 3: Waitlist not explicitly allowed, fallback to available"""
        prefs = BookingPreferences(
            preferred_trains=["12723"],
            preferred_classes=["SL", "3A"],
            passengers=self.dummy_passengers,
            allow_waitlist=False
        )
        engine = DecisionEngine(prefs)
        
        train_results = [
            {
                "train_number": "12723",
                "classes": [
                    {"class": "SL", "status": "waitlist"},
                    {"class": "3A", "status": "available"}
                ]
            }
        ]
        
        result = engine.select_best_option(train_results)
        self.assertEqual(result, ("12723", "3A"))

    def test_waitlist_allowed(self):
        """Scenario 3b: Waitlist allowed explicitly"""
        prefs = BookingPreferences(
            preferred_trains=["12723"],
            preferred_classes=["SL", "3A"],
            passengers=self.dummy_passengers,
            allow_waitlist=True
        )
        engine = DecisionEngine(prefs)
        
        train_results = [
            {
                "train_number": "12723",
                "classes": [
                    {"class": "SL", "status": "waitlist"},
                    {"class": "3A", "status": "available"}
                ]
            }
        ]
        
        result = engine.select_best_option(train_results)
        self.assertEqual(result, ("12723", "SL"))

    def test_all_unavailable(self):
        """Scenario 4: All unavailable -> No suitable option"""
        prefs = BookingPreferences(
            preferred_trains=["12723", "12615"],
            preferred_classes=["SL", "3A"],
            passengers=self.dummy_passengers
        )
        engine = DecisionEngine(prefs)
        
        train_results = [
            {
                "train_number": "12723",
                "classes": [{"class": "SL", "status": "unavailable"}, {"class": "3A", "status": "unavailable"}]
            },
            {
                "train_number": "12615",
                "classes": [{"class": "SL", "status": "unavailable"}]
            }
        ]
        
        result = engine.select_best_option(train_results)
        self.assertIsNone(result)

    def test_preferred_train_unavailable_fallback(self):
        """Preferred train totally unavailable -> fallback to second preferred train"""
        prefs = BookingPreferences(
            preferred_trains=["12723", "12615"],
            preferred_classes=["SL", "3A"],
            passengers=self.dummy_passengers
        )
        engine = DecisionEngine(prefs)
        
        train_results = [
            {
                "train_number": "12723",
                "classes": [{"class": "SL", "status": "unavailable"}, {"class": "3A", "status": "unavailable"}]
            },
            {
                "train_number": "12615",
                "classes": [{"class": "SL", "status": "available"}, {"class": "3A", "status": "unavailable"}]
            }
        ]
        
        result = engine.select_best_option(train_results)
        self.assertEqual(result, ("12615", "SL"))

if __name__ == '__main__':
    unittest.main()
