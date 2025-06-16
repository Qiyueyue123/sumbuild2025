from flask import Flask, render_template, request, jsonify
import os
import boto3
from werkzeug.utils import secure_filename
from config import Config
import uuid
import tempfile
from video_processor import GymFormAnalyzer
import logging

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

# Initialize GymFormAnalyzer
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
    exercise_type = request.form.get('exercise_type', 'squat')
    
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
        
        # Construct S3 URL dynamically with region
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
    exercise_type = data.get('exercise_type', 'squat')
    
    # Extract S3 key (filename) from URL
    try:
        s3_key = video_url.split('/')[-1]
        if not s3_key:
            raise ValueError("Invalid video URL format")
    except Exception as e:
        return jsonify({'error': f'Failed to extract video key from URL: {str(e)}'}), 400
    
    tmp_path = None
    processed_path = None
    
    try:
        # Download video from S3 to a temporary file
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(s3_key)[1], delete=False) as tmp_file:
            s3_client.download_fileobj(AWS_BUCKET_NAME, s3_key, tmp_file)
            tmp_path = tmp_file.name
        
        logger.info(f"Downloaded video {s3_key} to temp file {tmp_path}")
        
        # Prepare path for processed output video
        processed_filename = f"processed_{s3_key}"
        processed_path = os.path.join(tempfile.gettempdir(), processed_filename)
        
        # Analyze/process video
        result = analyzer.process_video(tmp_path, processed_path, exercise_type)
        
        # Upload processed video back to S3
        with open(processed_path, 'rb') as processed_file:
            s3_client.upload_fileobj(
                processed_file,
                AWS_BUCKET_NAME,
                processed_filename,
                ExtraArgs={'ContentType': 'video/mp4'}
            )
        
        processed_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{processed_filename}"
        logger.info(f"Uploaded processed video to {processed_url}")
        
        return jsonify({
            'success': True,
            'processed_url': processed_url,
            'analysis': result.get('summary', {})
        })
    
    except Exception as e:
        logger.error(f"Video analysis failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
    finally:
        # Cleanup temporary files if they exist
        for path in [tmp_path, processed_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                    logger.info(f"Deleted temp file {path}")
                except Exception as cleanup_err:
                    logger.warning(f"Failed to delete temp file {path}: {cleanup_err}")

if __name__ == '__main__':
    app.run(debug=True)
