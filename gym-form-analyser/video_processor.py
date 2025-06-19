import cv2
import mediapipe as mp
import numpy as np
import time

class GymFormAnalyzer:
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
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

    def analyze_movement_phases(self, angles):
        """Analyze eccentric and concentric phases from angle data"""
        if len(angles) < 3:
            return [], []
        
        eccentric_angles = []  # Bottom of movement (smallest angles)
        concentric_angles = []  # Top of movement (largest angles)
        
        for i in range(1, len(angles) - 1):
            prev_angle = angles[i - 1]
            curr_angle = angles[i]
            next_angle = angles[i + 1]
            
            # Eccentric phase: current angle is smaller than both neighbors (local minimum)
            if curr_angle < prev_angle and curr_angle < next_angle:
                eccentric_angles.append(curr_angle)
            
            # Concentric phase: current angle is larger than both neighbors (local maximum)
            elif curr_angle > prev_angle and curr_angle > next_angle:
                concentric_angles.append(curr_angle)
        
        return eccentric_angles, concentric_angles

    def count_good_reps(self, eccentric_angles, concentric_angles):
        """Count good reps based on range of motion between phases"""
        if not eccentric_angles or not concentric_angles:
            return 0, 0
        
        # Pair up eccentric and concentric phases
        min_pairs = min(len(eccentric_angles), len(concentric_angles))
        good_reps = 0
        
        for i in range(min_pairs):
            # Calculate range of motion between eccentric and concentric
            rom = abs(concentric_angles[i] - eccentric_angles[i])
            
            # Good rep criteria: ROM between 80-100 degrees and eccentric angle shows good depth
            if 80 <= rom <= 100 and eccentric_angles[i] < 90:
                good_reps += 1
        
        total_reps = len(concentric_angles)  # Total reps = number of concentric phases
        return total_reps, good_reps

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
            
            # Squat depth analysis
            if knee_angle < 90:
                depth = "Deep squat - Excellent!"
            elif knee_angle < 110:
                depth = "Good squat depth"
            else:
                depth = "Squat deeper - go below 90°"
            
            return {
                'knee_angle': round(knee_angle, 1),
                'depth_feedback': depth,
                'exercise': 'squat'
            }
        except:
            return None

    def analyze_pullup(self, landmarks):
        """Analyze pull-up form"""
        try:
            # Get key points for pull-up analysis
            left_shoulder = [landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value].x,
                            landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
            left_elbow = [landmarks[self.mp_pose.PoseLandmark.LEFT_ELBOW.value].x,
                        landmarks[self.mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
            left_wrist = [landmarks[self.mp_pose.PoseLandmark.LEFT_WRIST.value].x,
                        landmarks[self.mp_pose.PoseLandmark.LEFT_WRIST.value].y]
            
            # Calculate elbow angle (for pull-up depth)
            elbow_angle = self.calculate_angle(left_shoulder, left_elbow, left_wrist)
            
            # Body alignment check (hip to shoulder)
            left_hip = [landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value].x,
                    landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value].y]
            
            # Check if chin is above bar level (wrist level approximation)
            chin_y = landmarks[self.mp_pose.PoseLandmark.NOSE.value].y
            bar_level_y = left_wrist[1]  # Approximate bar level
            chin_above_bar = chin_y < bar_level_y
            
            # Pull-up form analysis
            if elbow_angle < 90 and chin_above_bar:
                form = "Excellent pull-up! Full range of motion"
            elif elbow_angle < 120:
                form = "Good pull-up, try to get chin higher"
            elif chin_above_bar:
                form = "Good height, but pull elbows closer"
            else:
                form = "Pull higher - get chin above bar"
            
            return {
                'elbow_angle': round(elbow_angle, 1),
                'chin_above_bar': chin_above_bar,
                'form_feedback': form,
                'exercise': 'pullup'
            }
        except:
            return None

    def analyze_bench(self, landmarks):
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
            
            # Check bar path (wrist should be above elbow at bottom)
            wrist_above_elbow = left_wrist[1] < left_elbow[1]
            
            # Check if elbows are too flared (shoulder-elbow-wrist angle)
            elbow_flare_angle = self.calculate_angle(left_shoulder, left_elbow, left_wrist)
            
            # Bench press form analysis
            if elbow_angle < 90 and wrist_above_elbow:
                form = "Good bench press depth and bar path!"
            elif elbow_angle < 90:
                form = "Good depth, check bar path over chest"
            elif wrist_above_elbow:
                form = "Good bar path, go deeper to chest"
            elif elbow_flare_angle > 160:
                form = "Elbows too flared - tuck them in more"
            else:
                form = "Focus on form: deeper range, bar to chest"
            
            return {
                'elbow_angle': round(elbow_angle, 1),
                'bar_path_good': wrist_above_elbow,
                'elbow_flare_angle': round(elbow_flare_angle, 1),
                'form_feedback': form,
                'exercise': 'bench'
            }
        except:
            return None

    def process_video(self, input_source, output_path, exercise_type="squat"):
        """Process video and analyze form with throttling - works with S3 URLs or local files"""
        cap = cv2.VideoCapture(input_source)  # OpenCV can handle URLs directly
        
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        analysis_results = []
        frame_count = 0
        last_process_time = 0
        throttle_interval = 0.1  # Process every 0.1 seconds
        
        while cap.isOpened():
            success, image = cap.read()
            if not success:
                break
            
            frame_count += 1
            current_time = time.time()
            
            # Throttling: only process every 0.1 seconds
            should_process = (current_time - last_process_time) >= throttle_interval
            
            if should_process:
                last_process_time = current_time
                
                # Convert BGR to RGB
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
                        analysis = self.analyze_pullup(results.pose_landmarks.landmark)
                    elif exercise_type == "bench":
                        analysis = self.analyze_bench(results.pose_landmarks.landmark)
                    else:
                        analysis = None
                    
                    if analysis:
                        analysis['frame'] = frame_count
                        analysis['timestamp'] = current_time
                        analysis_results.append(analysis)
                        
                        # Draw analysis on frame based on exercise
                        if exercise_type == "squat":
                            cv2.putText(image, f"Knee Angle: {analysis['knee_angle']}°", 
                                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                            cv2.putText(image, analysis['depth_feedback'], 
                                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        
                        elif exercise_type == "pullup":
                            cv2.putText(image, f"Elbow Angle: {analysis['elbow_angle']}°", 
                                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                            cv2.putText(image, f"Chin Above Bar: {'Yes' if analysis['chin_above_bar'] else 'No'}", 
                                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                            cv2.putText(image, analysis['form_feedback'], 
                                    (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        
                        elif exercise_type == "bench":
                            cv2.putText(image, f"Elbow Angle: {analysis['elbow_angle']}°", 
                                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                            cv2.putText(image, f"Bar Path: {'Good' if analysis['bar_path_good'] else 'Check'}", 
                                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                            cv2.putText(image, analysis['form_feedback'], 
                                    (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            out.write(image)
        
        cap.release()
        out.release()
        
        # Generate summary
        summary = self.generate_summary(analysis_results, exercise_type)
        
        return {
            'processed_video': output_path,
            'analysis_results': analysis_results,
            'summary': summary
        }

    def generate_summary(self, results, exercise_type):
        """Generate analysis summary with eccentric/concentric analysis"""
        if not results:
            return "No pose detected in video"

        if exercise_type == "squat":
            angles = [r['knee_angle'] for r in results]
            eccentric_angles, concentric_angles = self.analyze_movement_phases(angles)
            total_reps, good_reps = self.count_good_reps(eccentric_angles, concentric_angles)
            bad_reps = total_reps - good_reps
            
            avg_eccentric = np.mean(eccentric_angles) if eccentric_angles else 0
            avg_concentric = np.mean(concentric_angles) if concentric_angles else 0

            return {
                'exercise': 'squat',
                'total_frames_analyzed': len(results),
                'average_angle_at_concentric': round(avg_concentric, 1),
                'average_angle_at_eccentric': round(avg_eccentric, 1),
                'overall_feedback': (
                    f"{'Great form!' if good_reps == total_reps and total_reps > 0 else 'Try to maintain consistent depth'} "
                    f"(Reps: {good_reps} good / {bad_reps} bad)"
                )
            }

        elif exercise_type == "pullup":
            angles = [r['elbow_angle'] for r in results]
            eccentric_angles, concentric_angles = self.analyze_movement_phases(angles)
            total_reps, good_reps = self.count_good_reps(eccentric_angles, concentric_angles)
            bad_reps = total_reps - good_reps
            
            avg_eccentric = np.mean(eccentric_angles) if eccentric_angles else 0
            avg_concentric = np.mean(concentric_angles) if concentric_angles else 0
            chin_above_count = sum(1 for r in results if r.get('chin_above_bar', False))
            completion_rate = (chin_above_count / len(results)) * 100 if results else 0

            return {
                'exercise': 'pullup',
                'total_frames_analyzed': len(results),
                'average_angle_at_concentric': round(avg_concentric, 1),
                'average_angle_at_eccentric': round(avg_eccentric, 1),
                'chin_above_bar_rate': round(completion_rate, 1),
                'overall_feedback': (
                    f"{'Excellent pull-ups!' if good_reps == total_reps and total_reps > 0 else 'Focus on full range pull-ups'} "
                    f"(Reps: {good_reps} good / {bad_reps} bad)"
                )
            }

        elif exercise_type == "bench":
            angles = [r['elbow_angle'] for r in results]
            eccentric_angles, concentric_angles = self.analyze_movement_phases(angles)
            total_reps, good_reps = self.count_good_reps(eccentric_angles, concentric_angles)
            bad_reps = total_reps - good_reps
            
            avg_eccentric = np.mean(eccentric_angles) if eccentric_angles else 0
            avg_concentric = np.mean(concentric_angles) if concentric_angles else 0
            good_bar_path_count = sum(1 for r in results if r.get('bar_path_good', False))
            bar_path_rate = (good_bar_path_count / len(results)) * 100 if results else 0

            return {
                'exercise': 'bench',
                'total_frames_analyzed': len(results),
                'average_angle_at_concentric': round(avg_concentric, 1),
                'average_angle_at_eccentric': round(avg_eccentric, 1),
                'good_bar_path_rate': round(bar_path_rate, 1),
                'overall_feedback': (
                    f"{'Great bench form!' if good_reps == total_reps and total_reps > 0 else 'Improve range of motion consistency'} "
                    f"(Reps: {good_reps} good / {bad_reps} bad)"
                )
            }

        return "Analysis complete"