from flask import Flask
import logging
import test_real_irctc_v1_direct
app = Flask(__name__)
@app.route("/")
def index():
    print("ROUTE HIT", flush=True)
    test_real_irctc_v1_direct.logger.info("THIS IS A TEST LOG")
    return "OK"
if __name__ == "__main__":
    app.run(port=5006)
