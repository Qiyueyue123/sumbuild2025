import cv2
import mediapipe as mp
import numpy as np
import json
import os

 #The number of frames you skip before analyzing the next frame. Dont put it too high or its not reflected well


#UTILITY FUNCTIONS

def count_reps_and_track_extremes(angles, states):
        good_reps = 0
        total_reps = 0
        state_buffer = []

        peak_angles = []
        descent_angles = []

        for i in range(len(states)):
            state = states[i]
            if len(state_buffer) == 0 or state != state_buffer[len(state_buffer)-1]:
                state_buffer.append(state)

            if len(state_buffer) > 3:
                state_buffer.pop(0)

            pattern = ''.join(state_buffer)

            if pattern == 'TOPMIDBOT':
                good_reps += 1
                total_reps += 1
                state_buffer = []

            elif len(state_buffer) >= 2 and ''.join(state_buffer[-2:]) == 'MIDBOT':
                total_reps += 1
                state_buffer = []

            elif len(state_buffer) == 3 and ''.join(state_buffer) == 'TOPMIDTOP':
                total_reps += 1
                state_buffer = []

            # Use 3-point local max/min check: angle[i-1], angle[i], angle[i+1]
            if 0 < i < len(angles) - 1:
                prev_a, curr_a, next_a = angles[i-1], angles[i], angles[i+1]
                if curr_a > prev_a and curr_a > next_a:
                    peak_angles.append(curr_a)
                elif curr_a < prev_a and curr_a < next_a:
                    descent_angles.append(curr_a)

        # Calculate averages
        avg_peak = sum(peak_angles) / len(peak_angles) if peak_angles else None
        avg_descent = sum(descent_angles) / len(descent_angles) if descent_angles else None

        return {
            'good_reps': str(good_reps),
            'bad_reps': str(total_reps-good_reps),
            'total_reps': str(total_reps),
            'avg_peak_angle': round(avg_peak, 2), 
            'avg_descent_angle': round(avg_descent, 2) 
        }





class GymFormAnalyzer:
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
    
    def calculate_angle(self, point1, point2, point3):
        """Calculate angle between three points"""
        a = np.array(point1)
        b = np.array(point2)
        c = np.array(point3)
        
        radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
        angle = np.abs(radians * 180.0 / np.pi)
        
        if angle > 180.0:
            angle = 360 - angle
        
        return angle
    
    def analyze_squat(self, landmarks):
        """Analyze squat form"""
        try:
            # Get key points
            hip = [landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value].x,
                   landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value].y]
            knee = [landmarks[self.mp_pose.PoseLandmark.LEFT_KNEE.value].x,
                    landmarks[self.mp_pose.PoseLandmark.LEFT_KNEE.value].y]
            ankle = [landmarks[self.mp_pose.PoseLandmark.LEFT_ANKLE.value].x,
                     landmarks[self.mp_pose.PoseLandmark.LEFT_ANKLE.value].y]
            
            # Calculate knee angle
            knee_angle = self.calculate_angle(hip, knee, ankle)
            return {
                'angleToCheck': round(knee_angle, 1),
            }
        except:
            return None
    def analyze_bench_or_pull(self, landmarks):
        """Analyze bench press form"""
        try:
            # Get key points for bench press
            left_shoulder = [landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value].x,
                            landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
            left_elbow = [landmarks[self.mp_pose.PoseLandmark.LEFT_ELBOW.value].x,
                         landmarks[self.mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
            left_wrist = [landmarks[self.mp_pose.PoseLandmark.LEFT_WRIST.value].x,
                         landmarks[self.mp_pose.PoseLandmark.LEFT_WRIST.value].y]
            
            # Calculate elbow angle
            elbow_angle = self.calculate_angle(left_shoulder, left_elbow, left_wrist)
            
            return {
                'angleToCheck' : elbow_angle
            }
        except:
            return None
    
    def process_video(self, input_source, output_path, exercise_type="squat"):
        """Process video and analyze form - works with S3 URLs or local files"""
        cap = cv2.VideoCapture(input_source)  # OpenCV can handle URLs directly
        
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        throttleValue = 0
        frameSkipped = 2
        analysis_results = []
        frame_count = 0
        list_of_frames = []
        list_of_states = []
        
        while cap.isOpened():
            success, image = cap.read()
            if not success:
                break
            
            frame_count += 1
            if frame_count - throttleValue > frameSkipped:
                # Convert BGR to RGB
                throttleValue = frame_count
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                image_rgb.flags.writeable = False
                
                # Process with MediaPipe
                results = self.pose.process(image_rgb)
                
                # Convert back to BGR
                image_rgb.flags.writeable = True
                image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
                
                # Analyze pose if detected
                if results.pose_landmarks:
                    # Draw pose landmarks
                    self.mp_drawing.draw_landmarks(
                        image, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)
                    
                    # Analyze form based on exercise type
                    if exercise_type == "squat":
                        analysis = self.analyze_squat(results.pose_landmarks.landmark)
                    elif exercise_type == "pullup":
                        analysis = self.analyze_bench_or_pull(results.pose_landmarks.landmark)
                    elif exercise_type == "bench":
                        analysis = self.analyze_bench_or_pull(results.pose_landmarks.landmark)
                    else:
                        analysis = None
                    angleOfCurrentState = analysis['angleToCheck'] if analysis else 0

                    #0 is just defaulting to the bottom state
                    list_of_frames.append(angleOfCurrentState)
                    currentState = 2
                    if(angleOfCurrentState > 150):
                        #implies that it is at the top
                        currentState = 0
                        list_of_states.append('TOP')
                    elif(angleOfCurrentState > 100):
                        #implies that it is at the mid point
                        currentState = 1
                        list_of_states.append('MID')
                    else:
                        #quote on quote rest state
                        currentState = 2
                        list_of_states.append('BOT')

                    if analysis:
                        analysis_results.append(analysis)
                        
                        # Draw analysis on frame based on exercise
                        if exercise_type == "squat" or exercise_type == "pullup" or exercise_type == "bench":
                            allStates = ['TOP','MID','BOT']
                            colourTuple = (255 if currentState == 0 else 0,255 if currentState == 1 else 0,255 if currentState == 2 else 0)
                            cv2.putText(image, f"Key Joint Angle: {round(angleOfCurrentState,4)}°", 
                                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, colourTuple, 2)
                            cv2.putText(image, allStates[currentState], 
                                    (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, colourTuple, 2)
                
                out.write(image)
            
            
            
            # Generate summary
        cap.release()
        out.release()
        summary = self.generate_summary(list_of_frames,list_of_states, exercise_type)
        return {
            'processed_video': output_path,
            'analysis_results': analysis_results,
            'summary': summary
        }
   
        
    def generate_summary(self, frameSet, stateSet, exercise_type):
        frameSkipped = 2
        if not frameSet:
            return "No pose detected in video"
        returnedValue = {
            'good_reps': '0',
            'bad_reps': '0',
            'total_reps': '0',
            'avg_peak_angle': -1,
            'avg_descent_angle': -1,
        }
        returnedValue = count_reps_and_track_extremes(frameSet,stateSet)
        


# {
#             'good_reps': good_reps,
#             'bad_reps': total_reps-good_reps,
#             'total_reps':total_reps,
#             'avg_peak_angle': avg_peak,
#             'avg_descent_angle': avg_descent,
#         }









        if exercise_type == "squat":
            
            return {
                'exercise': 'squat',
                'total_frames_analyzed': str(len(frameSet)*frameSkipped),
                'average_peak_angle': str(returnedValue['avg_peak_angle']),
                'average_descent_angle':str(returnedValue['avg_descent_angle']),
                'overall_feedback': "Great form!" if returnedValue['avg_descent_angle'] < 90 else "Try to squat deeper! \n"
                                    + f" total reps: {returnedValue['total_reps']}, good reps: {returnedValue['good_reps']}, bad reps: {returnedValue['bad_reps']}"
            }
        
        elif exercise_type == "pullup":
            return {'exercise': 'pull',
                    'total_frames_analyzed': str(len(frameSet)*frameSkipped),
                    'average_peak_angle': str(returnedValue['avg_peak_angle']),
                    'average_descent_angle':str(returnedValue['avg_descent_angle']),
                    'overall_feedback': "Great form!" if returnedValue['avg_descent_angle'] < 90 else "Try to stretch at the bottom more! \n"
                                       + f" total reps: {returnedValue['total_reps']}, good reps: {returnedValue['good_reps']}, bad reps: {returnedValue['bad_reps']}"
            }
        elif exercise_type == "bench":
            
            return {'exercise': 'bench',
                    'total_frames_analyzed': str(len(frameSet)*frameSkipped),
                    'average_peak_angle': str(returnedValue['avg_peak_angle']),
                    'average_descent_angle':str(returnedValue['avg_descent_angle']),
                    'overall_feedback': "Great form!" if returnedValue['avg_descent_angle'] < 90 else "Try to go lower on the bench! \n"
                                       + f" total reps: {returnedValue['total_reps']}, good reps: {returnedValue['good_reps']}, bad reps: {returnedValue['bad_reps']}"
            }
        return "Analysis complete"