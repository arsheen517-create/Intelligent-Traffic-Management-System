"""
database.py
ADVANCED ITMS DATABASE SYSTEM
"""

import sqlite3
import hashlib

DATABASE = 'users.db'


# ─────────────────────────────────────────
# DATABASE CONNECTION
# ─────────────────────────────────────────

def get_db():

    conn = sqlite3.connect(
        DATABASE
    )

    conn.row_factory = sqlite3.Row

    return conn


# ─────────────────────────────────────────
# PASSWORD HASH
# ─────────────────────────────────────────

def hash_password(password: str):

    return hashlib.sha256(
        password.encode()
    ).hexdigest()


# ─────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────

def setup_database():

    conn = get_db()

    cur = conn.cursor()

    # ─────────────────────────────────────
    # USERS
    # ─────────────────────────────────────

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL,

            role TEXT DEFAULT 'public',

            full_name TEXT,

            phone TEXT,

            email TEXT UNIQUE,

            vehicle_number TEXT,

            vehicle_type TEXT,

            created_at DATETIME
            DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Safe migration
    _add_column_if_missing(
        cur,
        'users',
        'role',
        "TEXT DEFAULT 'public'"
    )

    _add_column_if_missing(
        cur,
        'users',
        'full_name',
        'TEXT'
    )

    _add_column_if_missing(
        cur,
        'users',
        'phone',
        'TEXT'
    )

    _add_column_if_missing(
        cur,
        'users',
        'email',
        'TEXT'
    )

    _add_column_if_missing(
        cur,
        'users',
        'vehicle_number',
        'TEXT'
    )

    _add_column_if_missing(
        cur,
        'users',
        'vehicle_type',
        'TEXT'
    )

    _add_column_if_missing(
        cur,
        'users',
        'created_at',
        'DATETIME DEFAULT CURRENT_TIMESTAMP'
    )

    # ─────────────────────────────────────
    # DEFAULT ADMIN
    # ─────────────────────────────────────

    cur.execute(

        """
        SELECT id

        FROM users

        WHERE username='traffic-admin'
        """
    )

    if cur.fetchone() is None:

        cur.execute(

            """
            INSERT INTO users (

                username,
                password,
                role,
                full_name

            )

            VALUES (?,?,?,?)
            """,

            (

                'traffic-admin',

                hash_password(
                    'adminpassword'
                ),

                'admin',

                'System Administrator'
            )
        )

        print(
            "[DB] Default admin created"
        )

    else:

        cur.execute(

            """
            UPDATE users

            SET role='admin'

            WHERE username='traffic-admin'
            """
        )

    # ─────────────────────────────────────
    # AMBULANCE DRIVERS
    # ─────────────────────────────────────

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ambulance_drivers (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            driver_name TEXT NOT NULL,

            ambulance_number TEXT UNIQUE NOT NULL,

            hospital_name TEXT,

            phone TEXT UNIQUE,

            password TEXT NOT NULL,

            is_active INTEGER DEFAULT 1,

            created_at DATETIME
            DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # ─────────────────────────────────────
    # VEHICLE DETAILS
    # ─────────────────────────────────────

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vehicle_details (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER,

            vehicle_number TEXT UNIQUE,

            vehicle_type TEXT,

            owner_name TEXT,

            registered_at DATETIME
            DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # ─────────────────────────────────────
    # LIVE ROUTES
    # ─────────────────────────────────────

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS live_routes (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            driver_id INTEGER,

            source TEXT,

            destination TEXT,

            source_lat REAL,
            source_lng REAL,

            destination_lat REAL,
            destination_lng REAL,

            lat REAL,
            lng REAL,

            route_geometry TEXT,

            eta_minutes INTEGER,

            distance_remaining REAL,

            is_active INTEGER DEFAULT 1,

            started_at DATETIME
            DEFAULT CURRENT_TIMESTAMP,

            updated_at DATETIME
            DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Migration-safe additions
    _add_column_if_missing(
        cur,
        'live_routes',
        'source_lat',
        'REAL'
    )

    _add_column_if_missing(
        cur,
        'live_routes',
        'source_lng',
        'REAL'
    )

    _add_column_if_missing(
        cur,
        'live_routes',
        'destination_lat',
        'REAL'
    )

    _add_column_if_missing(
        cur,
        'live_routes',
        'destination_lng',
        'REAL'
    )

    _add_column_if_missing(
        cur,
        'live_routes',
        'route_geometry',
        'TEXT'
    )

    _add_column_if_missing(
        cur,
        'live_routes',
        'eta_minutes',
        'INTEGER'
    )

    _add_column_if_missing(
        cur,
        'live_routes',
        'distance_remaining',
        'REAL'
    )

    # ─────────────────────────────────────
    # SIGNAL HISTORY
    # ─────────────────────────────────────

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS signal_status (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lane_id INTEGER,

            status TEXT,

            reason TEXT,

            recorded_at DATETIME
            DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # ─────────────────────────────────────
    # DETECTIONS
    # ─────────────────────────────────────

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS detections (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lane_id INTEGER,

            vehicle_type TEXT,

            confidence REAL,

            is_ambulance INTEGER DEFAULT 0,

            detected_at DATETIME
            DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # ─────────────────────────────────────
    # GREEN CORRIDOR EVENTS
    # ─────────────────────────────────────

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS green_corridor_events (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lane_id INTEGER,

            ambulance_id INTEGER,

            activated_at DATETIME
            DEFAULT CURRENT_TIMESTAMP,

            cleared_at DATETIME
        )
        """
    )

    # ─────────────────────────────────────
    # SYSTEM LOGS
    # ─────────────────────────────────────

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS system_logs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            event_type TEXT,

            message TEXT,

            created_at DATETIME
            DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()

    conn.close()

    print(
        "[DB] Advanced ITMS database ready."
    )


# ─────────────────────────────────────────
# SAFE COLUMN MIGRATION
# ─────────────────────────────────────────

def _add_column_if_missing(

    cur,
    table,
    column,
    definition
):

    try:

        cur.execute(

            f'''
            ALTER TABLE {table}

            ADD COLUMN {column}
            {definition}
            '''
        )

    except Exception:

        pass