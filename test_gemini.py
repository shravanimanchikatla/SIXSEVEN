import os, requests
from dotenv import load_dotenv
load_dotenv()
key = os.getenv("GEMINI_API_KEY")
url1 = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
res1 = requests.post(url1, json={"contents": [{"parts": [{"text": "Hello"}]}]})
print("1.5-flash:", res1.status_code, res1.text[:100])

url2 = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
res2 = requests.post(url2, json={"contents": [{"parts": [{"text": "Hello"}]}]})
print("2.5-flash:", res2.status_code, res2.text[:100])
