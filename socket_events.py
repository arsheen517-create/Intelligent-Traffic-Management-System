"""
socket_events.py
Advanced Real-Time SocketIO System
"""

from flask_socketio import emit, join_room, leave_room
from flask import request

import threading
import time
import math

# Live ambulance tracking
ambulance_locations = {}

# Example:
# {
#   driver_id: {
#       lat,
#       lng,
#       destination_lat,
#       destination_lng,
#       hospital,
#       active
#   }
# }

_broadcast_thread = None
_broadcast_lock = threading.Lock()


def register_socket_events(socketio, traffic_manager):

    # ─────────────────────────────────────────────
    # CLIENT CONNECTIONS
    # ─────────────────────────────────────────────

    @socketio.on('connect')
    def on_connect():
        print(f"[Socket] Client connected: {request.sid}")

    @socketio.on('disconnect')
    def on_disconnect():
        print(f"[Socket] Client disconnected: {request.sid}")

    # ─────────────────────────────────────────────
    # ROOM MANAGEMENT
    # ─────────────────────────────────────────────

    @socketio.on('join_room')
    def on_join(data):

        room = data.get('room', 'public')

        join_room(room)

        emit('status', {
            'msg': f'Joined room: {room}'
        })

    @socketio.on('leave_room')
    def on_leave(data):

        room = data.get('room', 'public')

        leave_room(room)

    # ─────────────────────────────────────────────
    # LIVE AMBULANCE LOCATION UPDATE
    # ─────────────────────────────────────────────

    @socketio.on('ambulance_location')
    def on_ambulance_location(data):

        driver_id = data.get('driver_id')

        if not driver_id:
            return

        existing = ambulance_locations.get(driver_id, {})

        ambulance_locations[driver_id] = {

            'driver_id': driver_id,

            'lat': data.get('lat'),
            'lng': data.get('lng'),

            'destination_lat':
                data.get('destination_lat', existing.get('destination_lat')),

            'destination_lng':
                data.get('destination_lng', existing.get('destination_lng')),

            'source':
                data.get('source', existing.get('source')),

            'destination':
                data.get('destination', existing.get('destination')),

            'hospital':
                data.get('hospital', existing.get('hospital')),

            'active':
                data.get('active', True),

            'timestamp':
                time.time()
        }

        # Broadcast to everyone
        socketio.emit(
            'ambulance_location',
            ambulance_locations[driver_id],
            room='public'
        )

        socketio.emit(
            'ambulance_location',
            ambulance_locations[driver_id],
            room='admin'
        )

        socketio.emit(
            'ambulance_location',
            ambulance_locations[driver_id],
            room='ambulance'
        )

    # ─────────────────────────────────────────────
    # MANUAL SIGNAL OVERRIDE
    # ─────────────────────────────────────────────

    @socketio.on('force_signal')
    def on_force_signal(data):

        lane_id = int(
            data.get('lane_id', 1)
        )

        status = data.get(
            'status',
            'green'
        )

        traffic_manager.force_signal(
            lane_id,
            status
        )

        socketio.emit(
            'signal_forced',
            {
                'lane_id': lane_id,
                'status': status
            },
            room='admin'
        )

    # ─────────────────────────────────────────────
    # GREEN CORRIDOR LOGIC
    # ─────────────────────────────────────────────

    def activate_green_corridor(current_lane):

        try:

            next_lane = (current_lane % 4) + 1

            traffic_manager.activate_green_corridor(
                current_lane
            )

            print(
                f"[Green Corridor] "
                f"Activated from lane {current_lane}; "
                f"next lane {next_lane}"
            )

            socketio.emit(
                'green_corridor',
                {
                    'current_lane': current_lane,
                    'next_lanes': [next_lane]
                }
            )

        except Exception as e:

            print(
                f"[Green Corridor Error] {e}"
            )

    # ─────────────────────────────────────────────
    # LIVE TRAFFIC BROADCAST LOOP
    # ─────────────────────────────────────────────

    def _broadcast_state():

        while True:

            try:

                state = (
                    traffic_manager
                    .get_system_state()
                )

                payload = {

                    'traffic_state': state,

                    'ambulance_locations':
                        list(
                            ambulance_locations
                            .values()
                        )
                }

                # Global update
                socketio.emit(
                    'state_update',
                    payload
                )

                # Ambulance detection logic
                for lane_id, lane in state.items():

                    if (
                        isinstance(lane, dict)
                        and lane.get('ambulance')
                    ):

                        # Activate green corridor
                        activate_green_corridor(
                            int(lane_id)
                        )

                        # Broadcast alert
                        alert_payload = {

                            'lane_id': lane_id,

                            'message':
                                f'🚨 Ambulance detected near '
                                f'Signal {lane_id}! '
                                f'Green corridor activated.'
                        }

                        socketio.emit(
                            'ambulance_alert',
                            alert_payload,
                            room='public'
                        )

                        socketio.emit(
                            'ambulance_alert',
                            alert_payload,
                            room='admin'
                        )

                # Remove inactive ambulances
                now = time.time()

                inactive = []

                for driver_id, data in (
                    ambulance_locations.items()
                ):

                    if now - data.get(
                        'timestamp',
                        now
                    ) > 30:

                        inactive.append(driver_id)

                for driver_id in inactive:

                    del ambulance_locations[
                        driver_id
                    ]

                    socketio.emit(
                        'ambulance_offline',
                        {
                            'driver_id': driver_id
                        }
                    )

            except Exception as e:

                print(
                    f"[Socket Broadcast Error] {e}"
                )

            time.sleep(1)

    # ─────────────────────────────────────────────
    # START BACKGROUND THREAD
    # ─────────────────────────────────────────────

    global _broadcast_thread

    with _broadcast_lock:

        if (
            _broadcast_thread is None
            or not _broadcast_thread.is_alive()
        ):

            _broadcast_thread = threading.Thread(
                target=_broadcast_state,
                daemon=True,
                name='socket-broadcast'
            )

            _broadcast_thread.start()

            print(
                "[Socket] Background "
                "broadcast thread started."
            )
