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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
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

@app.route('/')
def home():
    return render_template('index.html')

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

if __name__ == '__main__':
    # Ensure all environment variables are set before running.
    app.run(debug=True, host='0.0.0.0') # Listen on all interfaces