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
    workout_date = request.form.get("workout_date", datetime.today)
    analysis_type = request.form.get("analysisType","FULL")
    total = 0
    total_good = 0

    logger.info(f"Exercise type received: {exercise_type}")
    logger.info(f"Number of sets received: {num_sets}")
    logger.info(f"Workout Date received: {workout_date }")
    logger.info(f"Analysis type received: {analysis_type}")

    processed_results = []
    total = 0
    total_score = 0
    for file in videos:
        if file.filename == '':
            continue

        if not allowed_file(file.filename):
            logger.warning(f"Invalid file skipped: {file.filename}")
            continue

        try:
            file_extension = file.filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4()}.{file_extension}"

            with tempfile.NamedTemporaryFile(suffix=f".{file_extension}", delete=False) as tmp_file:
                file.save(tmp_file.name)
                local_input_path = tmp_file.name

            logger.info(f"Uploaded file saved temporarily to {local_input_path}")
    
            raw_processed_filename = f"raw_processed_{unique_filename}"
            raw_processed_path = os.path.join(tempfile.gettempdir(), raw_processed_filename)

            result = analyzer.process_video(local_input_path, raw_processed_path, exercise_type, analysis_type)
            logger.info(f"Analysis complete. Output saved to {raw_processed_path}")
            processed_url = None
            if analysis_type != "QUICK":
                encoded_filename = f"processed_{uuid.uuid4()}.mp4"
                encoded_path = os.path.join(tempfile.gettempdir(), encoded_filename)

                subprocess.run([
                    'ffmpeg', '-i', raw_processed_path,
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '28',
                    '-c:a', 'aac', '-b:a', '128k',
                    '-movflags', '+faststart',
                    '-y', encoded_path
                ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                logger.info(f"FFmpeg transcoding complete: {encoded_path}")

                with open(encoded_path, 'rb') as processed_file:
                    s3_client.upload_fileobj(
                        processed_file,
                        AWS_BUCKET_NAME,
                        encoded_filename,
                        ExtraArgs={'ContentType': 'video/mp4'}
                    )
                
                processed_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{encoded_filename}"
                logger.info(f"Uploaded processed video to {processed_url}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            return jsonify({'error': 'Video encoding failed.', 'details': e.stderr.decode()}), 500

        except Exception as e:
            logger.error(f"Processing failed: {str(e)}")
            return jsonify({'error': f'Processing failed: {str(e)}'}), 500

        finally:
            if analysis_type == "FULL":
                for path in [local_input_path, raw_processed_path, encoded_path]:
                    if path and os.path.exists(path):
                        try:
                            os.unlink(path)
                            logger.info(f"Deleted temp file {path}")
                        except Exception as cleanup_err:
                            logger.warning(f"Failed to delete temp file {path}: {cleanup_err}")
            
        print(processed_url)
        processed_results.append({
            'processed_url': processed_url,
            'analysis': result.get('summary', {}),
            'gemini_feedback': result.get('gemini_feedback', 'No AI feedback available')
        })
            
        good_reps= (result.get('summary', {}).get('score',0))
        set_reps= 1 
        float_value = 0.0
        try:
            float_value = float(good_reps)
        except ValueError:
            float_value = 0.0  # or handle it differently
        total_score += float_value
        total += set_reps
    #save to db
    score = (total_score/total)*100
    workout_id = str(uuid.uuid4())  
    workout = {
        'id' : workout_id,
        'num_sets' : num_sets,
        'results' : processed_results,
        'score' : score       
                }
    db.users.update_one({'user_id': request.user_id}, {'$push':{f"workouts.{workout_date}":workout}})
    return jsonify({'success': True, 'results': processed_results, 'score': round(score, 2)})

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