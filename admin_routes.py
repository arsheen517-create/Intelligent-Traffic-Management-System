"""
routes/admin_routes.py
----------------------
All admin-only routes.
Preserves access to the existing video dashboard and analysis pages.
Adds user management, ambulance management, live map, and signal monitor.
"""

from flask import (Blueprint, render_template, request,
                   redirect, url_for, session, flash, jsonify, Response)
from functools import wraps
from database import get_db, hash_password

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ── Auth guard ────────────────────────────────────────────────────────────────

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('auth.login'))
        return fn(*args, **kwargs)
    return wrapper


# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route('/')
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Main admin dashboard – shows AI traffic feed + live stats."""
    return render_template('admin_dashboard.html',
                           tab='dashboard',
                           username=session.get('full_name', 'Admin'))


# ── Signal Monitor ────────────────────────────────────────────────────────────

@admin_bp.route('/signal_monitor')
@admin_required
def signal_monitor():
    return render_template('signal_monitor.html')


# ── Live Map ─────────────────────────────────────────────────────────────────

@admin_bp.route('/live_map')
@admin_required
def live_map():
    return render_template('live_map.html', role='admin')


# ── User Management ───────────────────────────────────────────────────────────

@admin_bp.route('/users')
@admin_required
def users():
    db  = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, username, full_name, email, phone, vehicle_number, vehicle_type, role, created_at FROM users ORDER BY id DESC")
    all_users = cur.fetchall()
    db.close()
    return render_template('admin_dashboard.html',
                           tab='users',
                           users=all_users,
                           username=session.get('full_name', 'Admin'))


@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM users WHERE id=? AND role != 'admin'", (user_id,))
    db.commit()
    db.close()
    flash('User deleted.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/add', methods=['POST'])
@admin_required
def add_user():
    data = request.form
    db   = get_db()
    cur  = db.cursor()
    try:
        username = data.get('email', '').split('@')[0] or data.get('full_name', 'user').replace(' ', '_').lower()
        cur.execute('''
            INSERT INTO users (username, password, role, full_name, phone, email, vehicle_number, vehicle_type)
            VALUES (?,?,?,?,?,?,?,?)
        ''', (username, hash_password(data.get('password', 'changeme')),
              data.get('role', 'public'), data.get('full_name', ''),
              data.get('phone', ''), data.get('email', ''),
              data.get('vehicle_number', '').upper(), data.get('vehicle_type', '')))
        db.commit()
        flash('User added.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'danger')
    finally:
        db.close()
    return redirect(url_for('admin.users'))


# ── Ambulance Management ──────────────────────────────────────────────────────

@admin_bp.route('/ambulances')
@admin_required
def ambulances():
    db  = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM ambulance_drivers ORDER BY id DESC")
    drivers = cur.fetchall()
    # Active routes
    cur.execute('''
        SELECT lr.*, ad.driver_name, ad.ambulance_number
        FROM live_routes lr
        JOIN ambulance_drivers ad ON lr.driver_id = ad.id
        WHERE lr.is_active = 1
    ''')
    active_routes = cur.fetchall()
    db.close()
    return render_template('admin_dashboard.html',
                           tab='ambulances',
                           ambulances=drivers,
                           active_routes=active_routes,
                           username=session.get('full_name', 'Admin'))


@admin_bp.route('/ambulances/delete/<int:driver_id>', methods=['POST'])
@admin_required
def delete_ambulance(driver_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM ambulance_drivers WHERE id=?", (driver_id,))
    db.commit()
    db.close()
    flash('Ambulance driver removed.', 'success')
    return redirect(url_for('admin.ambulances'))


@admin_bp.route('/ambulances/toggle/<int:driver_id>', methods=['POST'])
@admin_required
def toggle_ambulance(driver_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute(
        "UPDATE ambulance_drivers SET is_active = 1 - is_active WHERE id=?",
        (driver_id,)
    )
    db.commit()
    db.close()
    flash('Ambulance driver status updated.', 'success')
    return redirect(url_for('admin.ambulances'))


# ── API: live stats for admin dashboard cards ─────────────────────────────────

@admin_bp.route('/api/stats')
@admin_required
def api_stats():
    db  = get_db()
    cur = db.cursor()

    cur.execute("SELECT COUNT(*) FROM users WHERE role='public'")
    public_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM ambulance_drivers WHERE is_active=1")
    amb_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM live_routes WHERE is_active=1")
    active_routes = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM detections WHERE is_ambulance=1 AND detected_at > datetime('now','-1 hour')")
    recent_alerts = cur.fetchone()[0]

    db.close()
    return jsonify({
        'public_users':    public_count,
        'ambulances':      amb_count,
        'active_routes':   active_routes,
        'recent_amb_alerts': recent_alerts,
    })


# ── Backwards-compat: legacy routes redirected to admin ──────────────────────

@admin_bp.route('/upload', methods=['GET', 'POST'])
@admin_required
def upload():
    """Delegate to the global upload_page defined in app.py."""
    from flask import current_app
    return redirect(url_for('upload_page'))


@admin_bp.route('/legacy_dashboard')
@admin_required
def legacy_dashboard():
    return redirect(url_for('dashboard'))
