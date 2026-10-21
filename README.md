# 🚚 Laxmi Daak — Courier Tracking System

A full-featured internal courier & parcel tracking web application built with **Flask**, designed for managing dispatches across branches and departments.

## ✨ Features

- 📦 **Parcel Dispatch & Tracking** — Create, track and manage parcels with real-time status updates
- 🏢 **Multi-Branch Support** — Manage deliveries across multiple branches
- 🏛️ **Department Queries** — Department employees can raise dispatch queries; admin picks up and dispatches
- 📊 **Dashboard** — Role-based dashboards for Superadmin, Manager, and Employees
- 🔐 **Role-Based Access Control** — Superadmin, Manager, Branch Employee, Department Employee
- ⏰ **Overdue Alerts** — Automatic overdue detection and email notifications
- 📁 **Archive** — Delivered parcels archived with full history
- 🖨️ **Label Printing** — QR code based parcel labels
- 📷 **Photo Upload** — Attach delivery proof photos
- 📧 **Email Notifications** — Automated emails for dispatch, delivery, overdue alerts
- 🔍 **QR Scanner** — Scan parcels for quick status lookup
- 🔒 **Security Logs** — Full audit trail of all admin actions
- 📥 **Bulk Dispatch** — Upload multiple parcels via Excel

## 🛠️ Tech Stack

- **Backend:** Python / Flask
- **Database:** SQLite (via SQLAlchemy)
- **Frontend:** HTML, CSS (custom dark/light theme), JavaScript
- **Email:** SMTP (Gmail/custom)
- **Deployment:** AWS EC2

## 🚀 Quick Setup

```bash
# 1. Clone the repo
git clone https://github.com/dsnai11/Laxmi-Daak.git
cd Laxmi-Daak

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your settings

# 5. Run the app
python run.py
```

## ⚙️ Environment Variables

Copy `.env.example` to `.env` and fill in:

```
FLASK_SECRET_KEY=your_secret_key   # required: without it a temporary random key is used
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
BASE_URL=http://localhost:5000
COMPANY_NAME=Laxmi Daak
```

## 📁 Project Structure

```
courier_tracker/
├── app/
│   ├── models/          # Database models
│   ├── routes/          # Flask blueprints (admin, dispatch, auth)
│   ├── templates/       # Jinja2 HTML templates
│   ├── static/          # CSS, JS, images
│   └── services/        # Email & other services
├── requirements.txt
├── run.py
└── .env.example
```

## 📄 License

Private — All rights reserved © Laxmi Daak
