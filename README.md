# 🏋️ Gym Form Analyser

An AI-powered full stack web app to help beginner gym-goers improve their form. Upload a push-up, squat or pull-up video, and our system uses MediaPipe Pose + Google Gemini to give instant, personalized feedback.

---

## 🚀 Features

- **Video upload & storage** on AWS S3  
- **Pose tracking** & rep counting with MediaPipe Pose  
- **Score & general feedback** from our algorithm  
- **Full analysis** (personalized tips) via Google Gemini API  
- **Workout history** saved in MongoDB Atlas (create/read/update/delete)  

---

## 📥 Local Setup

1. **Clone repo**  
   ```bash
   git clone https://github.com/Qiyueyue123/gym-form-analyser.git
   cd gym-form-analyser

# render frontend first
cd frontend
npm install
npm run build
# → generates `dist/`, served by Flask


# to run the server
cd ../backend<br/>
python3 -m venv venv<br/>
source venv/bin/activate<br/>
pip install -r requirements.txt<br/>
python3 app.py <br/>
version 3.11 or lesser


# create .env file in backend

AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY
AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET
AWS_REGION=ap-southeast-1
AWS_BUCKET_NAME=your_bucket_name


MONGO_URI=your_mongo_connection_string

FLASK_ENV=development
FLASK_APP=app.py
SECRET_KEY=your_flask_secret


JWT_SECRET_KEY=your_jwt_secret


GEMINI_API_KEY1=your_key_1
GEMINI_API_KEY2=your_key_2
GEMINI_API_KEY3=your_key_3


### 🔧 Add `config.py` to Backend

Create a new file called `config.py` in your `backend/` directory and paste the following:

```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ==== AWS S3 CONFIG ====
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.environ.get('AWS_REGION')
    AWS_BUCKET_NAME = os.environ.get('AWS_BUCKET_NAME')

    # ==== MONGO CONFIG ====
    MONGO_URI = os.environ.get('MONGO_URI')

    # ==== FLASK CONFIG ====
    FLASK_ENV = os.environ.get('FLASK_ENV')
    FLASK_APP = os.environ.get('FLASK_APP')
    SECRET_KEY = os.environ.get('SECRET_KEY')

    # ==== JWT CONFIG ====
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = 7200

    # ==== GEMINI CONFIG ====
    GEMINI_API_KEY1 = os.environ.get('GEMINI_API_KEY1')
    GEMINI_API_KEY2 = os.environ.get('GEMINI_API_KEY2')
    GEMINI_API_KEY3 = os.environ.get('GEMINI_API_KEY3')
    GEMINI_API_KEYS = [GEMINI_API_KEY1, GEMINI_API_KEY2, GEMINI_API_KEY3]
    _gemini_key_index = 0

    @classmethod
    def getGeminiApiKey(cls):
        if not cls.GEMINI_API_KEYS:
            return None
        cls._gemini_key_index = (cls._gemini_key_index + 1) % len(cls.GEMINI_API_KEYS)
        print(f"Using Gemini API key index: {cls._gemini_key_index}")
        return cls.GEMINI_API_KEYS[cls._gemini_key_index]
