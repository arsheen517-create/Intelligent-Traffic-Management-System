"""
traffic_logic.py
ADVANCED AI GREEN CORRIDOR SYSTEM
"""

import time
import threading
import sqlite3

DATABASE = 'users.db'


class TrafficLogic:

    def __init__(self):

        # ─────────────────────────────────────────
        # LANE STATE
        # ─────────────────────────────────────────

        self.lanes = {

            i: {

                'density': 0,

                'ambulance': False,

                'status': 'red',

                'current_vehicle_counts':
                    self._empty_count()

            }

            for i in range(1, 5)
        }

        # Statistics
        self.cumulative_counts = {
            i: self._empty_count()
            for i in range(1, 5)
        }

        self.last_green_times = {
            1: 0,
            2: 0,
            3: 0,
            4: 0
        }

        # Timing
        self.timer = 0

        self.base_green_time = 10

        self.orange_light_duration = 3

        self.max_extra_time = 15

        self.density_threshold = 13

        # Emergency systems
        self.ambulance_override = False

        self.green_corridor_mode = False

        self.green_corridor_until = 0

        # Manual admin override
        self._manual_override = False

        self._manual_override_until = 0

        # FSM state
        self.priority_order = [1, 2, 3, 4]

        self.current_priority_index = 0

        self.current_active_lane = 1

        self.lanes[1]['status'] = 'green'

        self.current_green_duration = (
            self.base_green_time
        )

        self.is_first_run = True

        self.lock = threading.Lock()

        # Start thread
        self.logic_thread = threading.Thread(
            target=self._run_logic,
            daemon=True,
            name='traffic-logic'
        )

        self.logic_thread.start()

    # ─────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────

    @staticmethod
    def _empty_count():

        return {

            'Car': 0,

            'Bus': 0,

            'Truck': 0,

            'Motorcycle': 0,

            'Ambulance': 0
        }

    # ─────────────────────────────────────────
    # UPDATE LANE DATA
    # ─────────────────────────────────────────

    def update_lane_data(
        self,
        lane_id,
        density,
        ambulance,
        detailed_counts
    ):

        with self.lock:

            self.lanes[lane_id][
                'density'
            ] = density

            self.lanes[lane_id][
                'ambulance'
            ] = ambulance

            self.lanes[lane_id][
                'current_vehicle_counts'
            ] = detailed_counts

        # Ambulance detected
        if ambulance:

            print(
                f"[AI] Ambulance detected "
                f"in lane {lane_id}"
            )

            self.activate_green_corridor(
                lane_id
            )

            threading.Thread(

                target=self._log_detection,

                args=(
                    lane_id,
                    'Ambulance',
                    1.0,
                    True
                ),

                daemon=True

            ).start()

    # ─────────────────────────────────────────
    # GREEN CORRIDOR
    # ─────────────────────────────────────────

    def activate_green_corridor(
        self,
        current_lane
    ):

        with self.lock:

            if not self.green_corridor_mode:

                self.cumulative_counts[current_lane]['Ambulance'] += 1

            self.green_corridor_mode = True

            self.green_corridor_until = (
                time.time() + 25
            )

            # All red first
            for i in range(1, 5):

                self.lanes[i][
                    'status'
                ] = 'red'

            # Current lane green
            self.lanes[current_lane][
                'status'
            ] = 'green'

            # Keep the ambulance lane and the next adjacent lane open.
            next_lane = (
                current_lane % 4
            ) + 1

            self.lanes[next_lane][
                'status'
            ] = 'green'

            self.current_active_lane = (
                current_lane
            )

            self.timer = 0

            print(
                f"[GREEN CORRIDOR] "
                f"Activated from lane "
                f"{current_lane}; "
                f"next lane {next_lane}"
            )

    # ─────────────────────────────────────────
    # MANUAL OVERRIDE
    # ─────────────────────────────────────────

    def force_signal(
        self,
        lane_id,
        status
    ):

        with self.lock:

            for i in range(1, 5):

                self.lanes[i][
                    'status'
                ] = 'red'

            self.lanes[lane_id][
                'status'
            ] = status

            self.current_active_lane = (
                lane_id
            )

            self._manual_override = True

            self._manual_override_until = (
                time.time() + 30
            )

            self.timer = 0

        print(
            f"[Manual Override] "
            f"Lane {lane_id} = {status}"
        )

    # ─────────────────────────────────────────
    # STATE API
    # ─────────────────────────────────────────

    def get_system_state(self):

        with self.lock:

            state_copy = {}

            for i in range(1, 5):

                lane = self.lanes[i]

                state_copy[i] = {

                    'status':
                        lane['status'],

                    'density':
                        lane['density'],

                    'ambulance':
                        lane['ambulance']
                }

            return state_copy

    # ─────────────────────────────────────────
    # ANALYSIS API
    # ─────────────────────────────────────────

    def get_analysis_data(self):

        with self.lock:

            return {

                'cumulative_counts':
                    self.cumulative_counts,

                'current_density': {

                    i:
                    self.lanes[i]['density']

                    for i in range(1, 5)
                },

                'last_green_times':
                    self.last_green_times
            }

    # ─────────────────────────────────────────
    # MAIN FSM LOOP
    # ─────────────────────────────────────────

    def _run_logic(self):

        while True:

            time.sleep(1)

            with self.lock:

                # Startup
                if self.is_first_run:

                    self._set_green_light(
                        self.current_active_lane
                    )

                    self.is_first_run = False

                    continue

                # Manual override
                if self._manual_override:

                    if (
                        time.time()
                        <
                        self._manual_override_until
                    ):

                        continue

                    else:

                        self._manual_override = False

                        print(
                            "[Traffic] "
                            "Manual override expired"
                        )

                # Green corridor active
                if self.green_corridor_mode:

                    if (
                        time.time()
                        <
                        self.green_corridor_until
                    ):

                        continue

                    else:

                        print(
                            "[GREEN CORRIDOR] "
                            "Deactivated"
                        )

                        self.green_corridor_mode = False

                        # Reset
                        for i in range(1, 5):

                            self.lanes[i][
                                'status'
                            ] = 'red'

                        self._set_green_light(1)

                        continue

                # Normal cycle
                self.timer += 1

                cur_status = self.lanes[
                    self.current_active_lane
                ]['status']

                if (
                    cur_status == 'green'
                    and
                    self.timer >=
                    self.current_green_duration
                ):

                    self._set_orange_light(
                        self.current_active_lane
                    )

                elif (
                    cur_status == 'orange'
                    and
                    self.timer >=
                    self.orange_light_duration
                ):

                    counts = self.lanes[
                        self.current_active_lane
                    ].get(

                        'current_vehicle_counts',

                        self._empty_count()
                    )
                    print("COUNTS:", counts)
                    for v, c in counts.items():

                        self.cumulative_counts[
                            self.current_active_lane
                        ][v] += c
                        print(
                             "CUMULATIVE:",
                              self.current_active_lane,
                              self.cumulative_counts[self.current_active_lane]
                        )
                        

                    self.lanes[
                        self.current_active_lane
                    ]['status'] = 'red'

                    self.current_priority_index = (

                        (
                            self.current_priority_index
                            + 1
                        )

                        %
                        len(self.priority_order)
                    )

                    next_lane = self.priority_order[
                        self.current_priority_index
                    ]

                    self._set_green_light(
                        next_lane
                    )

    # ─────────────────────────────────────────
    # LIGHT HELPERS
    # ─────────────────────────────────────────

    def _set_orange_light(
        self,
        lane_id
    ):

        self.lanes[lane_id][
            'status'
        ] = 'orange'

        self.timer = 0

        print(
            f"[Traffic] Lane "
            f"{lane_id} → ORANGE"
        )

    def _set_green_light(
        self,
        lane_id
    ):

        for i in range(1, 5):

            if i != lane_id:

                self.lanes[i][
                    'status'
                ] = 'red'

        self.lanes[lane_id][
            'status'
        ] = 'green'

        self.current_active_lane = (
            lane_id
        )

        density = self.lanes[
            lane_id
        ]['density']

        if density > self.density_threshold:

            extra_time = self.max_extra_time

        else:

            extra_time = 0

        self.current_green_duration = (
            self.base_green_time
            +
            extra_time
        )

        self.last_green_times[
            lane_id
        ] = self.current_green_duration

        self.timer = 0

        print(
            f"[Traffic] Lane "
            f"{lane_id} → GREEN "
            f"({self.current_green_duration}s)"
        )

        threading.Thread(

            target=self._log_signal,

            args=(
                lane_id,
                'green',
                'normal'
            ),

            daemon=True

        ).start()

    # ─────────────────────────────────────────
    # DATABASE LOGGING
    # ─────────────────────────────────────────

    def _log_signal(
        self,
        lane_id,
        status,
        reason
    ):

        try:

            conn = sqlite3.connect(
                DATABASE
            )

            conn.execute(

                """
                INSERT INTO signal_status
                (lane_id, status, reason)

                VALUES (?,?,?)
                """,

                (
                    lane_id,
                    status,
                    reason
                )
            )

            conn.commit()

            conn.close()

        except Exception as e:

            print(
                f"[DB Signal Error] {e}"
            )

    def _log_detection(
        self,
        lane_id,
        vehicle_type,
        confidence,
        is_ambulance
    ):

        try:

            conn = sqlite3.connect(
                DATABASE
            )

            conn.execute(

                """
                INSERT INTO detections
                (lane_id, vehicle_type,
                 confidence, is_ambulance)

                VALUES (?,?,?,?)
                """,

                (
                    lane_id,
                    vehicle_type,
                    confidence,
                    int(is_ambulance)
                )
            )

            conn.commit()

            conn.close()

        except Exception as e:

            print(
                f"[DB Detection Error] {e}"
            )
