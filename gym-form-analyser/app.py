from flask import Flask, render_template, request, jsonify
import os
import boto3
from werkzeug.utils import secure_filename
from config import Config
import uuid
import tempfile
from video_processor import GymFormAnalyzer 
import logging
import subprocess
from pymongo import MongoClient
from flask_cors import CORS


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)
MONGO_URI = app.config['MONGO_URI']
client = MongoClient("MONGO_URI")
db = client["workout_users"]
users_collection = db["users"]
CORS(app)

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

@app.route('/')
def home():
    return render_template('index.html')

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Missing username or password"}), 400

    if users_collection.find_one({"username": username}):
        return jsonify({"error": "Username already exists"}), 409

    users_collection.insert_one({"username": username, "password": password})
    return jsonify({"message": "User registered successfully"}), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    user = users_collection.find_one({"username": username})
    if not user or user["password"] != password:
        return jsonify({"error": "Invalid username or password"}), 401

    return jsonify({"message": "Login successful"}), 200


@app.route('/upload_and_analyze', methods=['POST'])
def upload_and_analyze():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file in request'}), 400

    file = request.files['video']
    exercise_type = request.form.get('exercise_type', 'squat').lower()

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Allowed types: mp4, mov, avi'}), 400

    local_input_path = None
    raw_processed_path = None
    encoded_path = None

    try:
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_extension}"

        # Save video to temp file
        with tempfile.NamedTemporaryFile(suffix=f".{file_extension}", delete=False) as tmp_file:
            file.save(tmp_file.name)
            local_input_path = tmp_file.name

        logger.info(f"Uploaded file saved temporarily to {local_input_path}")

        # Analyze video
        raw_processed_filename = f"raw_processed_{unique_filename}"
        raw_processed_path = os.path.join(tempfile.gettempdir(), raw_processed_filename)

        result = analyzer.process_video(local_input_path, raw_processed_path, exercise_type)
        logger.info(f"Analysis complete. Output saved to {raw_processed_path}")

        # Transcode with FFmpeg
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
            'processed_url': processed_url,
            'analysis': result.get('summary', {}),
            'gemini_feedback': result.get('gemini_feedback', 'No AI feedback available')
        })

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e.stderr.decode()}")
        return jsonify({'error': 'Video encoding failed. Check if FFmpeg is installed and input is valid.',
                        'details': e.stderr.decode()}), 500

    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

    finally:
        # Clean up all temp files
        for path in [local_input_path, raw_processed_path, encoded_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                    logger.info(f"Deleted temp file {path}")
                except Exception as cleanup_err:
                    logger.warning(f"Failed to delete temp file {path}: {cleanup_err}")


if __name__ == '__main__':
    # Ensure all environment variables are set before running.
    app.run(debug=True, host='0.0.0.0', port=5000) # Listen on all interfaces