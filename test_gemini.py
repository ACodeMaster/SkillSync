import os
import google.generativeai as genai

# Load from system environment variable
api_key = os.getenv("GEMINI_API_KEY")
print("Loaded API key:", api_key)

if not api_key:
    raise Exception("❌ GEMINI_API_KEY not found in system environment variables")

# Configure Gemini
genai.configure(api_key=api_key)

# Test the API
model = genai.GenerativeModel("gemini-1.5-flash")
response = model.generate_content("Write a one-line funny programming joke.")
print("\n🤖 Gemini says:", response.text)
