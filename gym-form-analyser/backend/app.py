from flask import Flask, request, jsonify, send_from_directory
import os
import boto3
from pymongo import MongoClient
from functools import wraps
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
import jwt
import uuid
import tempfile
from video_processor import GymFormAnalyzer 
import logging
import subprocess
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#configure mongodb stuff
client = MongoClient(Config.MONGO_URI)
db = client['summbuild']

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FRONTEND_DIST = os.path.join(BASE_DIR, '../frontend/dist')

app = Flask(__name__, static_folder=FRONTEND_DIST, static_url_path='')

app.config.from_object(Config)

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=app.config['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=app.config['AWS_SECRET_ACCESS_KEY'],
    region_name=app.config['AWS_REGION']
)

AWS_BUCKET_NAME = app.config['AWS_BUCKET_NAME']
AWS_REGION = app.config['AWS_REGION']
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi'}

# Initialize GymFormAnalyzer once when the app starts
analyzer = GymFormAnalyzer()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_videos(videos, exercise_type, analysis_type):
    logger.info(f"Received {len(videos)} video files")

    if not videos or all(v.filename == '' for v in videos):
        raise ValueError("No valid video files received")

    logger.info(f"Exercise type: {exercise_type}")
    logger.info(f"Analysis type: {analysis_type}")

    processed_results = []
    total_score = 0.0
    processed_count = 0

    for idx, file in enumerate(videos):
        if file.filename == '' or not allowed_file(file.filename):
            logger.warning(f"Skipping invalid file: {file.filename}")
            continue

        try:
            file_ext = file.filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4()}.{file_ext}"

            with tempfile.NamedTemporaryFile(suffix=f".{file_ext}", delete=False) as tmp_file:
                file.save(tmp_file.name)
                local_input_path = tmp_file.name

            raw_path = os.path.join(tempfile.gettempdir(), f"raw_processed_{unique_filename}")
            result = analyzer.process_video(local_input_path, raw_path, exercise_type, analysis_type)

            processed_url = None
            encoded_path = None

            if analysis_type != "QUICK":
                encoded_filename = f"processed_{uuid.uuid4()}.mp4"
                encoded_path = os.path.join(tempfile.gettempdir(), encoded_filename)

                subprocess.run([
                    'ffmpeg', '-i', raw_path,
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '28',
                    '-c:a', 'aac', '-b:a', '128k',
                    '-movflags', '+faststart',
                    '-y', encoded_path
                ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                with open(encoded_path, 'rb') as processed_file:
                    s3_client.upload_fileobj(
                        processed_file,
                        AWS_BUCKET_NAME,
                        encoded_filename,
                        ExtraArgs={'ContentType': 'video/mp4'}
                    )

                processed_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{encoded_filename}"

            processed_results.append({
                'id': str(uuid.uuid4()),
                'processed_url': processed_url,
                'analysis': result.get('summary', {}),
                'gemini_feedback': result.get('gemini_feedback', 'No AI feedback available')
            })

            score = float(result.get('summary', {}).get('score', 0))
            total_score += score
            processed_count += 1

        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise RuntimeError("Video encoding failed")

        except Exception as e:
            logger.error(f"Processing failed: {str(e)}")
            raise RuntimeError(f"Processing error: {str(e)}")

        finally:
            for path in [local_input_path, raw_path, encoded_path]:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                        logger.info(f"Deleted temp file: {path}")
                    except Exception as cleanup_err:
                        logger.warning(f"Cleanup failed for {path}: {cleanup_err}")

    return processed_results, total_score, processed_count

#ROUTES

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        parts = auth_header.split()

        if len(parts) != 2 or parts[0] != 'Bearer':
            return jsonify({'error': 'Missing or invalid token format'}), 401

        token = parts[1]

        try:
            decoded = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            request.user_id = decoded['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        return f(*args, **kwargs)

    return decorated

@app.route('/verify-token', methods=['GET'])
@token_required
def verify_token():
    return jsonify({'valid': True, 'user_id': request.user_id})

@app.route('/register', methods=['POST'])
def register_user():
    data = request.json
    user_id = data.get('user_id')
    email = data.get('email')
    password = data.get('password')

    if not user_id or not email or not password:
        return jsonify({'error': 'Missing fields'}), 400

    # Check for duplicates
    if db.users.find_one({'user_id': user_id}) or db.users.find_one({'email': email}):
        return jsonify({'error': 'User already exists'}), 409

    password_hash = generate_password_hash(password)

    user_doc = {
        "user_id": user_id,
        "email": email,
        "password_hash": password_hash,
        "profile": {
            "created_at": datetime.utcnow(),
            "last_login": None,
            "workout_stats": {},
        }
    }

    db.users.insert_one(user_doc)
    return jsonify({'message': 'Account created successfully'}), 201

@app.route('/login', methods=['POST'])
def login(): 
    data = request.json
    user_id = data.get('user_id')
    password = data.get('password')

    if not user_id or not password:
        return jsonify({'error': 'Missing user_id or password'}), 400

    user = db.users.find_one({'user_id': user_id})
    if not user:
        return jsonify({'error': 'User account does not exist'}), 404

    if not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Wrong password'}), 401

    # Generate JWT
    expires_in = int(app.config['JWT_ACCESS_TOKEN_EXPIRES']) #based on wtv i set in config
    token_payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(seconds=expires_in)  #session token valid for 2 hrs (based on config settings)
    }

    token = jwt.encode(token_payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')

    return jsonify({
        'message': 'Login successful',
        'token': token
    })

@app.route('/all_workouts', methods = ['GET'])
@token_required
def all_workouts():
    user = db.users.find_one({"user_id" : request.user_id})
    workouts = user.get("workouts", [])
    return jsonify(workouts)

@app.route('/delete_workout', methods=['DELETE'])
@token_required
def delete_workout():
    data = request.get_json()
    workout_id = data.get("workout_id")
    workout_date = data.get("workout_date")

    if not workout_id or not workout_date:
        return jsonify({'error': 'Missing workout_id or workout_date'}), 400

    result = db.users.update_one(
        {"user_id": request.user_id},
        {"$pull": {f"workouts.{data.get('workout_date')}": {"id": workout_id}}}
    )

    if result.modified_count == 0:
        return jsonify({'error': 'Workout not found'}), 404

    user = db.users.find_one(
        {"user_id": request.user_id},
        {f"workouts.{workout_date}": 1}
    )
    workouts_on_date = user.get("workouts", {}).get(workout_date, [])

    if not workouts_on_date:
        db.users.update_one(
            {"user_id": request.user_id},
            {"$unset": {f"workouts.{workout_date}": ""}}
        )

    return jsonify({'message': 'Workout deleted'})

@app.route('/update_workout', methods=['POST'])
@token_required
def update_workout():
    form = request.form

    original_date = form.get("original_date")
    workout_date = form.get("workout_date", original_date)
    exercise_type = form.get("exercise_type", "").lower()
    num_sets = int(form.get("num_sets", 0))
    analysis_type = form.get("analysisType", "FULL")
    workout_id = form.get("id")
    deleted_set_ids = json.loads(form.get("deleted_set_ids", "[]"))
    videos = request.files.getlist("video")

    if not original_date or not workout_id:
        return jsonify({"error": "Missing required fields: original_date or workout_id"}), 400

    # 1. Delete selected sets
    if deleted_set_ids:
        db.users.update_one(
            {
                "user_id": request.user_id,
                f"workouts.{original_date}.id": workout_id
            },
            {
                "$pull": {
                    f"workouts.{original_date}.$.results": {
                        "id": {"$in": deleted_set_ids}
                    }
                }
            }
        )

    # 2. Get the workout object
    user_doc = db.users.find_one(
        { "user_id": request.user_id },
        { f"workouts.{original_date}": 1 }
    )
    workouts_on_date = user_doc.get("workouts", {}).get(original_date, [])
    target_workout = next((w for w in workouts_on_date if w["id"] == workout_id), None)

    if not target_workout:
        return jsonify({"error": "Workout not found"}), 404

    # 3. If workout_date has changed, move it first
    if workout_date != original_date:
        db.users.update_one(
            { "user_id": request.user_id },
            { "$pull": { f"workouts.{original_date}": { "id": workout_id } } }
        )
        db.users.update_one(
            { "user_id": request.user_id },
            { "$push": { f"workouts.{workout_date}": target_workout } }
        )
        # Clean up empty date
        check_user = db.users.find_one(
            { "user_id": request.user_id },
            { f"workouts.{original_date}": 1 }
        )
        if not check_user.get("workouts", {}).get(original_date):
            db.users.update_one(
                { "user_id": request.user_id },
                { "$unset": { f"workouts.{original_date}": "" } }
            )

    # 4. Process new videos if any
    new_results = []
    if videos and any(v.filename for v in videos):
        try:
            new_results, _, _ = process_videos(videos, exercise_type, analysis_type)
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except RuntimeError as re:
            return jsonify({"error": str(re)}), 500

        # Add results to updated workout (now at workout_date)
        db.users.update_one(
            {
                "user_id": request.user_id,
                f"workouts.{workout_date}.id": workout_id
            },
            {
                "$push": {
                    f"workouts.{workout_date}.$.results": { "$each": new_results }
                }
            }
        )

    # 5. Recalculate score and metadata
    updated_doc = db.users.find_one(
        { "user_id": request.user_id },
        { f"workouts.{workout_date}": 1 }
    )
    updated_workouts = updated_doc.get("workouts", {}).get(workout_date, [])
    updated = next((w for w in updated_workouts if w["id"] == workout_id), None)

    if updated:
        sets = updated.get("results", [])
        total_score = sum(float(s.get("analysis", {}).get("score", 0)) for s in sets)
        total_sets = len(sets)
        avg_score = (total_score / total_sets) * 100 if total_sets else 0

        db.users.update_one(
            {
                "user_id": request.user_id,
                f"workouts.{workout_date}.id": workout_id
            },
            {
                "$set": {
                    f"workouts.{workout_date}.$.num_sets": total_sets,
                    f"workouts.{workout_date}.$.score": round(avg_score, 2),
                    f"workouts.{workout_date}.$.exercise_type": exercise_type
                }
            }
        )

    return jsonify({"message": "Workout updated successfully"})

@app.route('/upload_and_analyze', methods=['POST'])
@token_required
def upload_and_analyze():
    videos = request.files.getlist("video")
    logger.info(f"Received {len(videos)} video files")
    for idx, file in enumerate(videos):
        logger.info(f"Video {idx + 1}: {file.filename}")

    if not videos or all(v.filename == '' for v in videos):
        return jsonify({'error': 'No video files received'}), 400

    exercise_type = request.form.get("exercise_type", "squat").lower()
    num_sets = request.form.get("num_sets", '1')
    workout_date = request.form.get("workout_date", datetime.today().strftime('%Y-%m-%d'))
    analysis_type = request.form.get("analysisType", "FULL")

    logger.info(f"Exercise type received: {exercise_type}")
    logger.info(f"Number of sets received: {num_sets}")
    logger.info(f"Workout Date received: {workout_date}")
    logger.info(f"Analysis type received: {analysis_type}")

    try:
        processed_results, total_score, total_sets = process_videos(videos, exercise_type, analysis_type)
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except RuntimeError as re:
        return jsonify({'error': str(re)}), 500

    # Final score calculation
    score = (total_score / total_sets) * 100 if total_sets else 0

    workout = {
        'id': str(uuid.uuid4()),
        'num_sets': int(num_sets),
        'results': processed_results,
        'score': round(score, 2)
    }

    db.users.update_one(
        { 'user_id': request.user_id },
        { '$push': { f"workouts.{workout_date}": workout } }
    )

    return jsonify({
        'success': True,
        'results': processed_results,
        'score': round(score, 2)
    })

@app.route('/get-profile', methods=['GET'])
@token_required
def get_profile():
    user = db.users.find_one({"user_id": request.user_id})
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({
        'user_id': user['user_id'],
        'email': user['email']
    })

@app.route('/update-profile', methods=['PUT'])
@token_required
def update_profile():
    data = request.json
    email = data.get('email')
    user_id = data.get('user_id')
    password = data.get('password')

    if not email or not user_id:
        return jsonify({'error': 'Missing fields'}), 400

    update_fields = {
        'email': email,
        'user_id': user_id,
    }

    if password:
        update_fields['password_hash'] = generate_password_hash(password)

    result = db.users.update_one(
        {'user_id': request.user_id},
        {'$set': update_fields}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({'message': 'Profile updated successfully'})


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    full_path = os.path.join(app.static_folder, path)
    if path != "" and os.path.exists(full_path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')
    
@app.errorhandler(404)
def not_found(e):
    return app.send_static_file('index.html')

if __name__ == '__main__':
    # Ensure all environment variables are set before running.
    app.run(debug=True, host='0.0.0.0') # Listen on all interfaces