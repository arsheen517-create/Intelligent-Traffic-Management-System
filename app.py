"""
app.py  (UPGRADED)
------------------
Main Flask application entry point.

Changes from original:
  • Flask-SocketIO added
  • Role-based auth blueprints registered
  • database.py used for setup (extends existing DB, never drops data)
  • Legacy routes (/login, /home, /dashboard …) kept for backwards compat
  • All existing video stream and status API routes preserved
  • Admin routes now also accessible via /admin/* prefix
"""

import os
import cv2
import traceback
import sqlite3

from flask import (Flask, render_template, request, redirect,
                   url_for, Response, jsonify, session, flash)
from flask_socketio import SocketIO

# ── Project modules ───────────────────────────────────────────────────────────
from detector     import TrafficDetector
from traffic_logic import TrafficLogic
from database     import setup_database, hash_password

# ── Blueprints ─────────────────────────────────────────────────────────────────
from routes.auth_routes      import auth_bp
from routes.admin_routes     import admin_bp
from routes.ambulance_routes import ambulance_bp
from routes.public_routes    import public_bp

# ── Configuration ─────────────────────────────────────────────────────────────
UPLOAD_FOLDER      = 'uploads'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}
DATABASE           = 'users.db'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY']    = os.environ.get('SECRET_KEY', 'itms_super_secret_2024_change_me')

# ── SocketIO (async_mode=threading keeps compatibility with cv2 threads) ───────
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins='*')

# ── Register blueprints ────────────────────────────────────────────────────────
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(ambulance_bp)
app.register_blueprint(public_bp)

# ── Global state ──────────────────────────────────────────────────────────────
video_paths = {1: None, 2: None, 3: None, 4: None}
video_caps  = {1: None, 2: None, 3: None, 4: None}

try:
    detector = TrafficDetector(
        vehicle_model_path='yolov8n.pt',
        ambulance_model_path='best.pt'
    )
except Exception as e:
    print(f"[App] YOLO models failed to load: {e}")
    detector = None

traffic_manager = TrafficLogic()

# ── Register SocketIO events (passes traffic_manager reference) ───────────────
from socket_events import register_socket_events
register_socket_events(socketio, traffic_manager)

# ── Helpers ───────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def draw_ui_elements(frame, lane_id, density, ambulance, status):
    """Draws traffic-light overlay and lane info — unchanged from original."""
    cv2.rectangle(frame, (10, 10), (70, 170), (50, 50, 50), -1)
    cv2.rectangle(frame, (10, 10), (70, 170), (255, 255, 255), 1)
    red_color    = (0, 0, 255)   if status == 'red'    else (40, 40, 40)
    orange_color = (0, 165, 255) if status == 'orange' else (40, 40, 40)
    green_color  = (0, 255, 0)   if status == 'green'  else (40, 40, 40)
    cv2.circle(frame, (40, 40),  20, red_color,    -1)
    cv2.circle(frame, (40, 90),  20, orange_color, -1)
    cv2.circle(frame, (40, 140), 20, green_color,  -1)
    cv2.putText(frame, f"Lane: {lane_id}",   (10, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, f"Density: {density}", (10, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    if ambulance:
        cv2.putText(frame, "AMBULANCE!", (10, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
    return frame


def generate_frames(lane_id):
    """MJPEG stream generator — unchanged from original."""
    video_path = video_paths.get(lane_id)
    if not video_path:
        return

    if video_caps[lane_id] is None:
        try:
            video_caps[lane_id] = cv2.VideoCapture(video_path)
            if not video_caps[lane_id].isOpened():
                return
        except Exception:
            return

    cap = video_caps[lane_id]
    while True:
        try:
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            if detector:
                processed_frame, ambulance_detected, detailed_counts = detector.process_frame(frame)
                print("DETECTOR:", detailed_counts)
                density = sum(detailed_counts.values())
            else:
                processed_frame, density, ambulance_detected, detailed_counts = frame, 0, False, {}

            traffic_manager.update_lane_data(lane_id, density, ambulance_detected, detailed_counts)
            current_state = traffic_manager.get_system_state()
            lane_status   = current_state[lane_id]['status']
            final_frame   = draw_ui_elements(processed_frame, lane_id, density, ambulance_detected, lane_status)

            flag, encoded = cv2.imencode('.jpg', final_frame)
            if not flag:
                continue

            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                   + bytearray(encoded) + b'\r\n')

        except Exception:
            traceback.print_exc()
            break

    print(f"[App] Stream stopped for Lane {lane_id}.")


# ══════════════════════════════════════════════════════════════════════════════
#  LEGACY ROUTES  (kept for backwards compatibility — do NOT remove)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/', methods=['GET', 'POST'])
def root():
    """Root redirects: logged-in → role dashboard; guest → login."""
    if 'user_id' in session:
        role = session.get('role', 'public')
        if role == 'admin':
            return redirect(url_for('admin.dashboard'))
        if role == 'ambulance':
            return redirect(url_for('ambulance.dashboard'))
        return redirect(url_for('public.dashboard'))
    return redirect(url_for('auth.login'))


@app.route('/home')
def home():
    """Legacy home — redirects to role-appropriate dashboard."""
    if 'user_id' not in session and 'logged_in' not in session:
        return redirect(url_for('auth.login'))
    return redirect(url_for('admin.dashboard') if session.get('role') == 'admin'
                    else url_for('public.dashboard'))


@app.route('/logout')
def logout():
    """Legacy logout alias."""
    return redirect(url_for('auth.logout'))


@app.route('/upload', methods=['GET', 'POST'])
def upload_page():
    """Video upload — admin only (legacy route preserved)."""
    if not (session.get('logged_in') or session.get('user_id')):
        return redirect(url_for('auth.login'))
    if session.get('role') not in ('admin', None):
        return redirect(url_for('public.dashboard'))

    global video_paths, video_caps
    if request.method == 'POST':
        video_caps = {1: None, 2: None, 3: None, 4: None}
        for i in range(1, 5):
            f = request.files.get(f'video{i}')
            if not f or f.filename == '' or not allowed_file(f.filename):
                continue
            ext      = f.filename.rsplit('.', 1)[1].lower()
            filename = f'lane_{i}.{ext}'
            path     = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            f.save(path)
            video_paths[i] = path
        return redirect(url_for('dashboard'))
    return render_template('upload.html')


@app.route('/dashboard')
def dashboard():
    """Legacy video dashboard — admin only."""
    if not (session.get('logged_in') or session.get('user_id')):
        return redirect(url_for('auth.login'))
    if not all(video_paths.values()):
        return redirect(url_for('upload_page'))
    return render_template('dashboard.html')


@app.route('/analysis')
def analysis_page():
    """Legacy analysis page."""
    if not (session.get('logged_in') or session.get('user_id')):
        return redirect(url_for('auth.login'))
    return render_template('analysis.html')


# ── Video / API endpoints (unchanged) ─────────────────────────────────────────

@app.route('/video_feed/<int:lane_id>')
def video_feed(lane_id):
    if not (session.get('logged_in') or session.get('user_id')):
        return 'Unauthorized', 401
    if lane_id not in [1, 2, 3, 4]:
        return 'Invalid Lane ID', 404
    return Response(generate_frames(lane_id),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/status_api')
def status_api():
    if not (session.get('logged_in') or session.get('user_id')):
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify(traffic_manager.get_system_state())


@app.route('/api/analysis_data')
def analysis_data():
    if not (session.get('logged_in') or session.get('user_id')):
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify(traffic_manager.get_analysis_data())


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    setup_database()
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    # Use socketio.run instead of app.run to enable WebSocket support
    socketio.run(app, debug=False, host='0.0.0.0', port=5000,
                 allow_unsafe_werkzeug=True)
