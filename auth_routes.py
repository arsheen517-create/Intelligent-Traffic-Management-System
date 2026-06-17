"""
routes/auth_routes.py
---------------------
Handles authentication for all three roles:
  • Admin        – pre-seeded in DB, no public registration
  • Public User  – self-registers with vehicle info
  • Ambulance    – self-registers with hospital / ambulance info
"""

from flask import (Blueprint, render_template, request,
                   redirect, url_for, session, flash, jsonify)
from database import get_db, hash_password

auth_bp = Blueprint('auth', __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _login_required(roles=None):
    """Decorator factory: ensure user is logged in and has an allowed role."""
    from functools import wraps
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in first.', 'warning')
                return redirect(url_for('auth.login'))
            if roles and session.get('role') not in roles:
                flash('Access denied.', 'danger')
                return redirect(url_for('auth.login'))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ── Login ─────────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return _redirect_by_role(session['role'])

    if request.method == 'POST':
        role     = request.form.get('role', 'public')
        password = request.form.get('password', '')

        if role == 'ambulance':
            return _login_ambulance(request.form.get('identifier', ''), password)
        else:
            return _login_user(request.form.get('identifier', ''), password, role)

    return render_template('login.html')


def _login_user(identifier, password, expected_role):
    """Authenticate a normal user (admin or public)."""
    db  = get_db()
    cur = db.cursor()
    # Allow login by username OR email
    cur.execute(
        "SELECT * FROM users WHERE (username=? OR email=?) AND password=?",
        (identifier, identifier, hash_password(password))
    )
    user = cur.fetchone()
    db.close()

    if user and (expected_role == 'admin' and user['role'] == 'admin'
                 or expected_role != 'admin' and user['role'] != 'admin'):
        session.clear()
        session['user_id']   = user['id']
        session['username']  = user['username']
        session['full_name'] = user['full_name'] or user['username']
        session['role']      = user['role']
        session['logged_in'] = True     # keep old flag for legacy routes
        flash(f"Welcome, {session['full_name']}!", 'success')
        return _redirect_by_role(user['role'])

    flash('Invalid credentials. Please try again.', 'danger')
    return redirect(url_for('auth.login'))


def _login_ambulance(identifier, password):
    """Authenticate an ambulance driver (by phone or ambulance_number)."""
    db  = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT * FROM ambulance_drivers WHERE (phone=? OR ambulance_number=?) AND password=? AND is_active=1",
        (identifier, identifier, hash_password(password))
    )
    driver = cur.fetchone()
    db.close()

    if driver:
        session.clear()
        session['user_id']          = driver['id']
        session['username']         = driver['ambulance_number']
        session['full_name']        = driver['driver_name']
        session['role']             = 'ambulance'
        session['logged_in']        = True
        session['ambulance_number'] = driver['ambulance_number']
        session['hospital_name']    = driver['hospital_name']
        flash(f"Welcome, {driver['driver_name']}!", 'success')
        return redirect(url_for('ambulance.dashboard'))

    flash('Invalid ambulance credentials.', 'danger')
    return redirect(url_for('auth.login'))


def _redirect_by_role(role):
    if role == 'admin':
        return redirect(url_for('admin.dashboard'))
    if role == 'ambulance':
        return redirect(url_for('ambulance.dashboard'))
    return redirect(url_for('public.dashboard'))


# ── Register – Public User ────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form.get('role', 'public')
        if role == 'ambulance':
            return _register_ambulance()
        return _register_public()
    return render_template('register.html')


def _register_public():
    data = request.form
    required = ['full_name', 'phone', 'email', 'password',
                 'vehicle_number', 'vehicle_type']
    if not all(data.get(f) for f in required):
        flash('All fields are required.', 'danger')
        return redirect(url_for('auth.register'))

    db  = get_db()
    cur = db.cursor()
    # Check email / phone uniqueness
    cur.execute("SELECT id FROM users WHERE email=?", (data['email'],))
    if cur.fetchone():
        db.close()
        flash('Email already registered.', 'danger')
        return redirect(url_for('auth.register'))

    username = data['email'].split('@')[0]   # derive a username from email
    try:
        cur.execute('''
            INSERT INTO users
              (username, password, role, full_name, phone, email,
               vehicle_number, vehicle_type)
            VALUES (?,?,?,?,?,?,?,?)
        ''', (username, hash_password(data['password']), 'public',
              data['full_name'], data['phone'], data['email'],
              data['vehicle_number'].upper(), data['vehicle_type']))
        user_id = cur.lastrowid
        # Mirror into vehicle_details
        cur.execute('''
            INSERT OR IGNORE INTO vehicle_details
              (user_id, vehicle_number, vehicle_type, owner_name)
            VALUES (?,?,?,?)
        ''', (user_id, data['vehicle_number'].upper(),
              data['vehicle_type'], data['full_name']))
        db.commit()
        flash('Registration successful! Please log in.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Registration error: {e}', 'danger')
    finally:
        db.close()
    return redirect(url_for('auth.login'))


def _register_ambulance():
    data = request.form
    required = ['driver_name', 'ambulance_number',
                 'hospital_name', 'phone', 'password']
    if not all(data.get(f) for f in required):
        flash('All fields are required.', 'danger')
        return redirect(url_for('auth.register'))

    db  = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM ambulance_drivers WHERE phone=? OR ambulance_number=?",
                (data['phone'], data['ambulance_number'].upper()))
    if cur.fetchone():
        db.close()
        flash('Phone or ambulance number already registered.', 'danger')
        return redirect(url_for('auth.register'))

    try:
        cur.execute('''
            INSERT INTO ambulance_drivers
              (driver_name, ambulance_number, hospital_name, phone, password)
            VALUES (?,?,?,?,?)
        ''', (data['driver_name'], data['ambulance_number'].upper(),
              data['hospital_name'], data['phone'],
              hash_password(data['password'])))
        db.commit()
        flash('Ambulance registration successful! Please log in.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Registration error: {e}', 'danger')
    finally:
        db.close()
    return redirect(url_for('auth.login'))


# ── Logout ────────────────────────────────────────────────────────────────────

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
