import cv2
import numpy as np
import pygame
import mediapipe as mp
import time
import platform
import subprocess
import os
from enum import Enum
import pyautogui

pygame.init()
screen_width = 800
screen_height = 600
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Body Controller")

mp_face = mp.solutions.face_mesh
mp_pose = mp.solutions.pose

FACE_CONNECTIONS = mp_face.FACEMESH_TESSELATION
FACE_CONTOURS = mp_face.FACEMESH_CONTOURS
BODY_CONNECTIONS = mp_pose.POSE_CONNECTIONS
GESTURE_COOLDOWN = 1.0
SWIPE_THRESHOLD = 0.15
ARMS_UP_THRESHOLD = 0.7
DOUBLE_SWIPE_TIME = 0.5
FACE_ZONE_MARGIN = 0.1
EDGE_THRESHOLD = 0.15
HEAD_TILT_THRESHOLD = 0.04
ARMS_STRETCHED_THRESHOLD = 0.3
MOUTH_OPEN_THRESHOLD = 0.2

class GestureState:
    def __init__(self):
        self.last_gesture_time = 0
        self.arms_were_up = False

gesture_state = GestureState()

def initialize_camera():
    cap = cv2.VideoCapture(0)
    time.sleep(1)
    
    if not cap.isOpened():
        cap = cv2.VideoCapture(1)
        if not cap.isOpened():
            raise RuntimeError("Could not access the camera!")
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    return cap

try:
    cap = initialize_camera()
    
    face_mesh = mp_face.FaceMesh(
        max_num_faces=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    )
    
    pose = mp_pose.Pose(
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    )
    
except Exception as e:
    print(f"Initialization error: {e}")
    pygame.quit()
    exit(1)

FACE_COLOR = (100, 200, 255)
BODY_COLOR = (255, 100, 200)
EYE_COLOR = (255, 255, 255)
MOUTH_COLOR = (200, 100, 100)
CONTOUR_COLOR = (150, 150, 150)

def control_media(action):
    system = platform.system()
    
    if system == "Darwin":
        script_commands = {
            'playpause': 'tell application "Music" to playpause',
            'nexttrack': 'tell application "Music" to next track',
            'prevtrack': 'tell application "Music" to previous track',
            'volumeup': 'set volume output volume ((output volume of (get volume settings)) + 6.25)',
            'volumedown': 'set volume output volume ((output volume of (get volume settings)) - 6.25)'
        }
        cmd = f"osascript -e '{script_commands[action]}'"
        subprocess.run(cmd, shell=True)
        
    elif system == "Windows":
        if action == 'volumeup':
            pyautogui.press('volumeup')
        elif action == 'volumedown':
            pyautogui.press('volumedown')
        else:
            import win32api
            import win32con
            key_codes = {
                'playpause': win32con.VK_MEDIA_PLAY_PAUSE,
                'nexttrack': win32con.VK_MEDIA_NEXT_TRACK,
                'prevtrack': win32con.VK_MEDIA_PREV_TRACK
            }
            win32api.keybd_event(key_codes[action], 0, 0, 0)
            win32api.keybd_event(key_codes[action], 0, win32con.KEYEVENTF_KEYUP, 0)
            
    elif system == "Linux":
        commands = {
            'playpause': 'dbus-send --type=method_call --dest=org.mpris.MediaPlayer2.spotify ' 
                        '/org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.PlayPause',
            'nexttrack': 'dbus-send --type=method_call --dest=org.mpris.MediaPlayer2.spotify '
                        '/org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.Next',
            'prevtrack': 'dbus-send --type=method_call --dest=org.mpris.MediaPlayer2.spotify '
                        '/org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.Previous',
            'volumeup': 'pactl set-sink-volume @DEFAULT_SINK@ +5%',
            'volumedown': 'pactl set-sink-volume @DEFAULT_SINK@ -5%'
        }
        subprocess.run(commands[action], shell=True)

def handle_gestures(pose_landmarks):
    current_time = time.time()
    
    if current_time - gesture_state.last_gesture_time < GESTURE_COOLDOWN:
        return

    landmarks = pose_landmarks.landmark
    
    left_ear = landmarks[mp_pose.PoseLandmark.LEFT_EAR]
    right_ear = landmarks[mp_pose.PoseLandmark.RIGHT_EAR]
    nose = landmarks[mp_pose.PoseLandmark.NOSE]

    if all(lm.visibility > 0.7 for lm in [left_ear, right_ear, nose]):
        head_tilt = nose.x - (left_ear.x + right_ear.x) / 2
        
        if abs(head_tilt) > HEAD_TILT_THRESHOLD:
            if head_tilt > 0:
                print("Head tilted right - Volume down")
                control_media('volumedown')
                gesture_state.last_gesture_time = current_time
            else:
                print("Head tilted left - Volume up")
                control_media('volumeup')
                gesture_state.last_gesture_time = current_time

    left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST]
    right_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST]
    left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
    right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
    nose = landmarks[mp_pose.PoseLandmark.NOSE]

    if all(lm.visibility > 0.7 for lm in [left_wrist, right_wrist, left_shoulder, right_shoulder, nose]):
        left_arm_out = abs(left_wrist.y - left_shoulder.y) < ARMS_STRETCHED_THRESHOLD
        right_arm_out = abs(right_wrist.y - right_shoulder.y) < ARMS_STRETCHED_THRESHOLD
        arms_stretched = left_arm_out and right_arm_out
        
        shoulder_level = (left_shoulder.y + right_shoulder.y) / 2
        head_tilt = nose.y - shoulder_level
        
        if arms_stretched:
            if head_tilt < -HEAD_TILT_THRESHOLD:
                print("Volume up")
                control_media('volumeup')
                gesture_state.last_gesture_time = current_time
            elif head_tilt > HEAD_TILT_THRESHOLD:
                print("Volume down")
                control_media('volumedown')
                gesture_state.last_gesture_time = current_time

        both_hands_right = (left_wrist.x > 1 - EDGE_THRESHOLD and 
                          right_wrist.x > 1 - EDGE_THRESHOLD)
        
        if both_hands_right:
            print("Both hands at right edge - Next track")
            control_media('nexttrack')
            gesture_state.last_gesture_time = current_time

        both_hands_left = (left_wrist.x < EDGE_THRESHOLD and 
                         right_wrist.x < EDGE_THRESHOLD)
        
        if both_hands_left:
            print("Both hands at left edge - Previous track")
            control_media('prevtrack')
            gesture_state.last_gesture_time = current_time

        arms_up = (left_wrist.y < left_shoulder.y - ARMS_UP_THRESHOLD and 
                  right_wrist.y < right_shoulder.y - ARMS_UP_THRESHOLD)
        
        if arms_up and not gesture_state.arms_were_up:
            print("Arms up detected - Play/Pause")
            control_media('playpause')
            gesture_state.last_gesture_time = current_time
        
        gesture_state.arms_were_up = arms_up

def check_mouth_and_head(face_landmarks):
    if not face_landmarks:
        return False, 0
    
    upper_lip = face_landmarks.landmark[13]
    lower_lip = face_landmarks.landmark[14]
    
    upper_lip_2 = face_landmarks.landmark[312]
    lower_lip_2 = face_landmarks.landmark[317]
    
    mouth_distance = (abs(upper_lip.y - lower_lip.y) + 
                     abs(upper_lip_2.y - lower_lip_2.y)) / 2
    
    left_eye = face_landmarks.landmark[33]
    right_eye = face_landmarks.landmark[263]
    nose_tip = face_landmarks.landmark[4]
    
    eye_level = (left_eye.y + right_eye.y) / 2
    head_tilt = nose_tip.y - eye_level
    
    return mouth_distance > MOUTH_OPEN_THRESHOLD, head_tilt

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    ret, frame = cap.read()
    if not ret:
        continue
        
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    face_results = face_mesh.process(rgb_frame)
    
    pose_results = pose.process(rgb_frame)
    
    screen.fill((0, 0, 0))
    
    if face_results.multi_face_landmarks:
        for face_landmarks in face_results.multi_face_landmarks:
            for connection in FACE_CONNECTIONS:
                start_idx = connection[0]
                end_idx = connection[1]
                
                start_point = (int(face_landmarks.landmark[start_idx].x * screen_width),
                             int(face_landmarks.landmark[start_idx].y * screen_height))
                end_point = (int(face_landmarks.landmark[end_idx].x * screen_width),
                           int(face_landmarks.landmark[end_idx].y * screen_height))
                
                pygame.draw.line(screen, FACE_COLOR, start_point, end_point, 1)
            
            left_eye = [(int(face_landmarks.landmark[p].x * screen_width),
                        int(face_landmarks.landmark[p].y * screen_height))
                       for p in [33, 133, 157, 158, 159, 160, 161, 246]]
            right_eye = [(int(face_landmarks.landmark[p].x * screen_width),
                         int(face_landmarks.landmark[p].y * screen_height))
                        for p in [362, 263, 387, 388, 389, 390, 391, 466]]
            
            pygame.draw.polygon(screen, EYE_COLOR, left_eye, 0)
            pygame.draw.polygon(screen, EYE_COLOR, right_eye, 0)
            
            mouth_outer = [(int(face_landmarks.landmark[p].x * screen_width),
                          int(face_landmarks.landmark[p].y * screen_height))
                         for p in [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291]]
            mouth_inner = [(int(face_landmarks.landmark[p].x * screen_width),
                          int(face_landmarks.landmark[p].y * screen_height))
                         for p in [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308]]
            
            pygame.draw.polygon(screen, MOUTH_COLOR, mouth_outer, 0)
            pygame.draw.polygon(screen, (150, 50, 50), mouth_inner, 0)
            
            current_time = time.time()
            if current_time - gesture_state.last_gesture_time >= GESTURE_COOLDOWN:
                mouth_open, head_tilt = check_mouth_and_head(face_landmarks)
                
                if mouth_open:
                    if head_tilt < -HEAD_TILT_THRESHOLD:
                        print("Volume up")
                        control_media('volumeup')
                        gesture_state.last_gesture_time = current_time
                    elif head_tilt > HEAD_TILT_THRESHOLD:
                        print("Volume down")
                        control_media('volumedown')
                        gesture_state.last_gesture_time = current_time
    
    if pose_results.pose_landmarks:
        landmarks = pose_results.pose_landmarks.landmark
        
        def draw_arm_segment(start_idx, end_idx, num_segments=5):
            if (landmarks[start_idx].visibility > 0.5 and 
                landmarks[end_idx].visibility > 0.5):
                
                start_x = landmarks[start_idx].x * screen_width
                start_y = landmarks[start_idx].y * screen_height
                end_x = landmarks[end_idx].x * screen_width
                end_y = landmarks[end_idx].y * screen_height
                
                for i in range(num_segments + 1):
                    t = i / num_segments
                    x1 = int(start_x + (end_x - start_x) * t)
                    y1 = int(start_y + (end_y - start_y) * t)
                    
                    width = 20 if i in (0, num_segments) else 15
                    
                    pygame.draw.circle(screen, BODY_COLOR, (x1, y1), width // 2)
                    
                    if i > 0:
                        x0 = int(start_x + (end_x - start_x) * (i-1) / num_segments)
                        y0 = int(start_y + (end_y - start_y) * (i-1) / num_segments)
                        pygame.draw.line(screen, BODY_COLOR, (x0, y0), (x1, y1), width)

        draw_arm_segment(mp_pose.PoseLandmark.LEFT_SHOULDER.value,
                        mp_pose.PoseLandmark.LEFT_ELBOW.value)
        draw_arm_segment(mp_pose.PoseLandmark.LEFT_ELBOW.value,
                        mp_pose.PoseLandmark.LEFT_WRIST.value)
        
        draw_arm_segment(mp_pose.PoseLandmark.RIGHT_SHOULDER.value,
                        mp_pose.PoseLandmark.RIGHT_ELBOW.value)
        draw_arm_segment(mp_pose.PoseLandmark.RIGHT_ELBOW.value,
                        mp_pose.PoseLandmark.RIGHT_WRIST.value)
        
        if all(landmarks[i].visibility > 0.5 for i in [11, 12]):
            shoulder_points = [
                (int(landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER].x * screen_width),
                 int(landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER].y * screen_height)),
                (int(landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER].x * screen_width),
                 int(landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER].y * screen_height))
            ]
            pygame.draw.line(screen, BODY_COLOR, shoulder_points[0], shoulder_points[1], 25)

        torso_points = [
            (int(landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER].x * screen_width),
             int(landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER].y * screen_height)),
            (int(landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER].x * screen_width),
             int(landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER].y * screen_height)),
            (int(landmarks[mp_pose.PoseLandmark.RIGHT_HIP].x * screen_width),
             int(landmarks[mp_pose.PoseLandmark.RIGHT_HIP].y * screen_height)),
            (int(landmarks[mp_pose.PoseLandmark.LEFT_HIP].x * screen_width),
             int(landmarks[mp_pose.PoseLandmark.LEFT_HIP].y * screen_height))
        ]
        
        if all(landmarks[i].visibility > 0.5 for i in [11, 12, 23, 24]):
            pygame.draw.polygon(screen, BODY_COLOR, torso_points, 0)

        handle_gestures(pose_results.pose_landmarks)

    pygame.display.flip()

cap.release()
face_mesh.close()
pose.close()
pygame.quit()
