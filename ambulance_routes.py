"""
routes/ambulance_routes.py
ADVANCED LIVE AMBULANCE ROUTING SYSTEM
"""

from flask import (
    Blueprint,
    render_template,
    request,
    session,
    redirect,
    url_for,
    flash,
    jsonify
)

from functools import wraps

from database import get_db

import requests
import json
import math
import time
import os

ambulance_bp = Blueprint(
    'ambulance',
    __name__,
    url_prefix='/ambulance'
)


def _float_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


KNOWN_HOSPITAL_COORDS = {
    'government medical college jammu': (32.7359, 74.8538),
    'smgs hospital': (32.7355, 74.8575),
    'aiims vijaypur': (32.5886, 75.0206),
    'fortis hospital jammu': (32.7048, 74.8630),
    'ascoms hospital': (32.6890, 74.8370),
    'bee enn hospital': (32.7305, 74.8640),
    'sub district hospital akhnoor': (32.8670, 74.7350),
    'narayana hospital': (32.9910, 74.9310),
    'narayana hospital katra': (32.9910, 74.9310),
}


def _known_hospital_coords(name):
    key = (name or '').strip().lower()
    return KNOWN_HOSPITAL_COORDS.get(key, (None, None))


SIGNAL_LOCATIONS = {
    1: {'lat': 32.722156, 'lng': 74.857295},
    2: {'lat': 32.717817, 'lng': 74.859390},
    3: {'lat': 32.74003, 'lng': 74.83403},
    4: {'lat': 32.73328, 'lng': 74.83991},
}

SIGNAL_GREEN_RADIUS_METERS = 350


def _distance_meters(lat1, lng1, lat2, lng2):
    radius = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(delta_lambda / 2) ** 2
    )

    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _nearest_signal_lane(lat, lng):
    nearest_lane = None
    nearest_distance = float('inf')

    for lane_id, point in SIGNAL_LOCATIONS.items():
        distance = _distance_meters(
            lat,
            lng,
            point['lat'],
            point['lng']
        )

        if distance < nearest_distance:
            nearest_lane = lane_id
            nearest_distance = distance

    if nearest_distance <= SIGNAL_GREEN_RADIUS_METERS:
        return nearest_lane, nearest_distance

    return None, nearest_distance


def _activate_signal_if_ambulance_nearby(lat, lng):
    lane_id, distance = _nearest_signal_lane(lat, lng)

    if lane_id is None:
        return None, distance

    from app import traffic_manager

    traffic_manager.activate_green_corridor(lane_id)

    return lane_id, distance


def _google_waypoint(lat, lng):
    return {
        'location': {
            'latLng': {
                'latitude': lat,
                'longitude': lng
            }
        }
    }

# ─────────────────────────────────────────
# AUTH GUARD
# ─────────────────────────────────────────

def ambulance_required(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

        if session.get('role') != 'ambulance':

            flash(
                'Ambulance driver access required.',
                'danger'
            )

            return redirect(
                url_for('auth.login')
            )

        return fn(*args, **kwargs)

    return wrapper

# ─────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────

@ambulance_bp.route('/')
@ambulance_bp.route('/dashboard')

@ambulance_required
def dashboard():

    driver_id = session['user_id']

    db = get_db()

    cur = db.cursor()

    cur.execute(

        """
        SELECT *
        FROM live_routes

        WHERE driver_id=?
        AND is_active=1

        ORDER BY started_at DESC

        LIMIT 1
        """,

        (driver_id,)
    )

    active_route = cur.fetchone()

    db.close()

    return render_template(

        'ambulance_dashboard.html',

        driver_name=session.get(
            'full_name',
            'Driver'
        ),

        ambulance_number=session.get(
            'ambulance_number',
            ''
        ),

        hospital=session.get(
            'hospital_name',
            ''
        ),

        active_route=active_route,

        driver_id=driver_id
    )

# ─────────────────────────────────────────
# GEOCODING
# ─────────────────────────────────────────

def geocode_location(location):

    try:

        url = (
            "https://nominatim.openstreetmap.org/"
            "search"
        )

        params = {

            'q': location,

            'format': 'json',

            'limit': 1
        }

        response = requests.get(
            url,
            params=params,
            headers={
                'User-Agent':
                    'ITMS-System'
            }
        )

        data = response.json()

        if not data:
            return None, None

        return (

            float(data[0]['lat']),

            float(data[0]['lon'])
        )

    except Exception as e:

        print(
            f"[Geocode Error] {e}"
        )

        return None, None

# ─────────────────────────────────────────
# START ROUTE
# ─────────────────────────────────────────

@ambulance_bp.route(
    '/start_route',
    methods=['POST']
)

@ambulance_required
def start_route():

    driver_id = session['user_id']

    source = request.form.get(
        'source',
        ''
    )

    destination = request.form.get(
        'destination',
        ''
    )

    source_lat = _float_or_none(request.form.get('source_lat'))
    source_lng = _float_or_none(request.form.get('source_lng'))
    dest_lat = _float_or_none(request.form.get('destination_lat'))
    dest_lng = _float_or_none(request.form.get('destination_lng'))

    if source_lat is None or source_lng is None:
        source_lat, source_lng = geocode_location(source)

    if dest_lat is None or dest_lng is None:
        dest_lat, dest_lng = geocode_location(destination)

    if dest_lat is None or dest_lng is None:
        dest_lat, dest_lng = _known_hospital_coords(destination)

    db = get_db()

    cur = db.cursor()

    if source_lat is None or source_lng is None or dest_lat is None or dest_lng is None:
        db.close()
        flash('Could not find the selected route locations. Please try again.', 'danger')
        return redirect(url_for('ambulance.dashboard'))

    # deactivate previous
    cur.execute(

        """
        UPDATE live_routes

        SET is_active=0

        WHERE driver_id=?
        """,

        (driver_id,)
    )

    # insert new route
    cur.execute(

        """
        INSERT INTO live_routes (

            driver_id,

            source,
            destination,

            source_lat,
            source_lng,

            destination_lat,
            destination_lng,

            lat,
            lng,

            is_active

        )

        VALUES (?,?,?,?,?,?,?,?,?,1)
        """,

        (

            driver_id,

            source,
            destination,

            source_lat,
            source_lng,

            dest_lat,
            dest_lng,

            source_lat,
            source_lng
        )
    )

    db.commit()

    db.close()

    flash(
        'Emergency route started.',
        'success'
    )

    return redirect(
        url_for('ambulance.dashboard')
    )

# ─────────────────────────────────────────
# END ROUTE
# ─────────────────────────────────────────

@ambulance_bp.route(
    '/end_route',
    methods=['POST']
)

@ambulance_required
def end_route():

    driver_id = session['user_id']

    db = get_db()

    cur = db.cursor()

    cur.execute(

        """
        UPDATE live_routes

        SET is_active=0

        WHERE driver_id=?
        """,

        (driver_id,)
    )

    db.commit()

    db.close()

    flash(
        'Route ended.',
        'info'
    )

    return redirect(
        url_for('ambulance.dashboard')
    )

# ─────────────────────────────────────────
# LIVE GPS UPDATE
# ─────────────────────────────────────────

@ambulance_bp.route(
    '/update_location',
    methods=['POST']
)

@ambulance_required
def update_location():

    driver_id = session['user_id']

    data = request.get_json(
        force=True
    )

    lat = data.get('lat')

    lng = data.get('lng')

    if lat is None or lng is None:

        return jsonify({

            'error':
                'Missing coordinates'

        }), 400

    lat = _float_or_none(lat)
    lng = _float_or_none(lng)

    if lat is None or lng is None:

        return jsonify({

            'error':
                'Invalid coordinates'

        }), 400

    db = get_db()

    cur = db.cursor()

    # get active route
    cur.execute(

        """
        SELECT *

        FROM live_routes

        WHERE driver_id=?
        AND is_active=1

        LIMIT 1
        """,

        (driver_id,)
    )

    route = cur.fetchone()

    if not route:

        db.close()

        return jsonify({

            'error':
                'No active route'

        }), 404

    # update route
    cur.execute(

        """
        UPDATE live_routes

        SET
            lat=?,
            lng=?,
            updated_at=CURRENT_TIMESTAMP

        WHERE driver_id=?
        AND is_active=1
        """,

        (
            lat,
            lng,
            driver_id
        )
    )

    db.commit()

    db.close()

    nearby_lane, signal_distance = (
        _activate_signal_if_ambulance_nearby(
            lat,
            lng
        )
    )

    # Socket sync
    from socket_events import (
        ambulance_locations
    )

    ambulance_locations[driver_id] = {

        'driver_id': driver_id,

        'lat': lat,
        'lng': lng,

        'destination_lat':
            route['destination_lat'],

        'destination_lng':
            route['destination_lng'],

        'source':
            route['source'],

        'destination':
            route['destination'],

        'active': True,

        'near_signal_lane':
            nearby_lane,

        'signal_distance_m':
            signal_distance,

        'timestamp':
            time.time()
    }

    return jsonify({

        'success': True,

        'message':
            'Location updated successfully',

        'near_signal_lane':
            nearby_lane,

        'signal_distance_m':
            signal_distance
    })


# ─────────────────────────────────────────
# ACTIVE ROUTES API
# ─────────────────────────────────────────

@ambulance_bp.route(
    '/api/active_routes'
)

def active_routes():

    db = get_db()

    cur = db.cursor()

    cur.execute(

        """
        SELECT lr.*, ad.driver_name, ad.ambulance_number, ad.hospital_name

        FROM live_routes lr

        LEFT JOIN ambulance_drivers ad ON lr.driver_id = ad.id

        WHERE lr.is_active=1
        """
    )

    routes = cur.fetchall()

    db.close()

    output = []

    for r in routes:

        output.append({

            'id': r['id'],

            'driver_id':
                r['driver_id'],

            'source':
                r['source'],

            'destination':
                r['destination'],

            'lat':
                r['lat'] if r['lat'] is not None else r['source_lat'],

            'lng':
                r['lng'] if r['lng'] is not None else r['source_lng'],

            'source_lat':
                r['source_lat'],

            'source_lng':
                r['source_lng'],

            'destination_lat':
                r['destination_lat'],

            'destination_lng':
                r['destination_lng'],

            'driver_name':
                r['driver_name'],

            'ambulance_number':
                r['ambulance_number'],

            'hospital_name':
                r['hospital_name']
        })

    return jsonify(output)


# ─────────────────────────────────────────
# GEOCODE API
# ─────────────────────────────────────────

@ambulance_bp.route('/geocode')

def geocode_api():

    location = request.args.get(
        'q',
        ''
    )

    if not location:

        return jsonify({
            'error': 'Missing location'
        }), 400

    lat, lng = geocode_location(
        location
    )

    if lat is None:

        return jsonify({
            'error': 'Location not found'
        }), 404

    return jsonify({

        'lat': lat,
        'lng': lng
    })


@ambulance_bp.route('/google_route', methods=['POST'])
@ambulance_required
def google_route():
    api_key = os.environ.get('GOOGLE_MAPS_API_KEY')

    if not api_key:
        return jsonify({
            'error': 'GOOGLE_MAPS_API_KEY is not configured'
        }), 503

    data = request.get_json(force=True) or {}
    points = data.get('points') or []

    if len(points) < 2:
        return jsonify({
            'error': 'At least origin and destination are required'
        }), 400

    parsed_points = []

    for point in points:
        lat = _float_or_none(point.get('lat'))
        lng = _float_or_none(point.get('lng'))

        if lat is None or lng is None:
            return jsonify({
                'error': 'Invalid route point'
            }), 400

        parsed_points.append({
            'lat': lat,
            'lng': lng
        })

    origin = parsed_points[0]
    destination = parsed_points[-1]
    intermediates = parsed_points[1:-1]

    payload = {
        'origin': _google_waypoint(
            origin['lat'],
            origin['lng']
        ),
        'destination': _google_waypoint(
            destination['lat'],
            destination['lng']
        ),
        'travelMode': 'DRIVE',
        'routingPreference': 'TRAFFIC_AWARE_OPTIMAL',
        'polylineQuality': 'HIGH_QUALITY',
        'polylineEncoding': 'GEO_JSON_LINESTRING',
        'computeAlternativeRoutes': False
    }

    if intermediates:
        payload['intermediates'] = [
            _google_waypoint(
                point['lat'],
                point['lng']
            )
            for point in intermediates
        ]

    try:
        response = requests.post(
            'https://routes.googleapis.com/directions/v2:computeRoutes',
            json=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Goog-Api-Key': api_key,
                'X-Goog-FieldMask': (
                    'routes.distanceMeters,'
                    'routes.duration,'
                    'routes.polyline.geoJsonLinestring'
                )
            },
            timeout=10
        )

        if not response.ok:
            return jsonify({
                'error': 'Google route request failed',
                'details': response.text[:500]
            }), response.status_code

        route_data = response.json()
        routes = route_data.get('routes') or []

        if not routes:
            return jsonify({
                'error': 'No Google route found'
            }), 404

        route = routes[0]
        coordinates = (
            route
            .get('polyline', {})
            .get('geoJsonLinestring', {})
            .get('coordinates', [])
        )

        coords = [
            [coord[1], coord[0]]
            for coord in coordinates
            if len(coord) >= 2
        ]

        if not coords:
            return jsonify({
                'error': 'Google route returned no polyline'
            }), 404

        return jsonify({
            'provider': 'google',
            'coords': coords,
            'distance_m': route.get('distanceMeters'),
            'duration': route.get('duration')
        })

    except requests.RequestException as exc:
        return jsonify({
            'error': 'Google route service unavailable',
            'details': str(exc)
        }), 502
