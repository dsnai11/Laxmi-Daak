# AWS Deployment Guide for Courier Tracking System

This guide outlines the steps to deploy the Courier Tracking application to **AWS Elastic Beanstalk** (recommended) or **AWS EC2**.

---

## Method 1: Deploying to AWS Elastic Beanstalk (Recommended)

Elastic Beanstalk is the easiest way to deploy and scale this Flask application.

### Step 1: Prepare the Zip Bundle
AWS Elastic Beanstalk deploys application versions via a ZIP archive.
Compress all project files into a ZIP archive, making sure **`application.py`** and **`requirements.txt`** are at the root level of the ZIP.

### Step 2: Create an Elastic Beanstalk Application
1. Open the **AWS Elastic Beanstalk Console**.
2. Click **Create Application**.
3. Configure the following options:
   - **Application Name**: `Courier-Tracking`
   - **Platform**: `Python`
   - **Platform Branch**: `Python 3.11` (or `Python 3.9` depending on your version)
4. Under **Application Code**, select **Upload your code** and upload the ZIP bundle you created in Step 1.
5. Click **Configure more options**.

### Step 3: Configure Environment Properties (Secrets)
Instead of uploading a `.env` file, configure your secrets securely via the AWS console:
1. Go to **Configuration** -> **Updates, monitoring, and logging** (Software).
2. Add the following **Environment properties**:
   - `FLASK_SECRET_KEY`: A cryptographically strong random key.
   - `COMPANY_NAME`: `Laxmi India Finance Ltd.`
   - `BASE_URL`: The domain name of your hosted site (e.g., `https://courier.lifc.in`).
   - `DATABASE_URL`: Set this to your persistent RDS database URL (see below).

### Step 4: Persistent Database (AWS RDS)
*Since Elastic Beanstalk EC2 instances are ephemeral, using SQLite locally will cause data loss whenever the server restarts or scales.*
1. Create an **AWS RDS PostgreSQL** or **MySQL** instance.
2. In the RDS Security Group, allow inbound access from your Elastic Beanstalk Security Group on the database port.
3. Configure the `DATABASE_URL` property in Elastic Beanstalk:
   - For PostgreSQL: `postgresql://username:password@rds-endpoint:5432/dbname`
   - For MySQL: `mysql+pymysql://username:password@rds-endpoint:3306/dbname`
4. The application will automatically initialize the database schema on startup!

---

## Method 2: Deploying to AWS EC2 (Manual Setup)

If you prefer full control, you can host on an EC2 instance (Ubuntu Server recommended).

### Step 1: Launch EC2 Instance & Install Dependencies
1. Launch an **Ubuntu Server** EC2 instance.
2. Connect via SSH and install dependencies:
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-venv git -y
   ```

### Step 2: Clone & Setup Project
1. Clone your project code onto the server:
   ```bash
   git clone <your-repository-url>
   cd courier_tracker
   ```
2. Create a virtual environment and install requirements:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

### Step 3: Configure Environment Variables
Create a `.env` file at the root of the project and populate it with your production configurations.

### Step 4: Run with Gunicorn & Eventlet (Production Server)
For WebSockets (Socket.IO) to function correctly in production, run Gunicorn using the Eventlet worker:
```bash
gunicorn --worker-class eventlet -w 1 -b 0.0.0.0:8000 application:application
```

### Step 5: Configure Nginx Reverse Proxy
To serve the app on port 80 (HTTP) or 443 (HTTPS), set up Nginx as a reverse proxy forwarding to `http://127.0.0.1:8000`.
Ensure WebSockets configuration headers are set in Nginx:
```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

location /socket.io {
    proxy_pass http://127.0.0.1:8000/socket.io;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "Upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```
