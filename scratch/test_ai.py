import os
import json
from openai import OpenAI
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def test_hackclub():
    api_key = os.getenv("Hackclub-API")
    print(f"Testing Hackclub-API: {api_key[:10]}...")
    try:
        client = OpenAI(api_key=api_key, base_url="https://ai.hackclub.com/proxy/v1")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Return 'hello' as JSON"}],
            response_format={"type": "json_object"}
        )
        print("Hackclub Success:", response.choices[0].message.content)
        return True
    except Exception as e:
        print("Hackclub Failed:", e)
        return False

def test_gemini():
    api_key = os.getenv("GOOGLE_API_KEY")
    print(f"Testing Gemini API: {api_key[:10]}...")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-pro-latest")
        response = model.generate_content("Say hello as JSON", generation_config={"response_mime_type": "application/json"})
        print("Gemini Success:", response.text)
        return True
    except Exception as e:
        print("Gemini Failed:", e)
        return False

if __name__ == "__main__":
    h = test_hackclub()
    g = test_gemini()
    if not h and not g:
        print("\nCRITICAL: Both AI APIs are failing. Reprocessing will not work.")
    else:
        print("\nSuccess: At least one API is working.")
