from flask import Flask, render_template, request, jsonify
import os
import boto3
from werkzeug.utils import secure_filename
from config import Config
import uuid

app = Flask(__name__)
app.config.from_object(Config)

# Initialize S3 client with your bucket's region (ap-southeast-2)
s3_client = boto3.client(
    's3',
    aws_access_key_id=app.config['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=app.config['AWS_SECRET_ACCESS_KEY'],
    region_name=app.config['AWS_REGION'],  
)

AWS_BUCKET_NAME = app.config['AWS_BUCKET_NAME']

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file'}), 400
    
    file = request.files['video']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only MP4, MOV, AVI allowed'}), 400
    
    try:
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        
        # Upload to S3
        s3_client.upload_fileobj(
            file,
            AWS_BUCKET_NAME,  # Using the bucket from your screenshot
            unique_filename,
            ExtraArgs={'ContentType': f'video/{file_extension}'}
        )
        
        # Generate S3 URL (updated for ap-southeast-2)
        s3_url = f"https://{AWS_BUCKET_NAME}.s3.ap-southeast-2.amazonaws.com/{unique_filename}"
        
        return jsonify({
            'message': 'Video uploaded successfully!',
            'video_url': s3_url,
            'filename': file.filename
        })
        
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/test-s3')
def test_s3():
    try:
        # List objects in your bucket (this will verify connection)
        response = s3_client.list_objects_v2(Bucket=AWS_BUCKET_NAME, MaxKeys=1)
        return jsonify({
            "status": "success", 
            "message": "S3 connection successful",
            "bucket": AWS_BUCKET_NAME
        })
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500

@app.route('/test-upload', methods=['POST'])
def test_upload():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected"}), 400
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            
            # Upload to S3
            s3_client.upload_fileobj(
                file,
                AWS_BUCKET_NAME,
                unique_filename,
                ExtraArgs={'ContentType': file.content_type}
            )
            
            return jsonify({
                "status": "success",
                "message": "Video uploaded successfully",
                "filename": unique_filename
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500
    else:
        return jsonify({
            "status": "error", 
            "message": "File type not allowed. Only mp4, mov, and avi files are supported"
        }), 400

@app.route('/upload-form')
def upload_form():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Video Upload</title>
    </head>
    <body>
        <h2>Test Video Upload</h2>
        <form action="/test-upload" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".mp4,.mov,.avi" required>
            <br><br>
            <input type="submit" value="Upload Video">
        </form>
    </body>
    </html>
    '''

@app.route('/main-upload-form')
def main_upload_form():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Main Upload Test</title>
    </head>
    <body>
        <h2>Test Main Upload Endpoint</h2>
        <form action="/upload" method="post" enctype="multipart/form-data">
            <input type="file" name="video" accept=".mp4,.mov,.avi" required>
            <br><br>
            <input type="submit" value="Upload Video">
        </form>
        <div id="result"></div>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(debug=True)