import logging
import sys
class BadHandler(logging.Handler):
    def emit(self, record):
        raise ValueError("I crash!")
    def handleError(self, record):
        raise ValueError("HandleError crashes!")
logging.getLogger().addHandler(BadHandler())
logging.info("Hello")
print("I survived!")
