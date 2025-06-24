import cv2
import mediapipe as mp
import numpy as np
import json
import os
from config import Config
import google.generativeai as genai
import logging
from typing import List, Literal

logger = logging.getLogger(__name__)

# UTILITY FUNCTIONS
def get_visible_side(lm, left_idx, right_idx):
    """Returns the index of the more visible landmark."""
    return left_idx if lm[left_idx][3] >= lm[right_idx][3] else right_idx
def count_reps_and_track_extremes(angles, states):
    good_reps = 0
    total_reps = 0

    peak_angles = []
    descent_angles = []

    last_bot_idx = None

    for i in range(len(states)):
        state = states[i]

        # Track the index of the most recent BOT
        if state == "BOT":
            last_bot_idx = i

        # If we reach a TOP after a BOT, count as rep
        elif state == "TOP" and last_bot_idx is not None:
            bot_angle = angles[last_bot_idx]
            top_angle = angles[i]

            total_reps += 1
            if bot_angle <= 90 and top_angle >= 160:
                good_reps += 1

            last_bot_idx = None  # reset for next rep

        # Track local max/min for angle trends
        if 0 < i < len(angles) - 1:
            prev_a, curr_a, next_a = angles[i - 1], angles[i], angles[i + 1]
            if curr_a > prev_a and curr_a > next_a:
                peak_angles.append(curr_a)
            elif curr_a < prev_a and curr_a < next_a:
                descent_angles.append(curr_a)

    avg_peak = sum(peak_angles) / len(peak_angles) if peak_angles else None
    avg_descent = sum(descent_angles) / len(descent_angles) if descent_angles else None

    return {
        'good_reps': str(good_reps),
        'bad_reps': str(total_reps - good_reps),
        'total_reps': str(total_reps),
        'avg_peak_angle': round(avg_peak, 2) if avg_peak is not None else -1,
        'avg_descent_angle': round(avg_descent, 2) if avg_descent is not None else -1
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
        # Configure Gemini API once during initialization
        try:
            if not Config.GEMINI_API_KEY:
                raise ValueError("Gemini API Key is not set in Config.")
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.gemini_model = genai.GenerativeModel("models/gemini-2.5-flash")
            logger.info("Gemini API configured successfully using models/gemini-2.5-flash.")
        except Exception as e:
            logger.error(f"Failed to configure Gemini API: {e}. Gemini feedback will be unavailable.")
            self.gemini_model = None # Set to None if configuration fails

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
    Landmarks = List[List[List[float]]]  # Each frame: 33 landmarks [x, y, z]
    States = List[Literal["top", "mid", "bot"]]
    Exercise = Literal["squat", "pushups", "pullups"]

    def evaluate_form(self, landmarks: Landmarks, states: States, exercise: Exercise) -> float:
        
        if len(states) < 3:
            return 0.0
        if len(landmarks) != len(states):
            return 0.0
       

        

        # Define landmark indices for each key joint (both left and right)
        indices = {
            "nose": 0,
            "left_shoulder": 11,
            "right_shoulder": 12,
            "left_hip": 23,
            "right_hip": 24,
            "left_knee": 25,
            "right_knee": 26,
            "left_ankle": 27,
            "right_ankle": 28,
            "left_elbow": 13,
            "right_elbow": 14,
            "left_wrist": 15,
            "right_wrist": 16
        }

        scores = []

        for i, lm in enumerate(landmarks):
            state = states[i]

            # Function to select best side based on visibility
            def select_best_side(left_idx, right_idx):
                left_vis = lm[left_idx][3] if len(lm[left_idx]) > 3 else lm[left_idx].visibility
                right_vis = lm[right_idx][3] if len(lm[right_idx]) > 3 else lm[right_idx].visibility
                return left_idx if left_vis >= right_vis else right_idx

            # Select most visible side for each joint
            shoulder_idx = select_best_side(indices["left_shoulder"], indices["right_shoulder"])
            hip_idx = select_best_side(indices["left_hip"], indices["right_hip"])
            knee_idx = select_best_side(indices["left_knee"], indices["right_knee"])
            ankle_idx = select_best_side(indices["left_ankle"], indices["right_ankle"])
            elbow_idx = select_best_side(indices["left_elbow"], indices["right_elbow"])
            wrist_idx = select_best_side(indices["left_wrist"], indices["right_wrist"])

            # Required landmark indices based on exercise and state
            required = [indices["nose"], shoulder_idx, hip_idx, knee_idx]

            if exercise != "squats":
                required += [elbow_idx, wrist_idx]

            if exercise == "pushups":
                required += [ankle_idx]
            if any(lm[idx][3] < 0.7 for idx in required):
                continue

            # Angles using selected sides
            spinal_angle = self.calculate_angle(lm[indices["nose"]], lm[shoulder_idx], lm[hip_idx])
            hip_angle = self.calculate_angle(lm[shoulder_idx], lm[hip_idx], lm[knee_idx])

            spinal_score = 1.0 if 140 <= spinal_angle <= 170 else max(0.0, 1-abs(spinal_angle-155)/155)
           
            if exercise == "squats":
                hip_score = 1.0 if 70 <= hip_angle <= 100 else max(0.0, 1-abs(hip_angle-85)/85)
            else:
                hip_score = 1.0 if 160 <= hip_angle <= 180 else max(0.0, 1-abs(hip_angle -170)/170)
           

            # Joint scoring using selected sides
            joint_score = 1.0
            if state in ["TOP", "BOT"]:
                if exercise == "squats":
                    joint_angle = self.calculate_angle(lm[hip_idx], lm[knee_idx], lm[ankle_idx])
                else:
                    joint_angle = self.calculate_angle(lm[shoulder_idx], lm[elbow_idx], lm[wrist_idx])

                if state == "BOT":
                    joint_score = 1.0 if joint_angle <= 90 else -1.0
                elif state == "TOP":  # top
                    joint_score = 1.0 if joint_angle >= 160 else -1.0
                else:
                    joint_score = 1.0

            # Extra for pushups using selected side
            extra_score = 1.0
            if exercise == "pushups":
                leg_line_angle = self.calculate_angle(lm[hip_idx], lm[knee_idx], lm[ankle_idx])
                extra_score = 1.0 if 140 <= leg_line_angle <= 180 else max(0.0, 1 - (140 - leg_line_angle)/140)

            # Final score
            if state not in ["TOP","BOT"]:
                
                score = (spinal_score +hip_score +extra_score) if exercise == "pushups" else (spinal_score +hip_score)
                score = score/3 if exercise == "pushups" else score/2
            else:
                
                score = (joint_score)
                
            scores.append(score)

        return max(0.100,round(np.mean(scores),3)) if scores else 0.0
    

    def analyze_squat(self, landmarks):
        try:
            PL = self.mp_pose.PoseLandmark

# Check visibilities
            hip_vis = landmarks[PL.LEFT_HIP.value].visibility
            knee_vis = landmarks[PL.LEFT_KNEE.value].visibility
            ankle_vis = landmarks[PL.LEFT_ANKLE.value].visibility

            right_hip_vis = landmarks[PL.RIGHT_HIP.value].visibility
            right_knee_vis = landmarks[PL.RIGHT_KNEE.value].visibility
            right_ankle_vis = landmarks[PL.RIGHT_ANKLE.value].visibility

            # Use side with higher visibility, but only if one is confidently visible
            if max(hip_vis, right_hip_vis) < 0.7 or max(knee_vis, right_knee_vis) < 0.7 or max(ankle_vis, right_ankle_vis) < 0.7:
                return None  # or handle as a skipped frame

            # Select most visible side for each
            hip = [landmarks[PL.LEFT_HIP.value].x, landmarks[PL.LEFT_HIP.value].y] \
                if hip_vis >= right_hip_vis else \
                [landmarks[PL.RIGHT_HIP.value].x, landmarks[PL.RIGHT_HIP.value].y]

            knee = [landmarks[PL.LEFT_KNEE.value].x, landmarks[PL.LEFT_KNEE.value].y] \
                if knee_vis >= right_knee_vis else \
                [landmarks[PL.RIGHT_KNEE.value].x, landmarks[PL.RIGHT_KNEE.value].y]

            ankle = [landmarks[PL.LEFT_ANKLE.value].x, landmarks[PL.LEFT_ANKLE.value].y] \
                if ankle_vis >= right_ankle_vis else \
                [landmarks[PL.RIGHT_ANKLE.value].x, landmarks[PL.RIGHT_ANKLE.value].y]

            # Compute angle
            knee_angle = self.calculate_angle(hip, knee, ankle)
            return {'angleToCheck': round(knee_angle, 3)}
        except Exception as e:
            logger.warning(f"Failed to analyze squat landmarks: {e}")
            return None


    def analyze_bench_or_pull(self, landmarks):
        try:
            PL = self.mp_pose.PoseLandmark

            # Check visibilities
            left_shoulder_vis = landmarks[PL.LEFT_SHOULDER.value].visibility
            right_shoulder_vis = landmarks[PL.RIGHT_SHOULDER.value].visibility
            left_elbow_vis = landmarks[PL.LEFT_ELBOW.value].visibility
            right_elbow_vis = landmarks[PL.RIGHT_ELBOW.value].visibility
            left_wrist_vis = landmarks[PL.LEFT_WRIST.value].visibility
            right_wrist_vis = landmarks[PL.RIGHT_WRIST.value].visibility

            # Require at least one confident side
            if max(left_shoulder_vis, right_shoulder_vis) < 0.7 or \
            max(left_elbow_vis, right_elbow_vis) < 0.7 or \
            max(left_wrist_vis, right_wrist_vis) < 0.7:
                return None

            # Pick more visible side for each point
            shoulder = [landmarks[PL.LEFT_SHOULDER.value].x, landmarks[PL.LEFT_SHOULDER.value].y] \
                if left_shoulder_vis >= right_shoulder_vis else \
                [landmarks[PL.RIGHT_SHOULDER.value].x, landmarks[PL.RIGHT_SHOULDER.value].y]

            elbow = [landmarks[PL.LEFT_ELBOW.value].x, landmarks[PL.LEFT_ELBOW.value].y] \
                if left_elbow_vis >= right_elbow_vis else \
                [landmarks[PL.RIGHT_ELBOW.value].x, landmarks[PL.RIGHT_ELBOW.value].y]

            wrist = [landmarks[PL.LEFT_WRIST.value].x, landmarks[PL.LEFT_WRIST.value].y] \
                if left_wrist_vis >= right_wrist_vis else \
                [landmarks[PL.RIGHT_WRIST.value].x, landmarks[PL.RIGHT_WRIST.value].y]

            # Compute angle
            elbow_angle = self.calculate_angle(shoulder, elbow, wrist)
            return {'angleToCheck': round(elbow_angle, 3)}
        except Exception as e:
            logger.warning(f"Failed to analyze bench/pull landmarks: {e}")
            return None

    def process_video(self, input_source, output_path=None, exercise_type="squat"):
        cap = cv2.VideoCapture(input_source)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v') # Use mp4v or XVID for better compatibility
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        else:
            out = None

        frame_count = 0
        throttleValue = 0
        frameSkipped = 2 # Process every 3rd frame
        list_of_frames = [] # Stores angles per relevant frame
        list_of_states = [] # Stores states (TOP/MID/BOT) per relevant frame
        keypoint_series = [] # Stores all landmark data for Gemini
        keypointSeriesForImportantFrames = []
        lastPeakOrDescent = 'MID'
        while cap.isOpened():
            success, image = cap.read()
            if not success:
                break
            frame_count += 1
            if (frame_count - 1) % (frameSkipped + 1) == 0:  # process every 3rd frame
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                image_rgb.flags.writeable = False
                results = self.pose.process(image_rgb)
                image_rgb.flags.writeable = True
                
                if results.pose_landmarks:
                    landmarks = results.pose_landmarks.landmark
                    landmarks = results.pose_landmarks.landmark
                    # Optimized keypoint data for Gemini to reduce token count
                    
                    if exercise_type == "squats":
                        analysis = self.analyze_squat(landmarks)
                    elif exercise_type in ["pullups", "pushups"]:
                        analysis = self.analyze_bench_or_pull(landmarks)
                    else:
                        analysis = None

                    angleOfCurrentState = analysis['angleToCheck'] if analysis else 0
                    if len(list_of_frames) == 0:
                        list_of_frames = [angleOfCurrentState]
                        list_of_states = ['MID']
                        keypointSeriesForImportantFrames.append([
                            [round(lm.x, 3), round(lm.y, 3), round(lm.z, 3), round(lm.visibility, 3)]
                            for lm in landmarks
                        ])

                    elif abs(list_of_frames[len(list_of_frames)-1] - angleOfCurrentState) > 5:
                        
                        keypointSeriesForImportantFrames.append([
                            [round(lm.x, 3), round(lm.y, 3), round(lm.z, 3), round(lm.visibility, 3)]
                            for lm in landmarks
                        ])
                        
                        lastStateIndex = len(list_of_states)-1
                        lastState = list_of_states[lastStateIndex]
                        lastAngleIndex = len(list_of_frames)-1
                        lastAngle = list_of_frames[lastAngleIndex]
                        list_of_frames.append(angleOfCurrentState)
                        if lastState == 'TOP':
                            if angleOfCurrentState < lastAngle:
                                list_of_states.append('MID')
                                #top means apex of ROM or eccentric stage so next is mid
                                
                            else:
                                list_of_states[lastAngleIndex] = 'MID'
                                #convert it to a transition
                                list_of_states.append('TOP')
                                
                                #mid simply signifies a transition not necessarily the angle
                        elif lastState == 'BOT':
                            if angleOfCurrentState > lastAngle:
                                list_of_states.append('MID')
                                
                            else:
                                list_of_states[lastAngleIndex] = 'MID'
                               
                                list_of_states.append('BOT')
                                #BOT means concentric stage or the bottom

                                
                        else:
                            if angleOfCurrentState < lastAngle  and lastPeakOrDescent == 'TOP':
                                lastPeakOrDescent = 'TOP'
                                #convert it to a transition
                                list_of_states.append('MID')
                                #top means apex of ROM or eccentric stage
                                #as you can see I copy pasted a ton
                            elif angleOfCurrentState > lastAngle and lastPeakOrDescent == 'BOT':
                                lastPeakOrDescent = 'BOT'
                                list_of_states.append('MID')

                            else:
                                if angleOfCurrentState < lastAngle  and lastPeakOrDescent != 'TOP':
                                    lastPeakOrDescent = 'TOP'
                                    #the current value implies descending
                                    list_of_states[lastAngleIndex] = 'MID'
                                    
                                    list_of_states.append('BOT')
                                
                                elif angleOfCurrentState > lastAngle and lastPeakOrDescent != 'BOT':
                                    lastPeakOrDescent = 'BOT'
                                    #the current value implies ascending
                                    list_of_states[lastAngleIndex] = 'MID'
                                    list_of_states.append('TOP') 
                    keypoint_series.append([
                        {
                            'x': round(lm.x, 3), # Round to 3 decimal places
                            'y': round(lm.y, 3), # Round to 3 decimal places
                            # 'z': round(lm.z, 3), # Removed 'z' for further token reduction
                            # 'visibility': round(lm.visibility, 2) # Removed 'visibility' for token reduction
                        }
                        for lm in landmarks
                        ])
                    
                    currentState = list_of_states[len(list_of_states)-1]
                    if analysis and out: # Only draw if analysis was successful and output video is enabled
                        all_states_labels = ['TOP', 'MID', 'BOT']
                        currentState = all_states_labels.index(currentState)
                        colourTuple = (255 if currentState == 0 else 0, # Blue for TOP
                                        255 if currentState == 1 else 0, # Green for MID
                                        255 if currentState == 2 else 0) # Red for BOT
                        cv2.putText(image, f"Angle: {round(angleOfCurrentState, 1)} deg", (10, 50),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, colourTuple, 2)
                        cv2.putText(image, all_states_labels[currentState], (10, 100),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, colourTuple, 2)
                        self.mp_drawing.draw_landmarks(
                        image,
                        results.pose_landmarks,
                        self.mp_pose.POSE_CONNECTIONS,
                        landmark_drawing_spec=self.mp_drawing.DrawingSpec(color=(0,255,0), thickness=2, circle_radius=2),
                        connection_drawing_spec=self.mp_drawing.DrawingSpec(color=(0,0,255), thickness=2, circle_radius=2)
                        )

                if out:
                    out.write(image)

        cap.release()
        if out:
            out.release()
        score = self.evaluate_form(keypointSeriesForImportantFrames, list_of_states, exercise_type)
        summary = self.generate_summary(list_of_frames, list_of_states, exercise_type,score)
        gemini_feedback = self.send_to_gemini(keypoint_series, exercise_type)

        return {
            'processed_video': output_path if output_path else None,
            'summary': summary,
            'gemini_feedback': gemini_feedback
        }

    def send_to_gemini(self, landmarks_series, exercise_type):
        if not self.gemini_model:
            # Changed return type to dictionary to match successful JSON output structure
            return {"error": "Gemini API not configured. Cannot provide AI feedback."}

        # Reduced max_sample_frames for more aggressive token reduction
        max_sample_frames = 25 # Target 25 frames for testing, adjust as needed
        sample_frames = landmarks_series[::max(1, len(landmarks_series) // max_sample_frames)]
        if len(sample_frames) > max_sample_frames:
            sample_frames = sample_frames[:max_sample_frames]

        # MODIFIED PROMPT: Explicitly instructing Gemini for JSON output with schema
        prompt = f"""
        You are a virtual fitness coach specialized in analyzing exercise form.
        The user has performed a {exercise_type}. I will provide you with a series of pose keypoints (x, y) for various frames.
        Each frame contains data for 33 body keypoints, normalized to the image size (0.0 to 1.0).

        Please provide a **concise and summarized analysis** of the {exercise_type} form, focusing on the most critical points.
        Your response MUST be in JSON format, strictly following the schema provided below.
        Do NOT include any other text or markdown outside the JSON object.
        Embed relevant emojis directly into the string values where appropriate to add visual appeal.

        **JSON Schema:**
        ```json
        {{
          "title": "Gym Form Analysis - {exercise_type.capitalize()}",
          "strengths": [
            "string",
            "string"
          ],
          "areas_for_improvement": [
            "string",
            "string"
          ],
          "actionable_tips": [
            "string",
            "string",
            "string"
          ],
          "overall_assessment": "string"
        }}
        ```
        -   **title**: A short, descriptive title for the analysis.
        -   **strengths**: An array of 1-2 concise bullet points highlighting key good aspects. Each string should be self-contained.
        -   **areas_for_improvement**: An array of 1-2 concise bullet points for critical areas needing work. Each string should be self-contained.
        -   **actionable_tips**: An array of 1-3 concise, concrete, actionable advice points. Each string should be self-contained.
        -   **overall_assessment**: A very brief, encouraging summary sentence.

        Analyze the movement over time. Pay attention to joint angles, range of motion, and consistency based on the x and y coordinates provided.

        Here is a sample of the pose data (list of dictionaries, each dictionary represents a frame's 33 keypoints):
        {json.dumps(sample_frames, indent=2)}
        """
        try:
            chat = self.gemini_model.start_chat()
            # CRUCIAL: Set response_mime_type to application/json
            response = chat.send_message(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json"
                )
            )
            # Parse the JSON string from the response
            feedback_data = json.loads(response.text)
            return feedback_data # Return the parsed dictionary
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing Gemini JSON response: {e}. Raw response: {response.text if 'response' in locals() else 'N/A'}")
            # Return an error dictionary that your frontend can check for
            return {"error": f"AI response malformed. Failed to parse JSON: {e}"}
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            # Return an error dictionary
            return {"error": f"Error getting feedback from AI: {str(e)}. Please check API key and network."}

    def generate_summary(self, frameSet, stateSet, exercise_type,score = 0):
        frameSkipped = 2 # Assuming this is consistent with how frames were skipped during processing
        if not frameSet:
            return {
                'exercise': exercise_type,
                'total_frames_analyzed': '0',
                'overall_feedback': "No pose detected in video. Please ensure the person is visible and well-lit.",
                'good_reps': '0',
                'bad_reps': '0',
                'total_reps': '0',
                'avg_peak_angle': '-1',
                'avg_descent_angle': '-1',
                'score': "0"
            }

        returnedValue = count_reps_and_track_extremes(frameSet, stateSet)

        # General feedback template
        feedback = "Analysis complete."
        if exercise_type == "squats":
            feedback = "Great squat form!" if returnedValue['avg_descent_angle'] <= 90 and returnedValue['avg_descent_angle'] != -1 else "Try to squat deeper! Aim for knees around 90 degrees or below."
        elif exercise_type == "pullups":
            feedback = "Excellent pull-up depth!" if returnedValue['avg_descent_angle'] <= 90 and returnedValue['avg_descent_angle'] != -1 else "Ensure full extension at the bottom of the pull-up."
        elif exercise_type == "pushups":
            feedback = "Good push up depth!" if returnedValue['avg_descent_angle'] <= 90 and returnedValue['avg_descent_angle'] != -1 else "Try to go lower for a full range of motion."

        return {
            'exercise': exercise_type,
            'total_frames_analyzed': str(len(frameSet) * (frameSkipped + 1)), # +1 because 0-index skipped frames
            'average_peak_angle': str(returnedValue['avg_peak_angle']),
            'average_descent_angle': str(returnedValue['avg_descent_angle']),
            'good_reps': returnedValue['good_reps'],
            'bad_reps': returnedValue['bad_reps'],
            'total_reps': returnedValue['total_reps'],
            'overall_feedback': feedback,
            'score' : str(score) if score > 0.1 else "0"
        }