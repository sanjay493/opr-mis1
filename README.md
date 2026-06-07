# SAIL MIS Report Generator & Ingestion Portal

This repository contains the Operation Monthly Informatics (OMI) Management Information System (MIS) portal for Steel Authority of India Limited (SAIL). It consists of a **Python FastAPI backend** for database storage and WeasyPrint-based PDF generation, and a **Next.js frontend** for report editing and excel data ingestion.

---

## Architecture Overview

1. **Frontend (Next.js)**: A React-based web interface built with Next.js for interactive report visualization, inline editing, and Excel sheet ingestion.
2. **Backend (FastAPI)**: A Python API server that interfaces with a local SQLite database and uses **WeasyPrint** to compile HTML templates into clean, print-ready A4 PDF reports.
3. **Database (SQLite)**: Store report configurations, techno-economic parameters, and actual/plan monthly production data.

---

## System Requirements

- **Node.js**: v18.x or v20.x (LTS recommended)
- **Python**: 3.9.x to 3.12.x
- **pip**: Python package installer

---

## 1. System-Specific Dependencies (Required for WeasyPrint PDF Generation)

WeasyPrint relies on external system libraries for graphics rendering (Cairo, Pango, GObject). Install them based on your OS:

### Linux (Ubuntu / Debian)
```bash
sudo apt-get update
sudo apt-get install -y build-essential python3-dev python3-pip python3-setuptools \
                       python3-wheel python3-cffi libcairo2 libpango-1.0-0 \
                       libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info
```

### Linux (Fedora / CentOS / RHEL)
```bash
sudo dnf install -y redhat-rpm-config python3-devel cairo-devel pango-devel \
                    gdk-pixbuf2-devel libffi-devel
```

### macOS
Ensure you have [Homebrew](https://brew.sh/) installed:
```bash
brew install pango cairo gdk-pixbuf libffi
```

### Windows
WeasyPrint requires GTK libraries on Windows:
1. Download the latest GTK3 installer for Windows from [GTK-for-Windows](https://github.com/tschoonj/GTK-for-Windows-installer/releases).
2. Add the GTK installation `bin` folder (e.g. `C:\Program Files\GTK3-Runtime\bin`) to your system environment variables `Path`.
3. Alternatively, you can install WeasyPrint and its dependencies using [MSYS2](https://www.msys2.org/) or [Conda](https://docs.conda.io/en/latest/).

---

## 2. Backend Setup & Run Instructions

Navigate to the `backend` directory:
```bash
cd backend
```

### Dependency Installation
We recommend setting up a Python virtual environment:

**On Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**On Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

*Note: Running the backend server will automatically initialize/migrate the SQLite database (`mis_reports.db`) if it doesn't already exist.*

### Running the Backend

#### A. Development Model (With auto-reload)
```bash
# On Linux/macOS
PORT=8082 uvicorn main:app --host 127.0.0.1 --port 8082 --reload

# On Windows (CMD)
set PORT=8082
uvicorn main:app --host 127.0.0.1 --port 8082 --reload

# On Windows (PowerShell)
$env:PORT="8082"
uvicorn main:app --host 127.0.0.1 --port 8082 --reload
```

#### B. Production Model
```bash
# On Linux/macOS
PORT=8082 uvicorn main:app --host 127.0.0.1 --port 8082

# On Windows (CMD)
set PORT=8082
uvicorn main:app --host 127.0.0.1 --port 8082

# On Windows (PowerShell)
$env:PORT="8082"
uvicorn main:app --host 127.0.0.1 --port 8082
```

### Dynamic Port Configuration (Backend)
- Pass a custom port in the environment variable `PORT` to change backend API port.
- Pass `FRONTEND_PORT` or `FRONTEND_ORIGIN` to configure CORS allowance for custom frontend addresses.
  - E.g., `PORT=9000 FRONTEND_PORT=4000 python main.py` or `PORT=9000 FRONTEND_ORIGIN=http://127.0.0.1:4000 python main.py`.

---

## 3. Frontend Setup & Run Instructions

Navigate to the `frontend` directory:
```bash
cd frontend
```

### Dependency Installation
```bash
npm install
```

### Configure Backend Connection Port

Create a `.env.local` file inside the `frontend` directory to point the UI to your backend API server:
```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8082
```
Change `8082` to whatever custom port your backend is listening on.

### Running the Frontend

#### A. Development Model (Fast Refresh)
```bash
# Start on default port 3000
npm run dev

# Start on a user-defined port (e.g., 4000)
# Linux/macOS
PORT=4000 npm run dev
# Windows (CMD)
set PORT=4000 && npm run dev
# Windows (PowerShell)
$env:PORT="4000"; npm run dev
```
Open [http://localhost:3000](http://localhost:3000) (or the custom port) in your browser.

#### B. Production Model (Optimized build & served)
First build the production bundle:
```bash
npm run build
```

Then start the production server:
```bash
# Start on default port 3000
npm run start

# Start on a user-defined port (e.g., 4000)
# Linux/macOS
PORT=4000 npm run start
# Windows (CMD)
set PORT=4000 && npm run start
# Windows (PowerShell)
$env:PORT="4000"; npm run start
```

---

## 4. Full Example: Running Frontend & Backend on Custom Ports

Let's say you want to run the **Backend on port 8090** and the **Frontend on port 3005**.

### Step 1: Start Backend on Port 8090 and allow Frontend on 3005
```bash
cd backend
# Activate virtual environment
source venv/bin/activate

# Start backend
PORT=8090 FRONTEND_PORT=3005 python main.py
```

### Step 2: Configure and Start Frontend on Port 3005
In a new terminal window:
```bash
cd frontend

# Set the backend URL configuration
echo "NEXT_PUBLIC_API_URL=http://127.0.0.1:8090" > .env.local

# Run the frontend on port 3005
PORT=3005 npm run dev
```
Now access the web portal at [http://localhost:3005](http://localhost:3005).
