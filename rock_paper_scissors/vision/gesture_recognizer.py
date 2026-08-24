from __future__ import annotations

import cv2
import mediapipe as mp
import numpy as np
from PySide6.QtCore import QThread, Signal


class GestureRecognizerThread(QThread):
    frame_processed = Signal(np.ndarray, str)
    camera_status = Signal(bool, str)

    def __init__(self, camera_index: int = 0) -> None:
        super().__init__()
        self.running = False
        self.cap = None
        self.camera_index = camera_index
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5,
        )
        self.mp_draw = mp.solutions.drawing_utils

    def find_available_camera(self) -> int | None:
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                cap.release()
                return i
        return None

    def run(self) -> None:
        self.running = True
        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            available = self.find_available_camera()
            if available is not None:
                self.cap = cv2.VideoCapture(available)
                self.camera_index = available
                self.camera_status.emit(True, f"Using camera {available}")
            else:
                self.camera_status.emit(False, "No camera found")
                return
        else:
            self.camera_status.emit(True, f"Using camera {self.camera_index}")

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb_frame)
            gesture = "Waiting..."

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                    gesture = self.recognize_gesture(hand_landmarks.landmark)
                    h, w, _ = frame.shape
                    cv2.putText(frame, f"Gesture: {gesture}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    if gesture == "Scissors":
                        index_tip = hand_landmarks.landmark[8]
                        middle_tip = hand_landmarks.landmark[12]
                        index_pos = (int(index_tip.x * w), int(index_tip.y * h))
                        middle_pos = (int(middle_tip.x * w), int(middle_tip.y * h))
                        cv2.line(frame, index_pos, middle_pos, (0, 255, 255), 2)
                        cv2.putText(frame, "Scissors!", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            self.frame_processed.emit(frame, gesture)
            self.msleep(50)

    def recognize_gesture(self, landmarks) -> str:
        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        index_tip = landmarks[8]
        index_pip = landmarks[6]
        index_mcp = landmarks[5]
        middle_tip = landmarks[12]
        middle_pip = landmarks[10]
        middle_mcp = landmarks[9]
        ring_tip = landmarks[16]
        ring_pip = landmarks[14]
        pinky_tip = landmarks[20]
        pinky_pip = landmarks[18]

        thumb_extended = abs(thumb_tip.x - thumb_ip.x) > 0.04
        index_extended = index_tip.y < index_pip.y
        middle_extended = middle_tip.y < middle_pip.y
        ring_extended = ring_tip.y < ring_pip.y
        pinky_extended = pinky_tip.y < pinky_pip.y

        mcp_distance = abs(index_mcp.x - middle_mcp.x)
        tip_distance = abs(index_tip.x - middle_tip.x)

        extended_count = sum([index_extended, middle_extended, ring_extended, pinky_extended])

        if extended_count == 0:
            return "Rock"
        if (
            index_extended
            and middle_extended
            and not ring_extended
            and not pinky_extended
            and mcp_distance > 0.025
            and tip_distance > 0.02
        ):
            return "Scissors"
        if extended_count >= 4:
            return "Paper"
        if (
            index_extended
            and middle_extended
            and not ring_extended
            and not pinky_extended
            and (mcp_distance <= 0.025 or tip_distance <= 0.02)
        ):
            return "Scissors (spread fingers)"
        if index_extended and not middle_extended and not ring_extended and not pinky_extended:
            return "Point"
        if index_extended and middle_extended and ring_extended and not pinky_extended:
            return "Three"
        if thumb_extended and not any([index_extended, middle_extended, ring_extended, pinky_extended]):
            return "Thumb"
        return "Unknown"

    def stop(self) -> None:
        self.running = False
        if self.cap:
            self.cap.release()
        self.wait()
