from flask import Flask, render_template, request, redirect, url_for, session, flash
import random
import string
import uuid

app = Flask(__name__)
app.secret_key = 'irctc_simulator_secret'

# Mock Database
TRAINS = [
    {
        "train_number": "12760",
        "train_name": "CHARMINAR SF EXP",
        "from_station": "HYDERABAD",
        "to_station": "CHENNAI",
        "departure": "18:25",
        "arrival": "08:00",
        "duration": "13:35",
        "running_days": "M T W Th F S Su",
        "classes": {
            "SL": {"availability": "AVAILABLE 120", "fare": 435, "status": "available"},
            "3A": {"availability": "WL 10", "fare": 1165, "status": "waitlist"},
            "2A": {"availability": "AVAILABLE 15", "fare": 1660, "status": "available"},
            "1A": {"availability": "NOT AVAILABLE", "fare": 2815, "status": "unavailable"}
        }
    },
    {
        "train_number": "12723",
        "train_name": "TELANGANA EXP",
        "from_station": "HYDERABAD",
        "to_station": "NEW DELHI",
        "departure": "06:00",
        "arrival": "07:15",
        "duration": "25:15",
        "running_days": "M T W Th F S Su",
        "classes": {
            "SL": {"availability": "AVAILABLE 45", "fare": 650, "status": "available"},
            "3A": {"availability": "AVAILABLE 10", "fare": 1700, "status": "available"},
            "2A": {"availability": "WL 12", "fare": 2400, "status": "waitlist"},
            "1A": {"availability": "NOT AVAILABLE", "fare": 4100, "status": "unavailable"}
        }
    },
    {
        "train_number": "12615",
        "train_name": "GT EXPRESS",
        "from_station": "HYDERABAD",
        "to_station": "NEW DELHI",
        "departure": "17:15",
        "arrival": "06:30",
        "duration": "13:15",
        "running_days": "M T W Th F S Su",
        "classes": {
            "SL": {"availability": "NOT AVAILABLE", "fare": 630, "status": "unavailable"},
            "3A": {"availability": "NOT AVAILABLE", "fare": 1650, "status": "unavailable"}
        }
    }
]

EXPECTED_CAPTCHA = "ABCD"
USER_WALLET_BALANCE = 5000  # Will be reset on login to simulate balance

def check_state(*required_keys):
    for key in required_keys:
        if key not in session:
            flash(f"Invalid state transition. Missing: {key}", "error")
            return False
    return True

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username and password:
            session.clear()
            session['logged_in'] = True
            session['username'] = username
            session['wallet_balance'] = USER_WALLET_BALANCE
            return redirect(url_for('search'))
        flash("Please enter both username and password.", "error")
    return render_template('login.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    if not check_state('logged_in'): return redirect(url_for('login'))
    
    if request.method == 'POST':
        session['search_criteria'] = {
            'from_station': request.form.get('from_station').upper(),
            'to_station': request.form.get('to_station').upper(),
            'date': request.form.get('date'),
            'class_pref': request.form.get('class_pref')
        }
        return redirect(url_for('results'))
    
    return render_template('search.html')

@app.route('/results', methods=['GET', 'POST'])
def results():
    if not check_state('logged_in', 'search_criteria'): return redirect(url_for('search'))
    
    criteria = session['search_criteria']
    # Filter matching trains based on exact station match for simplicity
    matched_trains = [t for t in TRAINS if t['from_station'] == criteria['from_station'] and t['to_station'] == criteria['to_station']]
    
    if request.method == 'POST':
        train_no = request.form.get('train_number')
        class_selected = request.form.get('class_selected')
        
        # Validate train & class
        selected_train = next((t for t in matched_trains if t['train_number'] == train_no), None)
        if selected_train and class_selected in selected_train['classes']:
            cls_info = selected_train['classes'][class_selected]
            if cls_info['status'] == 'unavailable':
                flash("Selected class is NOT AVAILABLE. Cannot proceed.", "error")
                return redirect(url_for('results'))
            
            session['selected_train'] = {
                'train_number': selected_train['train_number'],
                'train_name': selected_train['train_name'],
                'departure': selected_train['departure'],
                'arrival': selected_train['arrival'],
                'duration': selected_train['duration'],
                'from_station': selected_train['from_station'],
                'to_station': selected_train['to_station'],
                'class': class_selected,
                'fare': cls_info['fare'],
                'availability': cls_info['availability']
            }
            return redirect(url_for('passengers'))
            
        flash("Invalid train or class selection.", "error")
        return redirect(url_for('results'))
        
    return render_template('results.html', trains=matched_trains, criteria=criteria)

@app.route('/passengers', methods=['GET', 'POST'])
def passengers():
    if not check_state('logged_in', 'selected_train'): return redirect(url_for('search'))
    
    if request.method == 'POST':
        names = request.form.getlist('name[]')
        ages = request.form.getlist('age[]')
        genders = request.form.getlist('gender[]')
        nationalities = request.form.getlist('nationality[]')
        berth_prefs = request.form.getlist('berth_pref[]')
        
        mobile = request.form.get('mobile')
        email = request.form.get('email')
        
        passengers_list = []
        for i in range(len(names)):
            n = names[i]
            if n:  # If name is provided, consider it a valid passenger
                passengers_list.append({
                    "name": n, 
                    "age": ages[i] if i < len(ages) else "", 
                    "gender": genders[i] if i < len(genders) else "",
                    "nationality": nationalities[i] if i < len(nationalities) else "",
                    "berth_pref": berth_prefs[i] if i < len(berth_prefs) else ""
                })
                
        if not passengers_list:
            flash("Please add at least one passenger.", "error")
            return redirect(url_for('passengers'))
            
        session['passengers'] = passengers_list
        # Convenience fee is a standard ₹30 for simulator
        session['base_fare'] = len(passengers_list) * session['selected_train']['fare']
        session['convenience_fee'] = 30.0
        session['total_fare'] = session['base_fare'] + session['convenience_fee']
        session['contact_details'] = {"mobile": mobile, "email": email}
        
        return redirect(url_for('review'))
        
    return render_template('passengers.html', train=session['selected_train'])

@app.route('/review', methods=['GET', 'POST'])
def review():
    if not check_state('logged_in', 'selected_train', 'passengers'): return redirect(url_for('search'))
    
    if request.method == 'POST':
        # Simulated review journey page, continue to payment
        session['review_passed'] = True
        return redirect(url_for('payment'))
            
    return render_template('review.html', 
                           train=session['selected_train'], 
                           passengers=session['passengers'], 
                           base_fare=session.get('base_fare', 0),
                           convenience_fee=session.get('convenience_fee', 30),
                           total_fare=session['total_fare'],
                           contact=session.get('contact_details', {}))

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if not check_state('logged_in', 'review_passed'): return redirect(url_for('search'))
    
    if request.method == 'POST':
        gateway = request.form.get('gateway')
        if gateway == 'ewallet':
            session['payment_gateway'] = 'ewallet'
            return redirect(url_for('ewallet'))
        flash("Only IRCTC eWallet is supported in this simulator.", "error")
        
    return render_template('payment.html', total_fare=session['total_fare'])

@app.route('/ewallet', methods=['GET', 'POST'])
def ewallet():
    if not check_state('logged_in', 'payment_gateway'): return redirect(url_for('search'))
    
    if request.method == 'POST':
        total_fare = session['total_fare']
        wallet_balance = session.get('wallet_balance', 0)
        
        if wallet_balance < total_fare:
            flash(f"Payment rejected: Insufficient Wallet Balance. Required: ₹{total_fare}, Available: ₹{wallet_balance}", "error")
        else:
            # Deduct balance and generate PNR directly in eWallet flow
            session['wallet_balance'] -= session['total_fare']
            session['pnr'] = "".join(random.choices(string.digits, k=10))
            session['booking_success'] = True
            return redirect(url_for('success'))
            
    return render_template('ewallet.html', balance=session.get('wallet_balance', 0), total_fare=session['total_fare'])

@app.route('/success')
def success():
    if not check_state('logged_in', 'booking_success'): return redirect(url_for('search'))
    return render_template('success.html', pnr=session['pnr'], train=session['selected_train'], passengers=session['passengers'], total_fare=session['total_fare'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)
