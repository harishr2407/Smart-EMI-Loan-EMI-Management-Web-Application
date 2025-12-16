# Smart EMI – Loan & EMI Management Web Application

<p align="center">
  <img src="images/logo.png" alt="Smart EMI Logo" width="200">
</p>

<p align="center">
  <strong>Your Personal Loan EMI Calculator & Management Solution</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#tech-stack">Tech Stack</a> •
  <a href="#installation">Installation</a> •
  <a href="#api-endpoints">API</a> •
  <a href="#author">Author</a>
</p>

---

## 📋 Overview

Smart EMI is a comprehensive Flask-based web application designed for efficient loan and EMI management. It offers robust user authentication with OTP verification via email, secure session handling, password management, and an integrated financial news module. The application also serves interactive HTML dashboards and loan calculation tools.

### ✨ Key Highlights

- 🔐 **Secure Authentication** - OTP verification via Gmail SMTP
- 💰 **EMI Calculation** - Advanced loan calculation engine
- 📊 **Data Visualization** - Interactive charts and graphs
- 📤 **Export Capabilities** - PDF, Excel/CSV, and Email exports
- 📱 **Responsive Design** - Works on all device sizes
- 📰 **Financial News** - Curated financial updates

---

## 🚀 Features

### 🔐 Authentication System

* User registration with **email OTP verification**
* Secure login & logout functionality
* Session-based authentication with security measures
* User profile management APIs
* Strong password update policies with validation

### 📨 OTP Management

* 6-digit secure OTP generation
* SQLite storage with automatic 5-minute expiry
* Delivery via **Gmail SMTP** for real-time notifications
* Single-use OTP tokens for enhanced security

### 📰 Financial News Hub

* Preloaded curated financial news content (JSON format)
* `/news` API endpoint with optional limit parameter
* Image assets served from dedicated `/images` directory
* Dedicated news listing page (`news.html`) for browsing

### 🖥️ Frontend Pages

* `index.html` - Main landing page
* `dashboard.html` - Interactive EMI calculator dashboard
* `loan.html` - Loan information and tools
* `news.html` - Financial news browsing interface

---

## ⚙️ Tech Stack

### Backend
* **Framework**: Flask (Python)
* **Database**: SQLite
* **Authentication**: Session-based with OTP
* **Email Service**: Gmail SMTP Integration
* **Security**: Password hashing with Werkzeug

### Frontend
* **Languages**: HTML5, CSS3, JavaScript
* **Libraries**: Chart.js for data visualization
* **Styling**: Custom responsive CSS framework

### Development Tools
* **Environment Management**: python-dotenv
* **Cross-Origin Support**: Flask-CORS
* **Web Scraping**: Beautiful Soup 4
* **HTTP Requests**: requests library

---

## 📁 Project Structure

```
smart-emi/
├── app.py                 # Main Flask application
├── app.db                 # SQLite database
├── .env                   # Environment variables
├── requirements.txt       # Python dependencies
├── index.html             # Landing page
├── dashboard.html         # EMI calculator dashboard
├── loan.html              # Loan information page
├── news.html              # News browsing page
├── images/                # Image assets directory
│   ├── *.jpg             # News article images
│   └── *.png             # UI graphics
└── README.md             # Project documentation
```

---

## 🛠️ Installation

### 1. Clone Repository & Install Dependencies

```bash
git clone <repository-url>
cd smart-emi
pip install -r requirements.txt
```

Or install packages manually:

```bash
pip install flask flask-cors python-dotenv requests beautifulsoup4
```

### 2. Environment Configuration (.env)

```env
FLASK_SECRET=your_secure_secret_key
GMAIL_USER=your_email@gmail.com
GMAIL_APP_PASSWORD=your_gmail_app_password
```

> ⚠️ **Important**: Use a **Gmail App Password** instead of your regular Gmail password for enhanced security.

---

## ▶️ Run the Application

```bash
python app.py
```

The application will be accessible at:

```
http://localhost:5000
```

---

## 🌐 API Endpoints

### 🔐 Authentication Endpoints

| Endpoint | Method | Description |
|---------|--------|-------------|
| `/send-otp` | POST | Generate and send OTP to email |
| `/verify-otp` | POST | Validate provided OTP |
| `/create-account` | POST | Register new user account |
| `/login` | POST | Authenticate user login |
| `/logout` | POST | Terminate user session |
| `/profile` | GET | Retrieve logged-in user details |
| `/update-password` | POST | Modify user password |

### 📰 News Endpoints

| Endpoint | Method | Description |
|---------|--------|-------------|
| `/news` | GET | Fetch all financial news |
| `/news?limit=4` | GET | Fetch limited news articles |

---

## 🗄️ Database Schema

### Users Table

* `id` - Unique identifier
* `name` - User's full name
* `email` - Email address (unique)
* `password_hash` - Securely hashed password
* `location` - User's location
* `phone` - Contact number
* `role` - User role (default: "User")
* `created_at` - Account creation timestamp

### OTPs Table

* `email` - Associated email address
* `otp` - Generated OTP code
* `expires_at` - Expiration timestamp
* `used` - Usage status flag
* `created_at` - Record creation timestamp

---

## 🔒 Security Guidelines

* 🔐 All passwords are securely **hashed** using industry standards
* ⏰ OTP tokens automatically expire after 5 minutes
* 🍪 Session cookies are HTTPOnly for XSS protection
* 🌐 CORS is enabled for development convenience
* 🛡️ Input validation on all user-submitted data

---

## 📝 Development Notes

* ✉️ Email OTP functionality requires proper SMTP configuration
* 🖼️ Images must be placed in the `/images` folder for proper display
* 📱 Dashboard is fully responsive and mobile-friendly
* 📈 EMI calculations use advanced financial algorithms
* 🎨 UI follows modern design principles with dark theme

---

## 👨‍💻 Author

**Harish R**  
Information Science & Engineering  
Smart EMI Project 🚀

📧 Email: hr636298@gmail.com  
📍 Location: India  

---

<p align="center">
  Built with ❤️ using Flask & Python
</p>