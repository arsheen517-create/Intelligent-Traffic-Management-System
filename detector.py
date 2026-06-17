# detector.py
# ADVANCED AI TRAFFIC + AMBULANCE DETECTOR

from ultralytics import YOLO

import cv2
import numpy as np

import time


class TrafficDetector:

    def __init__(
        self,
        vehicle_model_path,
        ambulance_model_path
    ):

        # ─────────────────────────────────────
        # LOAD MODELS
        # ─────────────────────────────────────

        self.vehicle_model = YOLO(
            vehicle_model_path
        )

        self.ambulance_model = YOLO(
            ambulance_model_path
        )

        # ─────────────────────────────────────
        # VEHICLE MODEL CONFIG
        # ─────────────────────────────────────

        self.vehicle_model.classes_to_detect = [
            2,  # car
            3,  # motorcycle
            5,  # bus
            7   # truck
        ]

        self.vehicle_class_names = {

            2: 'Car',

            3: 'Motorcycle',

            5: 'Bus',

            7: 'Truck'
        }

        # ─────────────────────────────────────
        # AMBULANCE MODEL CONFIG
        # ─────────────────────────────────────

        self.ambulance_model.classes_to_detect = [
            0
        ]

        self.ambulance_class_names = {

            0: 'Ambulance'
        }

        self.ambulance_threshold = 0.70

        # ─────────────────────────────────────
        # COLORS
        # ─────────────────────────────────────

        all_names = (

            list(
                self.vehicle_class_names.values()
            )

            +

            list(
                self.ambulance_class_names.values()
            )
        )

        self.colors = np.random.uniform(

            0,
            255,

            size=(len(all_names), 3)
        )

        self.class_name_to_color_index = {

            name: i

            for i, name in enumerate(all_names)
        }

        # Emergency state
        self.last_ambulance_time = 0

        print(
            "[Detector] Vehicle and "
            "Ambulance models loaded."
        )

    # ─────────────────────────────────────
    # YOLO BBOX CONVERSION
    # ─────────────────────────────────────

    def yolo2bbox(self, bboxes):

        xmin = (
            bboxes[0]
            - bboxes[2] / 2
        )

        ymin = (
            bboxes[1]
            - bboxes[3] / 2
        )

        xmax = (
            bboxes[0]
            + bboxes[2] / 2
        )

        ymax = (
            bboxes[1]
            + bboxes[3] / 2
        )

        return xmin, ymin, xmax, ymax

    # ─────────────────────────────────────
    # DRAW BOXES
    # ─────────────────────────────────────

    def plot_box(
        self,
        image,
        bboxes,
        labels,
        confs,
        ambulance_detected=False
    ):

        h, w, _ = image.shape

        for box_num, box in enumerate(bboxes):

            x1, y1, x2, y2 = self.yolo2bbox(box)

            xmin = int(x1 * w)
            ymin = int(y1 * h)

            xmax = int(x2 * w)
            ymax = int(y2 * h)

            class_name = labels[box_num]

            confidence = confs[box_num]

            # Ambulance special color
            if class_name == 'Ambulance':

                color = (0, 0, 255)

                thickness = 4

            else:

                color = self.colors[
                    self.class_name_to_color_index[
                        class_name
                    ]
                ]

                thickness = 2

            cv2.rectangle(

                image,

                (xmin, ymin),

                (xmax, ymax),

                color=color,

                thickness=thickness
            )

            label = (
                f"{class_name} "
                f"{confidence:.2f}"
            )

            cv2.putText(

                image,

                label,

                (xmin, ymin - 10),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.7,

                (255, 255, 255),

                2
            )

        # Emergency overlay
        if ambulance_detected:

            cv2.rectangle(

                image,

                (0, 0),

                (w, 80),

                (0, 0, 255),

                -1
            )

            cv2.putText(

                image,

                "EMERGENCY VEHICLE DETECTED",

                (20, 50),

                cv2.FONT_HERSHEY_SIMPLEX,

                1.2,

                (255, 255, 255),

                3
            )

        return image

    # ─────────────────────────────────────
    # MAIN FRAME PROCESSOR
    # ─────────────────────────────────────

    def process_frame(self, frame):

        bboxes_to_plot = []

        labels_to_plot = []

        confs_to_plot = []

        detailed_counts = {

            'Car': 0,

            'Bus': 0,

            'Truck': 0,

            'Motorcycle': 0,

            'Ambulance': 0
        }

        ambulance_detected = False

        highest_ambulance_conf = 0

        frame_height, frame_width = (
            frame.shape[:2]
        )

        # ─────────────────────────────────
        # VEHICLE DETECTION
        # ─────────────────────────────────

        vehicle_results = self.vehicle_model(

            frame,

            classes=
                self.vehicle_model
                .classes_to_detect,

            verbose=False
        )

        for det in vehicle_results[0].boxes:

            cls = int(det.cls[0].item())

            class_name = (
                self.vehicle_class_names[cls]
            )

            detailed_counts[
                class_name
            ] += 1

            xywh = det.xywh[0].cpu().numpy()

            bboxes_to_plot.append([

                xywh[0] / frame_width,

                xywh[1] / frame_height,

                xywh[2] / frame_width,

                xywh[3] / frame_height
            ])

            labels_to_plot.append(
                class_name
            )

            confs_to_plot.append(
                det.conf[0].item()
            )

        # ─────────────────────────────────
        # AMBULANCE DETECTION
        # ─────────────────────────────────

        ambulance_results = self.ambulance_model(

            frame,

            classes=
                self.ambulance_model
                .classes_to_detect,

            verbose=False
        )

        for det in ambulance_results[0].boxes:

            conf = det.conf[0].item()

            if conf >= self.ambulance_threshold:

                ambulance_detected = True

                highest_ambulance_conf = max(

                    highest_ambulance_conf,

                    conf
                )

                detailed_counts[
                    'Ambulance'
                ] += 1

                cls = int(
                    det.cls[0].item()
                )

                class_name = (
                    self.ambulance_class_names[
                        cls
                    ]
                )

                xywh = (
                    det.xywh[0]
                    .cpu()
                    .numpy()
                )

                bboxes_to_plot.append([

                    xywh[0] / frame_width,

                    xywh[1] / frame_height,

                    xywh[2] / frame_width,

                    xywh[3] / frame_height
                ])

                labels_to_plot.append(
                    class_name
                )

                confs_to_plot.append(
                    conf
                )

        # ─────────────────────────────────
        # EMERGENCY PRIORITY
        # ─────────────────────────────────

        if ambulance_detected:

            self.last_ambulance_time = (
                time.time()
            )

            print(

                "[EMERGENCY] "
                "Ambulance detected "
                f"(confidence: "
                f"{highest_ambulance_conf:.2f})"
            )

        # ─────────────────────────────────
        # DRAW VISUALS
        # ─────────────────────────────────

        processed_frame = self.plot_box(

            frame,

            bboxes_to_plot,

            labels_to_plot,

            confs_to_plot,

            ambulance_detected
        )

        return (

            processed_frame,

            ambulance_detected,

            detailed_counts
        )