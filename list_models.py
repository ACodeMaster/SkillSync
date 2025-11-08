import google.generativeai as genai
import os

# Load API key from environment variable
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise Exception("❌ GEMINI_API_KEY not found. Please set it first.")

# Configure Gemini client
genai.configure(api_key=api_key)

print("✅ Listing available Gemini models...\n")

for model in genai.list_models():
    if "generateContent" in model.supported_generation_methods:
        print("🧠", model.name)
