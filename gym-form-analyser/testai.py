# list_gemini_models.py
import google.generativeai as genai
import os
from dotenv import load_dotenv

# Optional: Load environment variables from a .env file if you use one
load_dotenv()

# Configure the API key
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY environment variable not set.")
    print("Please set it before running this script: export GEMINI_API_KEY='YOUR_API_KEY'")
    exit()

genai.configure(api_key=GEMINI_API_KEY)

print("Listing available Gemini models and their capabilities:")
try:
    for m in genai.list_models():
        # Only print models that support text generation (which `generateContent` is for)
        if 'generateContent' in m.supported_generation_methods:
            print(f"  Name: {m.name}")
            print(f"  Description: {m.description}")
            print(f"  Supported methods: {m.supported_generation_methods}")
            print("-" * 30)
except Exception as e:
    print(f"An error occurred: {e}")
    print("Please ensure your API key is correct and you have network connectivity.")