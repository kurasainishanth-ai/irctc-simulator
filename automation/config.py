from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Passenger:
    name: str
    age: int
    gender: str

@dataclass
class BookingPreferences:
    preferred_trains: List[str]  # e.g., ["12723", "12615"]
    preferred_classes: List[str]  # e.g., ["SL", "3A", "2A"]
    passengers: List[Passenger]
    allow_waitlist: bool = False

@dataclass
class SearchConfig:
    source: str
    destination: str
    journey_date: str
    class_pref: str = "All Classes"

@dataclass
class AgentConfig:
    base_url: str = "http://127.0.0.1:5001"
    headless: bool = False
    slow_mo: int = 500  # for observation
