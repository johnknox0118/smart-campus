# Smart Campus Management and Security System - Installation Guide

Follow these steps to set up and run the Smart Campus application locally on your system.

---

## Prerequisites

- **Python 3.8+** (Must be installed and added to the PATH)
- **Web Browser** (Chrome, Firefox, Edge, etc.)
- **Git** (Optional, for version control)

---

## 1. Backend Setup

### Step 1.1: Install Dependencies
Open your terminal (PowerShell, Command Prompt, or bash), navigate to the `backend` directory, and run the following command to install the required Python packages:

```bash
pip install -r backend/requirements.txt
```

### Step 1.2: Initialize and Seed the Database
We have provided an automated database setup and seeding script. Running this script will automatically create the SQLite database file (`database/campus.db`) and populate it with default test accounts (using secure Bcrypt password hashing).

Run the following command from the project root directory:

```bash
python backend/init_db.py
```

You should see an output indicating:
- Tables created successfully.
- Departments seeded.
- Classes seeded.
- Default users (admin, student, staff, driver, security) seeded.

---

## 2. Running the Application

### Step 2.1: Start the Backend Server
Run the Flask server from the project root directory:

```bash
python backend/app.py
```

The Flask server will start running on:
- URL: `http://localhost:5000` or `http://127.0.0.1:5000`
- Logs will be written to `logs/campus.log`

### Step 2.2: Launch the Frontend Web Portal
Since the frontend uses HTML/CSS/JavaScript and fetches data from the backend, it must be run from a local web server (to avoid CORS origin restrictions when reading local file paths directly in browsers).

Run Python's built-in light HTTP server from the `frontend/` directory:

1. Open a new terminal window.
2. Navigate to the `frontend/` folder.
3. Run:
   ```bash
   python -m http.server 8000
   ```
4. Open your web browser and navigate to: `http://localhost:8000`

---

## 3. Test Credentials

You can log in to the web portal using any of the following pre-seeded test accounts:

| Username | Password | Role | Features |
| :--- | :--- | :--- | :--- |
| **admin** | `admin123` | **Admin** | Full Admin panel, charts, active maps, user controls, leave approvals. |
| **student** | `student123` | **Student** | Live GPS simulator, leave request form, attendance calendar, emergency SOS. |
| **staff** | `staff123` | **Staff** | Student leave approval, attendance log, emergency SOS. |
| **driver** | `driver123` | **Driver** | Transit console, Route controls (Start/End trip), live coordinates upload. |
| **security** | `security123` | **Security** | Alerts logs feed, SOS distress monitor, resolutions control. |

---

## 4. Verification (Running Unit Tests)

To verify the integrity of the application code, authentication middleware, geofencing coordinates matching, and the cybersecurity anti-spoofing engine, you can run the pytest suite:

1. Open your terminal at the project root directory.
2. Run the tests using the python pytest module:
   ```bash
   python -m pytest backend/tests/
   ```

All 18 automated tests should pass successfully.
