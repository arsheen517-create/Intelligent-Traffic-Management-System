# Intelligent Traffic Management System (ITMS)

An AI-powered Intelligent Traffic Management System that uses computer vision to dynamically manage traffic signals, optimize lane green-light times, and automatically route emergency vehicles (e.g., ambulances) through intersections.

## Features

- **Real-time Vehicle Detection**: Uses YOLOv8 to detect and count vehicles across 4 lanes from camera feeds.
- **Ambulance Detection & Priority Override**: Detects ambulances using a custom-trained YOLO model and automatically triggers green signals for the respective lane to allow clear passage.
- **Dynamic Traffic Light Logic**: Automatically adjusts green light durations based on vehicle density.
- **Role-Based Auth & Web Dashboards**: 
  - **Admin**: View all 4 camera streams, upload test videos, and check real-time traffic statistics.
  - **Ambulance User**: Request override or track status.
  - **Public Dashboard**: General interface displaying current traffic status.
- **WebSockets**: Leverages `Flask-SocketIO` to stream traffic metrics and updates to the web interface in real time without page refreshes.

---

## Project Structure

```
Code/
├── routes/             # Role-based route blueprints (admin, auth, ambulance, public)
├── static/             # Static files (CSS, JS, images, icons)
├── templates/          # HTML pages/templates
├── uploads/            # Temporary directory for video uploads
├── videos/             # Processed/saved videos
├── app.py              # Main Flask-SocketIO server entry point
├── database.py         # SQLite database setup and user accounts management
├── detector.py         # YOLOv8 vehicle & ambulance detection engine
├── socket_events.py    # WebSocket communication handlers
├── traffic_logic.py    # Core density-based traffic signal control algorithms
├── best.pt             # Trained YOLO model weights for ambulance detection
├── yolov8n.pt          # Pre-trained YOLOv8 nano weights for vehicle detection
├── requirements.txt    # Python dependencies list
└── .gitignore          # Rules for files excluded from Git tracking
```

---

## Installation & Setup

### Prerequisites
- Python 3.10 or higher
- [Git](https://git-scm.com/) (to clone/upload)

### Step-by-Step Guide

1. **Clone the Repository:**
   ```bash
   git clone <your-repository-url>
   cd <repository-directory>
   ```

2. **Create a Virtual Environment:**
   It is recommended to run the project in a virtual environment:
   ```bash
   python -m venv venv
   ```

3. **Activate the Virtual Environment:**
   - **Windows:**
     ```bash
     venv\Scripts\activate
     ```
   - **macOS/Linux:**
     ```bash
     source venv/bin/activate
     ```

4. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the Application:**
   ```bash
   python app.py
   ```
   Open `http://localhost:5000` in your web browser.

---

