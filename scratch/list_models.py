import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def list_models():
    api_key = os.getenv("GOOGLE_API_KEY")
    print(f"Testing Gemini API: {api_key[:10]}...")
    try:
        genai.configure(api_key=api_key)
        print("Available models:")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(m.name)
    except Exception as e:
        print("Gemini Failed:", e)

if __name__ == "__main__":
    list_models()
