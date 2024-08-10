from flask import Flask, render_template, request, redirect, url_for, jsonify, Response
from functools import wraps
from datetime import datetime, timedelta
from twilio.http.http_client import TwilioHttpClient
from twilio.rest import Client
import logging
import random

app = Flask(__name__)

# Twilio credentials
account_sid = 'AC6687331bb2d392bf3b3cee82d1d61e8e'
auth_token = '8339b8615c62c3f817b3790aa6b42626'
twilio_number = '+12294945742'

# Proxy client setup
proxy_client = TwilioHttpClient(proxy={'http': 'http://proxy-chain.intel.com:916', 'https': 'http://proxy-chain.intel.com:916'})
client = None

try:
    client = Client(account_sid, auth_token, http_client=proxy_client)
    logging.info('Twilio client initialized successfully.')
except Exception as e:
    logging.error(f'Failed to initialize Twilio client: {e}')

# Configure logging
logging.basicConfig(level=logging.INFO)

# Data storage
appointments = []
current_appointment = None
pending_appointments = {}
phone_numbers = set()

# Authentication functions
def check_auth(username, password):
    return username == 'admin' and password == 'password'

def authenticate():
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.route('/')
@requires_auth
def index():
    available_slots = generate_time_slots()
    return render_template('index.html', appointments=appointments, available_slots=available_slots, current_appointment=current_appointment)

@app.route('/client')
def client_view():
    available_slots = generate_time_slots()
    
    # Remove already booked slots
    booked_slots = [appointment['time'] for appointment in appointments]
    filtered_slots = [slot for slot in available_slots if slot not in booked_slots]
    
    return render_template('client.html', available_slots=filtered_slots)

@app.route('/book', methods=['POST'])
def book_appointment():
    start_time = request.form['time']
    phone_number = request.form['phone_number']
    name = request.form['name']  # New field
    haircut_type = request.form['haircut_type']
    num_appointments = int(request.form.get('num_appointments', 1))  # Number of consecutive appointments

    # Normalize phone number
    if phone_number.startswith('0'):
        phone_number = '+972' + phone_number[1:]

    # Check for re-registration
    if phone_number in phone_numbers:
        return jsonify({'error': 'Phone number already registered'}), 400

    phone_numbers.add(phone_number)

    # Generate all time slots for the requested number of consecutive appointments
    start_datetime = datetime.strptime(start_time, "%H:%M")
    appointments_to_check = [(start_datetime + timedelta(minutes=15 * i)).strftime("%H:%M") for i in range(num_appointments)]
    
    # Check if all requested slots are available
    booked_slots = [appointment['time'] for appointment in appointments]
    if any(slot in booked_slots for slot in appointments_to_check):
        return jsonify({'error': 'One or more of the selected slots are already booked'}), 400

    verification_code = str(random.randint(1000, 9999))
    pending_appointments[phone_number] = {
        'slots': appointments_to_check, 
        'name': name,
        'haircut_type': haircut_type,
        'code': verification_code
    }

    # Send SMS for verification
    if client:
        try:
            message = client.messages.create(
                body=f'Your appointments are scheduled for {", ".join(appointments_to_check)}. Reply with {verification_code} to confirm.',
                from_=twilio_number,
                to=phone_number
            )
            logging.info(f'SMS sent successfully to {phone_number}: {message.sid}')
        except Exception as e:
            logging.error(f'Failed to send SMS to {phone_number}: {e}')
    else:
        logging.error('Twilio client is not initialized.')

    return render_template('verify.html', phone_number=phone_number)

@app.route('/verify', methods=['POST'])
def verify_appointment():
    phone_number = request.form['phone_number']
    code = request.form['code']
    
    if phone_number in pending_appointments:
        appointment = pending_appointments[phone_number]
        if code == appointment['code']:
            for slot in appointment['slots']:
                appointments.append({'time': slot, 'phone_number': phone_number, 'name': appointment['name'], 'haircut_type': appointment['haircut_type']})
            del pending_appointments[phone_number]
            return redirect(url_for('client_view'))
        else:
            return jsonify({'error': 'Invalid verification code'}), 400
    return jsonify({'error': 'Phone number not found'}), 404

@app.route('/update_current', methods=['POST'])
@requires_auth
def update_current():
    global current_appointment
    current_appointment = request.form['current_appointment']
    return redirect(url_for('index'))

@app.route('/appointments')
def get_appointments():
    return jsonify(appointments=appointments, current_appointment=current_appointment)

@app.route('/cancel/<phone_number>', methods=['POST'])
def cancel_appointment(phone_number):
    global appointments
    appointments = [appt for appt in appointments if appt['phone_number'] != phone_number]
    if phone_number in phone_numbers:
        phone_numbers.remove(phone_number)
    return redirect(url_for('index'))

def generate_time_slots():
    slots = []
    start_time = datetime.strptime("09:00", "%H:%M")
    end_time = datetime.strptime("17:00", "%H:%M")
    while start_time < end_time:
        slots.append(start_time.strftime("%H:%M"))
        start_time += timedelta(minutes=15)
    return slots

if __name__ == '__main__':
    app.run(debug=True)
