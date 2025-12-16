# app.py
import sqlite3
from flask import Flask, request, jsonify, g, session, send_from_directory, abort, Response
from werkzeug.security import generate_password_hash, check_password_hash
from random import randint
from datetime import datetime, timedelta
from flask_cors import CORS
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Additional imports for news scraping/proxy
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import concurrent.futures

# Load environment variables from .env file (if present)
load_dotenv()

# -------------------------
# App / Config
# -------------------------
app = Flask(__name__, static_folder='.')
app.secret_key = os.environ.get("FLASK_SECRET", "YOUR_SECRET_KEY_123")   # change this or set FLASK_SECRET in .env
# Development friendly CORS. In production restrict origins.
CORS(app, supports_credentials=True)

# Configure session cookie settings for development
app.config.update(
    SESSION_COOKIE_SECURE=False,  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',  # or 'None' if you need cross-site cookies
)

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "app.db")
OTP_TTL_SECONDS = 300   # 5 minutes

# Gmail SMTP Configuration (for sending OTPs)
GMAIL_USER = os.environ.get('GMAIL_USER')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD')
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# -------------------------
# Database Helpers
# -------------------------
def get_db():
    db = getattr(g, "_db", None)
    if db is None:
        db = g._db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, "_db", None)
    if db:
        db.close()


def init_db():
    db = get_db()
    cur = db.cursor()

    # Users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            location TEXT,
            phone TEXT,
            role TEXT DEFAULT 'User',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # OTP table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS otps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            otp TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.commit()


# -------------------------
# OTP Utils
# -------------------------
def gen_otp():
    return str(randint(100000, 999999))


def store_otp(email, otp):
    db = get_db()
    expires = (datetime.utcnow() + timedelta(seconds=OTP_TTL_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
    cur = db.cursor()
    cur.execute(
        "INSERT INTO otps (email, otp, expires_at, used) VALUES (?, ?, ?, 0)",
        (email.lower(), otp, expires)
    )
    db.commit()


def send_otp_email(email, otp):
    """
    Send OTP via Gmail SMTP.
    Returns (success: bool, error_message: str or None)
    """
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = email
        msg['Subject'] = "Your OTP for Account Registration"
        
        body = f"""
        Hello,
        
        Your OTP for account registration is: {otp}
        
        This OTP is valid for 5 minutes.
        
        If you didn't request this OTP, please ignore this email.
        
        Best regards,
        Team
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Create SMTP session
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()  # Enable TLS encryption
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        
        # Send email
        text = msg.as_string()
        server.sendmail(GMAIL_USER, email, text)
        server.quit()
        
        return True, None
    except Exception as e:
        return False, str(e)


def verify_stored_otp(email, otp):
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT id, otp, expires_at, used FROM otps
        WHERE email = ? AND used = 0
        ORDER BY created_at DESC LIMIT 1
    """, (email.lower(),))
    row = cur.fetchone()

    if not row:
        return False, "no_otp"

    try:
        exp = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
    except:
        return False, "invalid_expiry"

    if datetime.utcnow() > exp:
        return False, "expired"

    if str(row["otp"]) != str(otp).strip():
        return False, "wrong"

    # mark as used
    cur.execute("UPDATE otps SET used = 1 WHERE id = ?", (row["id"],))
    db.commit()

    return True, "verified"


# -------------------------
# ROUTES
# -------------------------

# 1) SEND OTP
@app.route("/send-otp", methods=["POST"])
def send_otp():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "missing_email"}), 400

    otp = gen_otp()

    try:
        store_otp(email, otp)
    except Exception as e:
        return jsonify({"error": "db_error", "detail": str(e)}), 500

    # Send OTP via email
    if GMAIL_USER and GMAIL_APP_PASSWORD:
        success, error = send_otp_email(email, otp)
        if success:
            return jsonify({"sent": True})
        else:
            return jsonify({"error": "email_failed", "detail": error}), 500
    else:
        return jsonify({"error": "email_not_configured"}), 500


# 2) VERIFY OTP
@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").lower()
    otp = (data.get("otp") or "").strip()

    ok, reason = verify_stored_otp(email, otp)

    return jsonify({"verified": ok, "reason": reason}), (200 if ok else 400)


# 3) CREATE ACCOUNT
@app.route("/create-account", methods=["POST"])
def create_account():
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    location = data.get("location") or ""
    phone = data.get("phone") or ""

    # validations
    if not name:
        return jsonify({"error": "missing_name"}), 400
    if not email:
        return jsonify({"error": "missing_email"}), 400
    if not password:
        return jsonify({"error": "missing_password"}), 400

    # hash password
    pw_hash = generate_password_hash(password)

    db = get_db()
    cur = db.cursor()

    try:
        cur.execute("""
            INSERT INTO users (name, email, password_hash, location, phone)
            VALUES (?, ?, ?, ?, ?)
        """, (name, email, pw_hash, location, phone))
        db.commit()
        user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "email_exists"}), 400
    except Exception as e:
        return jsonify({"error": "db_error", "detail": str(e)}), 500

    # set session
    session["user_id"] = user_id
    session["email"] = email

    return jsonify({"created": True, "user": {
        "id": user_id,
        "name": name,
        "email": email,
        "location": location,
        "phone": phone
    }})


# 4) LOGIN
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "missing_fields"}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, name, email, password_hash, location, phone FROM users WHERE email = ?", (email,))
    user = cur.fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid_credentials"}), 401

    # set session
    session["user_id"] = user["id"]
    session["email"] = user["email"]

    return jsonify({"logged_in": True, "user": {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "location": user["location"],
        "phone": user["phone"]
    }})


# 5) LOGOUT
@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"logged_out": True})


# 6) GET PROFILE
@app.route("/profile")
def profile():
    print("Profile request received")
    print("Session data:", dict(session))
    user_id = session.get("user_id")
    if not user_id:
        print("No user_id in session")
        return jsonify({"error": "not_logged_in"}), 401

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, name, email, location, phone FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()

    if not user:
        print("User not found in database")
        return jsonify({"error": "user_not_found"}), 404

    print("Returning user data:", dict(user))
    return jsonify({"user": {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "location": user["location"],
        "phone": user["phone"]
    }})


# 7) SERVE STATIC FILES
@app.route("/<path:filename>")
def serve_static(filename):
    # security: prevent traversal
    if ".." in filename or filename.startswith("/"):
        abort(404)
    
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        abort(404)
        
    return send_from_directory('.', filename)


# 8) UPDATE PASSWORD
@app.route("/update-password", methods=["POST"])
def update_password():
    # Check if user is logged in
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "not_logged_in"}), 401

    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""

    # Validate new password with stronger requirements
    if len(new_password) < 8:
        return jsonify({"error": "password_too_short", "detail": "Password must be at least 8 characters"}), 400
    
    # Check for at least one uppercase letter
    if not any(c.isupper() for c in new_password):
        return jsonify({"error": "password_no_uppercase", "detail": "Password must contain at least one uppercase letter"}), 400
    
    # Check for at least one lowercase letter
    if not any(c.islower() for c in new_password):
        return jsonify({"error": "password_no_lowercase", "detail": "Password must contain at least one lowercase letter"}), 400
    
    # Check for at least one digit
    if not any(c.isdigit() for c in new_password):
        return jsonify({"error": "password_no_digit", "detail": "Password must contain at least one number"}), 400
    
    # Check for at least one special character
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in new_password):
        return jsonify({"error": "password_no_special", "detail": "Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)"}), 400

    # Get current user
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, password_hash FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()

    if not user:
        return jsonify({"error": "user_not_found"}), 404

    # Note: For password update, we typically don't require current password for email-verified updates
    # But if you want to require it, uncomment the following lines:
    # if not check_password_hash(user["password_hash"], current_password):
    #     return jsonify({"error": "invalid_current_password"}), 400

    # Hash new password and update
    new_pw_hash = generate_password_hash(new_password)
    cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_pw_hash, user_id))
    db.commit()

    return jsonify({"updated": True, "message": "Password updated successfully"})


# -------------------------
# NEWS: Static seed + HTML pages + JSON + proxy
# -------------------------
# NEWS_SEED (11 items you provided)
NEWS_SEED = [
    {"title":"India’s pension funds warn proposed bond rules may distort values","source":{"name":"Economic Times"},"url":"https://economictimes.indiatimes.com/news/economy/finance/indias-pension-funds-warn-proposed-bond-rules-may-distort-values/articleshow/125902100.cms","description":"Pension-fund managers caution that proposed bond-market rules could distort valuations and hurt long-term investors.","category":"Bonds / Regulatory","image":"/images/Pension.jpg"},
    {"title":"RBI cuts repo rate by 25 bp to 5.25% — ‘rare Goldilocks period’ for economy","source":{"name":"Indian Express"},"url":"https://indianexpress.com/article/business/economy/repo-rate-cut-25-bp-to-5-25-rare-goldilocks-period-says-rbi-governor-10405107/?ref=business_pg","description":"The Reserve Bank of India trims its key repo rate, citing low inflation and stable growth — signalling support for growth.","category":"RBI / Monetary Policy","image":"/images/repo rate.jpg"},
    {"title":"SGB 2017-18 Series XI matures; ₹1 lakh investment now worth over ₹4.3 lakh","source":{"name":"Moneycontrol"},"url":"https://www.moneycontrol.com/news/business/personal-finance/sgb-2017-18-series-xi-matures-on-dec-11-rs-1-lakh-investment-now-worth-over-rs-4-3-lakh-as-rbi-sets-redemption-price-13720119.html","description":"The Sovereign Gold Bond 2017-18 Series XI matures today — early investors see substantial returns.","category":"Investments / Bonds","image":"/images/investment.jpg"},
    {"title":"What is Trump’s Gold Card: Eligibility, benefits, price & how to apply","source":{"name":"Times of India"},"url":"https://timesofindia.indiatimes.com/business/international-business/what-is-trumps-gold-card-eligibility-benefits-price-and-how-to-apply-faqs-answered/articleshow/125900980.cms","description":"A look at Trump‘s Gold Card scheme — who is eligible, what are the benefits, cost and application details.","category":"International / Finance","image":"/images/gold card.jpg"},
    {"title":"Jio Financial Services invests ₹230 cr in two JVs","source":{"name":"Inc42"},"url":"https://inc42.com/buzz/jio-financial-services-pumps-inr-230-cr-in-two-jvs/","description":"Jio Financial Services makes strategic investment of ₹230 crore across two new joint ventures.","category":"Fintech / Investment","image":"/images/jio investment.jpg"},
    {"title":"RBI floating-rate savings bonds explained: returns, eligibility and key rules","source":{"name":"LiveMint"},"url":"https://www.livemint.com/money/rbi-floating-rate-savings-bonds-explained-returns-eligibility-and-key-rules-11765355423116.html","description":"A breakdown of new floating-rate savings bonds issued by RBI — how they work, who should invest, and what to know.","category":"Savings / Bonds","image":"/images/bond.jpg"},
    {"title":"Nippon India Large-Cap Fund tops 5-year return chart — beats benchmark by 5 % CAGR","source":{"name":"Financial Express"},"url":"https://www.financialexpress.com/money/nippon-india-large-cap-fund-tops-5-year-return-chart-beats-benchmark-by-5-cagr-4072324/","description":"Large-cap mutual fund outperforms benchmark over 5 years, delivering strong returns for investors.","category":"Mutual Funds / Investments","image":"/images/Mutual fund.jpg"},
    {"title":"Crypto markets hold steady as investors await US Fed rate-cut guidance","source":{"name":"Business Standard"},"url":"https://www.business-standard.com/markets/cryptocurrency/crypto-markets-hold-steady-as-investors-await-us-fed-rate-cut-guidance-125121000499_1.html","description":"Cryptocurrency markets remain stable amid global rate-cut expectations and investor caution.","category":"Crypto / Markets","image":"/images/crypto.jpg"},
    {"title":"Market down: Where to invest — Large vs Mid vs Small-cap, says HDFC Securities CEO","source":{"name":"India Today"},"url":"https://www.indiatoday.in/business/market/story/market-down-where-to-invest-large-vs-mid-vs-small-cap-hdfc-securities-md-ceo-dheeraj-relli-2834222-2025-12-11","description":"In a down market, HDFC Securities CEO discusses pros and cons of investing in large-, mid- and small-cap funds.","category":"Markets / Equity","image":"/images/market analysis.jpg"},
    {"title":"Home-loan borrowers to save up to ₹9 lakh on a ₹50 lakh loan after rate cuts: Analysis","source":{"name":"Financial Express"},"url":"https://www.financialexpress.com/money/rbi-policy-home-loan-borrowers-save-rs-9-lakh-in-emis-on-rs-50-lakh-loan-after-rate-cuts-in-2025-4066553/","description":"Recent rate cuts by RBI could significantly reduce EMIs and overall cost for home-loan borrowers.","category":"Housing Loans / EMI","image":"/images/home loan.jpg"},
    {"title":"Rate cut by RBI slashes EMIs — good news for home-loan borrowers","source":{"name":"The Week"},"url":"https://www.theweek.in/news/biz-tech/2025/12/05/good-news-for-home-loan-borrowers-as-rbi-slashes-repo-rate-here-is-how-it-impacts-your-emi.html","description":"With RBI’s repo-rate reduction, home-loan EMIs may fall — making loans cheaper for borrowers.","category":"Housing Loans / EMI","image":"/images/emi reduction.jpg"}
]

# JSON endpoint
@app.route("/news")
def news_json():
    try:
        limit_param = request.args.get("limit")
        if limit_param is None:
            # No limit specified, return all items
            return jsonify(NEWS_SEED)
        else:
            limit = int(limit_param)
            limit = max(1, min(limit, len(NEWS_SEED)))
            return jsonify(NEWS_SEED[:limit])
    except:
        # If there's any error, return all items
        return jsonify(NEWS_SEED)

# Route to serve images from the images folder
@app.route('/images/<path:filename>')
def serve_image(filename):
    images_dir = os.path.join(BASE_DIR, 'images')
    if not os.path.exists(os.path.join(images_dir, filename)):
        abort(404)
    return send_from_directory(images_dir, filename)

# serve listing page
@app.route("/news.html")
def news_page():
    path = os.path.join(BASE_DIR, 'news.html')
    if not os.path.exists(path):
        abort(404)
    return send_from_directory('.', 'news.html')

# serve loan page
@app.route("/loan.html")
def loan_page():
    path = os.path.join(BASE_DIR, 'loan.html')
    if not os.path.exists(path):
        abort(404)
    return send_from_directory('.', 'loan.html')

# serve dashboard page
@app.route("/dashboard.html")
def dashboard_page():
    path = os.path.join(BASE_DIR, 'dashboard.html')
    if not os.path.exists(path):
        abort(404)
    return send_from_directory('.', 'dashboard.html')

# optional root -> redirect to dashboard.html (serve index if exists)
@app.route("/")
def index():
    p = os.path.join(BASE_DIR, 'index.html')
    if os.path.exists(p):
        return send_from_directory('.', 'index.html')
    # Redirect to dashboard if no index.html
    return send_from_directory('.', 'dashboard.html')

if __name__ == "__main__":
    # create DB if missing
    with app.app_context():
        init_db()
    # run
    app.run(debug=True, port=5000)