from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os
import logging
import bcrypt

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["*", "http://localhost:5000", "https://*.onrender.com"])

# Database configuration
DATABASE = 'applications.db'

# Email configuration
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
ADMIN_EMAIL = EMAIL_ADDRESS

# Valid options
VALID_LANGUAGES = ['English', 'Spanish', 'French', 'German', 'Chinese', 'Arabic', 'Portuguese', 'Russian', 'Japanese', 'Korean']
VALID_AVAILABILITY = ['Day', 'Night', 'Both']

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL,
            experience_level TEXT,
            language TEXT,
            availability TEXT,
            motivation TEXT CHECK(length(motivation) <= 500),
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    try:
        cursor.execute("ALTER TABLE applications ADD COLUMN status TEXT DEFAULT 'pending';")
        logger.info("Added status column")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            logger.error(f"Error adding status column: {e}")
    
    default_email = "admin@work4u.com"
    default_password = "admin123"
    cursor.execute("SELECT COUNT(*) FROM admins WHERE email = ?", (default_email,))
    if cursor.fetchone()[0] == 0:
        hashed_pw = bcrypt.hashpw(default_password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute('INSERT INTO admins (username, email, password_hash) VALUES (?, ?, ?)',
                       ("admin", default_email, hashed_pw))
        logger.info(f"Created default admin: {default_email}")
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

# ✅ Serve admin.html at root
@app.route('/')
def serve_admin():
    return send_from_directory('.', 'admin.html')

def send_email(to_email, subject, body):
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        logger.warning("Email not configured")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = f"Work4U <{EMAIL_ADDRESS}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        server.quit()
        logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Email failed: {e}")
        return False

def send_confirmation_email(first_name, last_name, email):
    body = f"""Hi {first_name} {last_name},

We are delighted to let you know that we have successfully received your application. Thank you for showing interest in joining our team. We truly value the time and effort you put into applying.

Our recruitment team will carefully review your details and get back to you within 3 days.

If you find this email in your spam or promotions folder, kindly mark it as "Not Spam" so you won't miss our updates.

We look forward to the possibility of working together.

Best regards,
Work4U Recruitment Team"""
    return send_email(email, "Thank you for applying with us", body)

def send_admin_notification(first_name, last_name, applicant_email, language, created_at):
    formatted = created_at.strftime("%B %d, %Y at %I:%M %p")
    body = f"""Hello Admin,

A new application has just been submitted. Here are the applicant's details:

Full Name: {first_name} {last_name}
Email Address: {applicant_email}
Language Applied For: {language}
Date Submitted: {formatted}

Please log in to the dashboard for full application details.

Best regards,
Work4U Recruitment System"""
    return send_email(ADMIN_EMAIL, "New Application Received", body)

def send_approval_email(first_name, last_name, email):
    body = f"""Hi {first_name} {last_name},

Congratulations! Your application has been approved. Welcome to Work4U!

We are excited to have you join our team of dedicated professionals. Our team will be in touch shortly with next steps regarding onboarding and training.

Thank you for your interest in Work4U.

Best regards,
Work4U Recruitment Team"""
    return send_email(email, "Congratulations! Your Application Has Been Approved", body)

def send_rejection_email(first_name, last_name, email):
    body = f"""Hi {first_name} {last_name},

Thank you for your application and interest in joining Work4U.

After careful consideration, we regret to inform you that we cannot proceed with your application at this time. We appreciate the time and effort you invested in your application.

We encourage you to apply for future opportunities with us.

Best regards,
Work4U Recruitment Team"""
    return send_email(email, "Regarding Your Application", body)

# --- Password Change Endpoint ---
@app.route('/change-password', methods=['POST'])
def change_password():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No JSON data"}), 400
        
        current_password = data.get('currentPassword')
        new_password = data.get('newPassword')
        confirm_password = data.get('confirmPassword')
        admin_email = data.get('email', 'admin@work4u.com')
        
        if not all([current_password, new_password, confirm_password]):
            return jsonify({"status": "error", "message": "All fields required"}), 400
        if new_password != confirm_password:
            return jsonify({"status": "error", "message": "Passwords do not match"}), 400
        if len(new_password) < 6:
            return jsonify({"status": "error", "message": "Password too short"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, password_hash FROM admins WHERE email = ?', (admin_email,))
        admin = cursor.fetchone()
        if not admin or not bcrypt.checkpw(current_password.encode('utf-8'), admin['password_hash']):
            conn.close()
            return jsonify({"status": "error", "message": "Invalid current password"}), 401

        new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute('UPDATE admins SET password_hash = ? WHERE id = ?', (new_hash, admin['id']))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Password updated"})
    except Exception as e:
        logger.error(f"Password change error: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500

@app.route('/apply', methods=['POST'])
def submit_application():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data"}), 400
        
        required = ['first_name', 'last_name', 'email', 'experience_level', 'language', 'availability']
        for field in required:
            if not data.get(field):
                return jsonify({"status": "error", "message": f"Missing {field}"}), 400
        
        if data['experience_level'] not in ['Yes', 'No']:
            return jsonify({"status": "error", "message": "Invalid experience"}), 400
        if data['language'] not in VALID_LANGUAGES:
            return jsonify({"status": "error", "message": "Invalid language"}), 400
        if data['availability'] not in VALID_AVAILABILITY:
            return jsonify({"status": "error", "message": "Invalid availability"}), 400
        if '@' not in data['email']:
            return jsonify({"status": "error", "message": "Invalid email"}), 400

        motivation = str(data.get('motivation', ''))[:500]
        now = datetime.now()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO applications (first_name, last_name, email, experience_level, language, availability, motivation, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data['first_name'], data['last_name'], data['email'], data['experience_level'],
              data['language'], data['availability'], motivation, now))
        app_id = cursor.lastrowid
        conn.commit()
        conn.close()

        send_confirmation_email(data['first_name'], data['last_name'], data['email'])
        send_admin_notification(data['first_name'], data['last_name'], data['email'], data['language'], now)
        return jsonify({"status": "success", "message": "Submitted"})
    except Exception as e:
        logger.error(f"Submission error: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500

@app.route('/applications', methods=['GET'])
def get_applications():
    try:
        conn = get_db_connection()
        apps = conn.execute('SELECT * FROM applications ORDER BY created_at DESC').fetchall()
        result = [dict(app) for app in apps]
        conn.close()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch"}), 500

@app.route('/applications/<int:app_id>/approve', methods=['POST'])
def approve_application(app_id):
    try:
        conn = get_db_connection()
        app = conn.execute('SELECT * FROM applications WHERE id = ?', (app_id,)).fetchone()
        if not app:
            conn.close()
            return jsonify({"status": "error", "message": "Not found"}), 404
        conn.execute('UPDATE applications SET status = "approved" WHERE id = ?', (app_id,))
        conn.commit()
        conn.close()
        send_approval_email(app['first_name'], app['last_name'], app['email'])
        return jsonify({"status": "success", "message": "Approved"})
    except Exception as e:
        logger.error(f"Approve error: {e}")
        return jsonify({"status": "error", "message": "Approve failed"}), 500

@app.route('/applications/<int:app_id>/reject', methods=['POST'])
def reject_application(app_id):
    try:
        conn = get_db_connection()
        app = conn.execute('SELECT * FROM applications WHERE id = ?', (app_id,)).fetchone()
        if not app:
            conn.close()
            return jsonify({"status": "error", "message": "Not found"}), 404
        conn.execute('UPDATE applications SET status = "rejected" WHERE id = ?', (app_id,))
        conn.commit()
        conn.close()
        send_rejection_email(app['first_name'], app['last_name'], app['email'])
        return jsonify({"status": "success", "message": "Rejected"})
    except Exception as e:
        logger.error(f"Reject error: {e}")
        return jsonify({"status": "error", "message": "Reject failed"}), 500

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)