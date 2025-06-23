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
print(app.static_folder)
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
    print("received: ", data)
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

@app.route('/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file in request'}), 400

    file = request.files['video']
    exercise_type = request.form.get('exercise_type', 'squat').lower() # Ensure lowercase for consistency

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Allowed types: mp4, mov, avi'}), 400

    try:
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_extension}"

        # Upload original video to S3
        s3_client.upload_fileobj(
            file,
            AWS_BUCKET_NAME,
            unique_filename,
            ExtraArgs={'ContentType': f'video/{file_extension}'}
        )

        s3_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{unique_filename}"
        logger.info(f"Uploaded video {file.filename} as {unique_filename} to S3")

        return jsonify({
            'message': 'Video uploaded successfully!',
            'video_url': s3_url,
            'filename': file.filename,
            'exercise_type': exercise_type
        })

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/analyze', methods=['POST'])
def analyze_video():
    data = request.json
    if not data or 'video_url' not in data:
        return jsonify({'error': 'Missing video URL in request body'}), 400

    video_url = data['video_url']
    exercise_type = data.get('exercise_type', 'squat').lower() # Ensure lowercase for consistency

    tmp_path = None
    raw_processed_path = None
    encoded_path = None

    try:
        # Extract S3 key from URL
        from urllib.parse import urlparse
        parsed_url = urlparse(video_url)
        s3_key = os.path.basename(parsed_url.path)

        if not s3_key:
            raise ValueError("Invalid video URL format or missing S3 key.")

        # Download video from S3 to a temporary file
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(s3_key)[1], delete=False) as tmp_file:
            s3_client.download_fileobj(AWS_BUCKET_NAME, s3_key, tmp_file)
            tmp_path = tmp_file.name

        logger.info(f"Downloaded video {s3_key} to temp file {tmp_path}")

        # Define path for raw processed video (e.g., with Mediapipe drawings)
        raw_processed_filename = f"raw_processed_{s3_key}"
        raw_processed_path = os.path.join(tempfile.gettempdir(), raw_processed_filename)

        # Analyze/process video using GymFormAnalyzer
        result = analyzer.process_video(tmp_path, raw_processed_path, exercise_type)
        logger.info(f"Analysis complete. Raw processed video saved to {raw_processed_path}")

        # Transcode to web-friendly format using ffmpeg (MP4 with H.264)
        encoded_filename = f"processed_{s3_key.replace('.', '_encoded.')}.mp4" # Ensure .mp4 extension
        encoded_path = os.path.join(tempfile.gettempdir(), encoded_filename)
        FFMPEG_PATH = os.path.join(os.getcwd(), 'ffmpeg')

        subprocess.run([
            'ffmpeg', '-i', raw_processed_path,
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '28', # Use medium preset and higher CRF for smaller size
            '-c:a', 'aac', '-b:a', '128k', # AAC audio, 128k bitrate
            '-movflags', '+faststart', # Optimize for web streaming
            '-y', # Overwrite output file without asking
            encoded_path
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) # Capture output for debugging

        logger.info(f"Transcoded video saved to {encoded_path}")
        logger.info(f"Encoded video size: {os.path.getsize(encoded_path)} bytes")

        # Upload processed video to S3
        with open(encoded_path, 'rb') as processed_file:
            s3_client.upload_fileobj(
                processed_file,
                AWS_BUCKET_NAME,
                encoded_filename,
                ExtraArgs={'ContentType': 'video/mp4'}
            )

        processed_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{encoded_filename}"
        logger.info(f"Uploaded processed video to {processed_url}")

        return jsonify({
            'success': True,
            'processed_url': processed_url, # encoded_path variable is the source for this URL
            'analysis': result.get('summary', {}),
            'gemini_feedback': result.get('gemini_feedback', 'No AI feedback available')
        })

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed: {e.stderr.decode()}") # Log FFmpeg error output
        return jsonify({'success': False, 'error': f'Video encoding failed. Ensure ffmpeg is installed and input is valid. FFmpeg Output: {e.stderr.decode()}'}), 500
    except Exception as e:
        logger.error(f"Video analysis failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        # Clean up temporary files
        for path in [tmp_path, raw_processed_path, encoded_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                    logger.info(f"Deleted temp file {path}")
                except Exception as cleanup_err:
                    logger.warning(f"Failed to delete temp file {path}: {cleanup_err}")


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    print(f"Request path: {path}")
    full_path = os.path.join(app.static_folder, path)
    print(f"Resolved to: {full_path}")
    print('REACHED THE CATCHALL')

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