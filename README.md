# PRISM — GitHub Engineering Intelligence Platform

PRISM is a comprehensive analytics platform designed to ingest, process, and visualize GitHub repository data. It provides 9 distinct intelligence modules covering Pull Requests, Issues, Branches, CI/CD Workflows, Discussions, Projects, and AI/ML predictive analytics (e.g., PR merge delay prediction, bottleneck detection).

## 🏗️ Architecture

- **Frontend**: Next.js (React), Tailwind CSS, Recharts, Lucide React
- **Backend**: FastAPI, SQLAlchemy (asyncmy), Scikit-Learn (ML)
- **Database**: MySQL 8.0+
- **Background Tasks**: Celery with Redis broker

---

## 🚀 Getting Started

Follow these steps to set up and run the PRISM platform locally.

### Prerequisites

Make sure you have the following installed on your machine:
- **Python 3.9+**
- **Node.js 18+**
- **MySQL Server** (running locally on port 3306)
- **Redis Server** (running locally on port 6379)

---

### 1. Database Setup

Ensure your MySQL server is running. By default, the application expects a local MySQL instance with a `root` user and password `Msk@2806`.

Navigate to the backend directory and run the database setup script. This script will automatically create a dedicated database `github_analytics` and a restricted user `prism_app`.

```bash
cd backend
python setup_db.py
```

### 2. Backend Setup (FastAPI)

Open a new terminal and navigate to the backend directory:

```bash
cd backend
```

**Create and activate a virtual environment:**

*On Windows:*
```bash
python -m venv venv
.\venv\Scripts\activate
```
*On macOS/Linux:*
```bash
python3 -m venv venv
source venv/bin/activate
```

**Install Python dependencies:**
```bash
pip install -r requirements.txt
```

**Configure Environment Variables:**
Open the `backend/.env` file and insert your GitHub Personal Access Token (PAT). This is required to fetch repository data.
```env
GITHUB_TOKEN=your_github_pat_here
```
*(Note: All other variables, like database credentials and JWT secrets, have already been securely populated for local development).*

**Run the Backend Server:**
```bash
python main.py
```
*The API will be available at `http://127.0.0.1:8000`.*

---

### 3. Background Worker Setup (Celery)

PRISM uses Celery to handle long-running GitHub API syncs asynchronously so the web UI remains fast.

Open a **new terminal**, navigate to the `backend` directory, activate your virtual environment again, and run:

*On Windows (requires the `gevent` or `solo` pool for Celery):*
```bash
celery -A celery_app worker --loglevel=info --pool=solo
```
*On macOS/Linux:*
```bash
celery -A celery_app worker --loglevel=info --concurrency=2
```

---

### 4. Frontend Setup (Next.js)

Open a **new terminal** and navigate to the frontend directory:

```bash
cd frontend
```

**Install Node dependencies:**
```bash
npm install
```

**Run the Next.js Development Server:**
```bash
npm run dev
```

*The frontend application will be available at `http://localhost:3000`.*

---

## 🎯 Usage

1. Open `http://localhost:3000` in your browser.
2. Sign up for a new account (or log in if you already have one).
3. From the dashboard, enter a GitHub repository URL (e.g., `https://github.com/facebook/react`) and click **Add Repository**.
4. The backend Celery worker will begin ingesting data. You will see live progress in the UI.
5. Once the sync is complete, navigate through the 9 intelligence modules on the sidebar to view deep analytics, developer segments, and AI predictions!

---

## 🔐 Security Note
The application has been hardened for production. It uses `HttpOnly` cookies for JWT storage, bcrypt password hashing, parameterized SQL queries to prevent SQL injection, and a dynamic Content-Security-Policy. 

**Never commit your `.env` file containing your `GITHUB_TOKEN` to source control.**
