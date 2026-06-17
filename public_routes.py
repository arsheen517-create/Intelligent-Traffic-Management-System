"""
routes/public_routes.py
-----------------------
Routes for registered public users (vehicle owners / drivers).
"""

from flask import (Blueprint, render_template, session,
                   redirect, url_for, flash, jsonify)
from functools import wraps
from database import get_db

public_bp = Blueprint('public', __name__, url_prefix='/public')


def public_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in.', 'warning')
            return redirect(url_for('auth.login'))
        if session.get('role') not in ('public', 'admin'):
            return redirect(url_for('auth.login'))
        return fn(*args, **kwargs)
    return wrapper


@public_bp.route('/')
@public_bp.route('/dashboard')
@public_required
def dashboard():
    return render_template('public_dashboard.html',
                           full_name=session.get('full_name', 'User'))


@public_bp.route('/live_map')
@public_required
def live_map():
    return render_template('live_map.html', role='public')


@public_bp.route('/api/congestion')
@public_required
def api_congestion():
    """Returns simplified traffic state for the public map."""
    from app import traffic_manager   # imported at call time to avoid circular import
    state = traffic_manager.get_system_state()
    return jsonify(state)
