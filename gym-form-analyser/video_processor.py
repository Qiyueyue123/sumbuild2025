import cv2
import mediapipe as mp
import numpy as np
import json
import os
from config import Config
import google.generativeai as genai
import logging

logger = logging.getLogger(__name__)

# UTILITY FUNCTIONS

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

        # Repetition logic for various patterns
        if pattern == 'TOPMIDBOT':
            good_reps += 1
            total_reps += 1
            state_buffer = [] # Reset buffer after a successful rep
        elif len(state_buffer) >= 2 and ''.join(state_buffer[-2:]) == 'MIDBOT':
            total_reps += 1
            # Do not reset buffer if it's only a partial rep completion, let it potentially complete with next states
        elif len(state_buffer) == 3 and ''.join(state_buffer) == 'TOPMIDTOP':
            total_reps += 1
            state_buffer = [] # Reset for an incomplete but registered rep

        # Use 3-point local max/min check: angle[i-1], angle[i], angle[i+1]
        # Ensure we have enough data points for comparison
        if 0 < i < len(angles) - 1:
            prev_a, curr_a, next_a = angles[i-1], angles[i], angles[i+1]
            if curr_a > prev_a and curr_a > next_a: # Local maximum (peak)
                peak_angles.append(curr_a)
            elif curr_a < prev_a and curr_a < next_a: # Local minimum (descent/bottom)
                descent_angles.append(curr_a)

    # Calculate averages
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
        except Exception as e:
            logger.warning(f"Failed to analyze squat landmarks: {e}")
            return None

    def analyze_bench_or_pull(self, landmarks):
        """Analyze bench press/pull-up form based on elbow angle"""
        try:
            # Get key points for arm analysis (e.g., for bench press or pull-up)
            # Using LEFT side for consistency, but good practice is to average both or pick visible one.
            left_shoulder = [landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value].x,
                             landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
            left_elbow = [landmarks[self.mp_pose.PoseLandmark.LEFT_ELBOW.value].x,
                          landmarks[self.mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
            left_wrist = [landmarks[self.mp_pose.PoseLandmark.LEFT_WRIST.value].x,
                          landmarks[self.mp_pose.PoseLandmark.LEFT_WRIST.value].y]

            # Calculate elbow angle
            elbow_angle = self.calculate_angle(left_shoulder, left_elbow, left_wrist)

            return {
                'angleToCheck': round(elbow_angle, 1)
            }
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
        analysis_results = []
        list_of_frames = [] # Stores angles per relevant frame
        list_of_states = [] # Stores states (TOP/MID/BOT) per relevant frame
        keypoint_series = [] # Stores all landmark data for Gemini

        while cap.isOpened():
            success, image = cap.read()
            if not success:
                break

            frame_count += 1
            if (frame_count - throttleValue) >= frameSkipped: # Use >= for consistent skipping
                throttleValue = frame_count
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                image_rgb.flags.writeable = False
                results = self.pose.process(image_rgb)
                image_rgb.flags.writeable = True
                image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)

                if results.pose_landmarks:
                    self.mp_drawing.draw_landmarks(image, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)

                    landmarks = results.pose_landmarks.landmark
                    # Optimized keypoint data for Gemini to reduce token count
                    keypoint_series.append([
                        {
                            'x': round(lm.x, 3), # Round to 3 decimal places
                            'y': round(lm.y, 3), # Round to 3 decimal places
                            # 'z': round(lm.z, 3), # Removed 'z' for further token reduction
                            # 'visibility': round(lm.visibility, 2) # Removed 'visibility' for token reduction
                        }
                        for lm in landmarks
                    ])

                    # Angle analysis
                    analysis = None
                    if exercise_type == "squat":
                        analysis = self.analyze_squat(landmarks)
                    elif exercise_type in ["pullup", "bench"]: # Handle both with the same analysis method
                        analysis = self.analyze_bench_or_pull(landmarks)
                    else:
                        logger.warning(f"Unknown exercise type: {exercise_type}. No specific analysis applied.")

                    angleOfCurrentState = analysis['angleToCheck'] if analysis else 0

                    list_of_frames.append(angleOfCurrentState)
                    currentState = 2 # Default to BOT/Rest if angle not clear
                    if angleOfCurrentState > 150: # Example thresholds, adjust as needed
                        list_of_states.append('TOP')
                        currentState = 0
                    elif angleOfCurrentState > 100: # Example thresholds
                        list_of_states.append('MID')
                        currentState = 1
                    else:
                        list_of_states.append('BOT')
                        currentState = 2

                    if analysis and out: # Only draw if analysis was successful and output video is enabled
                        all_states_labels = ['TOP', 'MID', 'BOT']
                        colourTuple = (255 if currentState == 0 else 0, # Blue for TOP
                                        255 if currentState == 1 else 0, # Green for MID
                                        255 if currentState == 2 else 0) # Red for BOT
                        cv2.putText(image, f"Angle: {round(angleOfCurrentState, 1)}°", (10, 50),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, colourTuple, 2)
                        cv2.putText(image, all_states_labels[currentState], (10, 100),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, colourTuple, 2)

                if out:
                    out.write(image)

        cap.release()
        if out:
            out.release()

        summary = self.generate_summary(list_of_frames, list_of_states, exercise_type)
        gemini_feedback = self.send_to_gemini(keypoint_series, exercise_type)

        return {
            'processed_video': output_path if output_path else None,
            'analysis_results': analysis_results,
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

    def generate_summary(self, frameSet, stateSet, exercise_type):
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
                'avg_descent_angle': '-1'
            }

        returnedValue = count_reps_and_track_extremes(frameSet, stateSet)

        # General feedback template
        feedback = "Analysis complete."
        if exercise_type == "squat":
            feedback = "Great squat form!" if returnedValue['avg_descent_angle'] <= 90 and returnedValue['avg_descent_angle'] != -1 else "Try to squat deeper! Aim for knees around 90 degrees or below."
        elif exercise_type == "pullup":
            feedback = "Excellent pull-up depth!" if returnedValue['avg_descent_angle'] <= 90 and returnedValue['avg_descent_angle'] != -1 else "Ensure full extension at the bottom of the pull-up."
        elif exercise_type == "bench":
            feedback = "Good bench press depth!" if returnedValue['avg_descent_angle'] <= 90 and returnedValue['avg_descent_angle'] != -1 else "Try to bring the bar lower to your chest for a full range of motion."

        return {
            'exercise': exercise_type,
            'total_frames_analyzed': str(len(frameSet) * (frameSkipped + 1)), # +1 because 0-index skipped frames
            'average_peak_angle': str(returnedValue['avg_peak_angle']),
            'average_descent_angle': str(returnedValue['avg_descent_angle']),
            'good_reps': returnedValue['good_reps'],
            'bad_reps': returnedValue['bad_reps'],
            'total_reps': returnedValue['total_reps'],
            'overall_feedback': feedback
        }