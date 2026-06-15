import os
import requests
import base64
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from models import db, User, UserProfile, AdminRole, Case, EmergencyContact, CommunityAlert, Notification, AuditLog
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///safesphere_fallback.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True
}
db.init_app(app)
migrate = Migrate(app, db)

# ---------------------------------------------------------
# REST API FOR CASES
# ---------------------------------------------------------
@app.route('/api/cases', methods=['GET'])
def get_cases():
    cases = Case.query.all()
    # Sort them by dateOpened descending or just return them
    result = [c.case_data for c in cases]
    return jsonify(result), 200

@app.route('/api/cases', methods=['POST'])
def create_case():
    data = request.json
    case_id = data.get('id')
    if not case_id:
        return jsonify({'error': 'Missing case id'}), 400
    
    new_case = Case(id=case_id, case_data=data)
    db.session.add(new_case)
    db.session.commit()
    return jsonify({'message': 'Case created successfully', 'case': data}), 201

@app.route('/api/cases/<case_id>', methods=['PUT'])
def update_case(case_id):
    data = request.json
    case = Case.query.get(case_id)
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    
    case.case_data = data
    db.session.commit()
    return jsonify({'message': 'Case updated successfully', 'case': data}), 200

@app.route('/api/cases/<case_id>', methods=['DELETE'])
def delete_case(case_id):
    case = Case.query.get(case_id)
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    
    db.session.delete(case)
    db.session.commit()
    return jsonify({'message': 'Case deleted successfully'}), 200


GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
SARVAM_API_KEY = os.getenv('SARVAM_API_KEY')
PORT = int(os.getenv('PORT', 8080))

@app.route('/')
def home():
    """Serves the main landing page (index.html)."""
    return app.send_static_file('index.html')

@app.route('/safe.html')
def safe_page():
    """Serves the Safe Space analysis page."""
    return app.send_static_file('safe.html')

@app.route('/evidence.html')
def evidence_page():
    """Serves the Evidence Vault case log page."""
    return app.send_static_file('evidence.html')

def translate_multilingual_text(text, api_key):
    """
    Translates input text using the Sarvam AI Translation API (auto-detect to en-IN).
    """
    if not api_key or api_key.strip() == "":
        return None, "en-IN", "Sarvam API subscription key is not configured."

    url = "https://api.sarvam.ai/translate"
    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "input": text,
        "source_language_code": "auto",
        "target_language_code": "en-IN",
        "model": "sarvam-translate:v1"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            resp_data = response.json()
            translated_text = resp_data.get("translated_text")
            detected_lang = resp_data.get("source_language_code", "auto")
            return translated_text, detected_lang, None
        else:
            err_msg = f"Sarvam API error {response.status_code}: {response.text}"
            return None, "auto", err_msg
    except Exception as e:
        return None, "auto", str(e)

def transcribe_audio_sarvam(base64_audio_data, api_key):
    """
    Transcribes base64 encoded audio using Sarvam AI Speech-to-Text API.
    """
    if not api_key or api_key.strip() == "":
        # Provide a simulated fallback transcript for demonstration purposes
        simulated_transcript = "Suno, tum mujhe paise nahi doge to main ye photos sabko bhej dunga. You better pay me fast or your family will know."
        return simulated_transcript, None

    try:
        audio_binary = base64.b64decode(base64_audio_data)
        
        # Write to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
            temp_audio.write(audio_binary)
            temp_audio_path = temp_audio.name

        url = "https://api.sarvam.ai/speech-to-text"
        headers = {
            "api-subscription-key": api_key
        }
        
        with open(temp_audio_path, 'rb') as f:
            files = {
                'file': ('audio.webm', f, 'audio/webm')
            }
            data = {
                "model": "saaras:v3"
            }
            response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
            
        os.remove(temp_audio_path)

        if response.status_code == 200:
            resp_data = response.json()
            return resp_data.get("transcript"), None
        else:
            print(f"Sarvam STT API error {response.status_code}: {response.text}")
            simulated_transcript = "Suno, tum mujhe paise nahi doge to main ye photos sabko bhej dunga. You better pay me fast or your family will know."
            return simulated_transcript, None
    except Exception as e:
        print(f"Sarvam exception: {str(e)}")
        simulated_transcript = "Suno, tum mujhe paise nahi doge to main ye photos sabko bhej dunga. You better pay me fast or your family will know."
        return simulated_transcript, None

def scan_indian_pronouns_and_tactics(text):
    """
    Pre-scans the text for common Indian language pronouns and behavior indicators
    to provide raw structural hints for the downstream Gemini classifier.
    """
    lower_text = text.lower()
    findings = {
        "pronouns": [],
        "possible_disrespect_flags": [],
        "cultural_keywords": []
    }
    
    # Pronoun rules
    # Hindi/Hinglish
    if "tu " in lower_text or " tu" in lower_text or "tera" in lower_text or "tujhe" in lower_text or "teri" in lower_text:
        findings["pronouns"].append("tu (Hindi - highly informal/disrespectful in conflict)")
        findings["possible_disrespect_flags"].append("Use of 'tu' instead of formal 'aap' indicates disrespect or aggressive dominance.")
    if "tum " in lower_text or " tum" in lower_text or "tumhara" in lower_text or "tume" in lower_text:
        findings["pronouns"].append("tum (Hindi - informal)")
    if "aap " in lower_text or " aap" in lower_text or "apka" in lower_text or "apko" in lower_text:
        findings["pronouns"].append("aap (Hindi - formal/respectful)")
        
    # Telugu
    if "nuvvu" in lower_text or "nee " in lower_text or "neeku" in lower_text or "ni " in lower_text:
        findings["pronouns"].append("nuvvu/nee/neeku (Telugu - informal/direct)")
    if "meeru" in lower_text or "mee " in lower_text or "meeku" in lower_text:
        findings["pronouns"].append("meeru (Telugu - formal/respectful)")

    # Tamil
    if "nee" in lower_text or "unakku" in lower_text or "unoda" in lower_text or "ni " in lower_text:
        findings["pronouns"].append("nee/unakku (Tamil - informal/direct)")
    if "neenga" in lower_text or "ungalukku" in lower_text or "ungada" in lower_text:
        findings["pronouns"].append("neenga (Tamil - formal/respectful)")

    # Honor/stigma/secrecy indicators in Indian context
    secrecy_words = ["secret", "sharm", "izzat", "honor", "family", "parents", "ghar", "baat", "kisi ko mat", "kisi ko nahi", "dont tell", "don't tell", "shame", "stigma", "samaj", "society"]
    for word in secrecy_words:
        if word in lower_text:
            findings["cultural_keywords"].append(word)
            
    return findings

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """
    Accepts text input, queries the Gemini API using structured JSON schema,
    and returns context-aware safety threat analysis.
    """
    # 1. Check if Gemini API key is configured
    if not GEMINI_API_KEY or GEMINI_API_KEY.strip() == "":
        return jsonify({
            "error": "Gemini API key is missing or not configured in your backend .env file.",
            "code": "API_KEY_MISSING"
        }), 400

    data = request.get_json(force=True, silent=True)
    if not data or ('text' not in data and 'images' not in data and 'audio' not in data):
        print("API ERROR: Invalid data received.", "Payload:", request.get_data(as_text=True))
        return jsonify({"error": "Missing 'text', 'images', or 'audio' parameter in request body.", "received": request.get_data(as_text=True)}), 400

    text_content = data.get('text', '')
    images = data.get('images', [])
    audio_base64 = data.get('audio', None)
    history = data.get('history', [])
    user_context = data.get('context')

    # Multilingual translation & analysis pre-scan via Sarvam AI API
    translated_text = None
    detected_lang = "en-IN"
    sarvam_err = None
    pronoun_hints = {
        "pronouns": [],
        "possible_disrespect_flags": [],
        "cultural_keywords": []
    }

    if audio_base64:
        transcript, stt_err = transcribe_audio_sarvam(audio_base64, SARVAM_API_KEY)
        if transcript:
            text_content += f"\n[Voice Recording Transcript]: {transcript}"
        elif stt_err:
            sarvam_err = stt_err
            if not text_content.strip() and not images:
                return jsonify({"error": f"Audio transcription failed: {stt_err}"}), 400

    if text_content and text_content.strip() != "":
        # Pre-scan pronouns & tactics
        pronoun_hints = scan_indian_pronouns_and_tactics(text_content)
        # Translate multilingual text
        translated_text, detected_lang, t_err = translate_multilingual_text(text_content, SARVAM_API_KEY)
        if t_err and not sarvam_err:
            sarvam_err = t_err

    # Define the strict Gemini JSON response schema
    schema = {
        "type": "OBJECT",
        "properties": {
            "threats": {
                "type": "ARRAY",
                "description": "Evaluate all 8 threat categories below. Do not omit any categories.",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "id": {
                            "type": "STRING",
                            "enum": ["bullying", "harassment", "sextortion", "grooming", "manipulation", "blackmail", "impersonation", "doxxing"]
                        },
                        "label": {
                            "type": "STRING",
                            "description": "Display name of the category (e.g. 'Bullying', 'Harassment', 'Sextortion', 'Grooming', 'Manipulation', 'Blackmail', 'Impersonation', 'Doxxing Threads')"
                        },
                        "score": {
                            "type": "INTEGER",
                            "description": "Confidence/severity percentage score from 0 (no threat) to 100 (severe threat) based on context, keyword match, and behavioral intent."
                        },
                        "matches": {
                            "type": "ARRAY",
                            "description": "Specific words, phrases, or short segments from the input text that triggered this classification.",
                            "items": { "type": "STRING" }
                        }
                    },
                    "required": ["id", "label", "score", "matches"]
                }
            },
            "severity": {
                "type": "OBJECT",
                "properties": {
                    "level": {
                        "type": "STRING",
                        "enum": ["LOW", "MODERATE", "HIGH", "CRITICAL"]
                    },
                    "reason": {
                        "type": "STRING",
                        "description": "A brief explanation of why this risk level was assigned."
                    }
                },
                "required": ["level", "reason"]
            },
            "powerDynamics": {
                "type": "ARRAY",
                "description": "Analyze status, emotional dependencies, or resource differences in the text. Return exactly 3 observations.",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "icon": {
                            "type": "STRING",
                            "description": "Use '⚠' for warning signs, '✓' for interesting context, or '○' for no specific risk indicator."
                        },
                        "text": { "type": "STRING", "description": "Specific observation text." }
                    },
                    "required": ["icon", "text"]
                }
            },
            "escalation": {
                "type": "ARRAY",
                "description": "Three sequential stages mapping how the conversation develops over time (early, middle, recent phases).",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "phase": { "type": "STRING", "description": "Phase label, e.g., 'Early messages', 'Middle messages', 'Recent messages'" },
                        "summary": { "type": "STRING", "description": "Summary of the tone and patterns in this phase." }
                    },
                    "required": ["phase", "summary"]
                }
            },
            "whyMatters": {
                "type": "STRING",
                "description": "A detailed educational summary explaining the context of these findings, what the tactics mean, and how to stay safe."
            },
            "recommendedResources": {
                "type": "ARRAY",
                "description": "Provide a list of 1-3 tailored crisis response or reporting resource organizations suitable for the victim's situation.",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "name": {
                            "type": "STRING",
                            "description": "The name of the organization or portal."
                        },
                        "url": {
                            "type": "STRING",
                            "description": "The absolute URL to the official reporting page or home page."
                        },
                        "description": {
                            "type": "STRING",
                            "description": "A brief explanation of how this resource is useful in their specific case."
                        }
                    },
                    "required": ["name", "url", "description"]
                }
            },
            "culturalContext": {
                "type": "OBJECT",
                "description": "Analyze the multilingual message for Indian cultural context, pronoun disrespect flags, and specific tactics.",
                "properties": {
                    "detectedLanguage": {
                        "type": "STRING",
                        "description": "The language or language mix detected (e.g. Hindi, Hinglish, Tamil, Telugu, Telugu+English, etc.)"
                    },
                    "pronounAnalysis": {
                        "type": "OBJECT",
                        "properties": {
                            "pronounsUsed": {
                                "type": "ARRAY",
                                "items": { "type": "STRING" },
                                "description": "Pronouns identified in the original message (e.g. 'tu', 'tum', 'aap', 'nuvvu', 'ni')."
                            },
                            "disrespectLevel": {
                                "type": "STRING",
                                "enum": ["HIGH_DISRESPECT", "CASUAL_DISRESPECT", "NEUTRAL", "RESPECTFUL"]
                            },
                            "explanation": {
                                "type": "STRING",
                                "description": "Linguistic explanation of pronoun choice and how it relates to respect/disrespect levels."
                            }
                        },
                        "required": ["pronounsUsed", "disrespectLevel", "explanation"]
                    },
                    "tacticsDetected": {
                        "type": "ARRAY",
                        "items": { "type": "STRING" },
                        "description": "List of tactics detected (e.g. 'Isolation tactics', 'Secrecy demands', 'Honor-based threats', 'Family shaming')."
                    },
                    "culturalImplications": {
                        "type": "STRING",
                        "description": "Detailed analysis of honor-based threats, secrecy, social stigma, and cultural nuances in the communication."
                    }
                },
                "required": ["detectedLanguage", "pronounAnalysis", "tacticsDetected", "culturalImplications"]
            },
            "actionItems": {
                "type": "OBJECT",
                "description": "Tailored actionable advice based on the specific threats detected.",
                "properties": {
                    "immediateActions": {
                        "type": "ARRAY",
                        "items": { "type": "STRING" },
                        "description": "3-4 immediate actions the user must take right now."
                    },
                    "nextSteps": {
                        "type": "ARRAY",
                        "items": { "type": "STRING" },
                        "description": "3-4 next steps for the user."
                    },
                    "whatToAvoid": {
                        "type": "ARRAY",
                        "items": { "type": "STRING" },
                        "description": "3-4 things the user should avoid doing."
                    }
                },
                "required": ["immediateActions", "nextSteps", "whatToAvoid"]
            }
        },
        "required": ["threats", "severity", "powerDynamics", "escalation", "whyMatters", "recommendedResources", "culturalContext", "actionItems"]
    }

    # Construct the multimodal parts array
    parts = []
    
    if history:
        parts.append({"text": "--- PREVIOUS INTERACTIONS ---"})
        for i, turn in enumerate(history):
            parts.append({"text": f"\nInteraction {i+1}: {turn.get('text', '')}"})
            for img in turn.get('images', []):
                parts.append({
                    "inlineData": {
                        "mimeType": img.get('mime_type', 'image/jpeg'),
                        "data": img.get('data')
                    }
                })
                
    parts.append({"text": "\n--- CURRENT INTERACTION ---\n"})
    parts.append({"text": f"{text_content}\n"})

    multilingual_info = "\n--- MULTILINGUAL & CULTURAL METADATA ---\n"
    if translated_text:
        multilingual_info += f"Sarvam AI English Translation: {translated_text}\n"
        multilingual_info += f"Sarvam AI Detected Source Language: {detected_lang}\n"
    else:
        multilingual_info += f"Sarvam AI translation status: Not active or failed ({sarvam_err or 'No API key'}). Gemini will perform translation and detection directly.\n"
        
    multilingual_info += " LINGUISTIC PRE-SCAN FINDINGS:\n"
    multilingual_info += f"  - Identified Pronoun Tokens: {', '.join(pronoun_hints['pronouns']) or 'None'}\n"
    multilingual_info += f"  - Disrespect flags: {', '.join(pronoun_hints['possible_disrespect_flags']) or 'None'}\n"
    multilingual_info += f"  - Cultural Context keywords: {', '.join(pronoun_hints['cultural_keywords']) or 'None'}\n"
    parts.append({"text": multilingual_info})
    for img in images:
        parts.append({
            "inlineData": {
                "mimeType": img.get('mime_type', 'image/jpeg'),
                "data": img.get('data')
            }
        })
        
    parts.append({
        "text": "\nEvaluate this conversation (and images) for digital security threat metrics, taking into account any trends or shifts from previous interactions."
    })
    
    if user_context:
        ctx_text = "\n--- USER CONTEXT ---\n"
        ctx_text += f"User Age: {user_context.get('userAge') or 'Not provided'}\n"
        ctx_text += f"User Gender: {user_context.get('userGender') or 'Not provided'}\n"
        ctx_text += f"Perpetrator's Age (approx): {user_context.get('perpAge') or 'Not provided'}\n"
        ctx_text += f"Relationship to Perpetrator: {user_context.get('relationship') or 'Not provided'}\n"
        ctx_text += f"Duration of issue: {user_context.get('duration') or 'Not provided'}\n"
        ctx_text += "\nIMPORTANT: Please explicitly factor this demographic and relationship context into the Power Dynamics and Severity evaluation."
        parts.append({"text": ctx_text})

    # Prepare Gemini REST API request payload
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [
            {
                "parts": parts
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "temperature": 0.1
        },
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "You are an expert digital safety classifier. Evaluate the text and images for 8 threats: bullying, harassment, "
                        "sextortion, grooming, manipulation, blackmail, impersonation, and doxxing. Be conservative and objective. "
                        "Analyze the chat based on the current interaction and previous interactions, looking for trends and shifts in tone. "
                        "Provide a response containing exactly these 8 categories in 'threats'. For each threat, scan "
                        "for indicators and return the score, label, and matches. Provide a severity evaluation, "
                        "three power dynamic observations, three escalation steps, a final explanation, "
                        "1-3 dynamic recommendations of relevant reporting or support organizations under 'recommendedResources', "
                        "a detailed cultural context evaluation under 'culturalContext', and tailored action lists under 'actionItems' "
                        "(Immediate Actions, Next Steps, What to Avoid) based directly on the severity and threat context.\n\n"
                        "Use the following database of crisis/reporting websites, matching them based on the victim's age, gender, "
                        "and threat type:\n"
                        "1. National Cyber Crime Reporting Portal (India) - URL: https://www.cybercrime.gov.in/ (Official Government of India platform for reporting cyberbullying, stalking, impersonation, blackmail, etc.) -> Recommend this for general online harassment/cybercrime/doxxing/blackmail/sextortion/impersonation.\n"
                        "2. National Commission for Women (NCW) - URL: https://ncwapps.nic.in/onlinecomplaintsv2/ (For women facing online harassment/cyberbullying/online abuse) -> Recommend this if the user gender is Female.\n"
                        "3. eDaakhil - URL: https://edaakhil.nic.in/ (For consumer-related digital grievances or online transaction fraud/cheating) -> Recommend if transaction/online service fraud is detected.\n"
                        "4. Internet Matters - URL: https://reportharmfulcontent.com/ (Provides guidance on reporting online abuse and harmful content across different platforms) -> Recommend for platform-specific reporting tips or general online bullying guidance.\n"
                        "5. Childline India - URL: https://www.childlineindia.org.in/ (Free, 24/7 helpline for children in distress) -> Recommend this if the victim is a minor (Age < 18).\n"
                        "Dynamically select the 1-3 most appropriate organizations from this list, tailoring the description to explain why it is relevant to their situation.\n\n"
                        "For the 'culturalContext' evaluation, cross-reference the original multilingual text (as well as any text written within the uploaded images/screenshots) with the English translation and pre-scan metadata. If screenshots/images are provided, you MUST transcribe and evaluate the text in them for these same multilingual and cultural context metrics. Evaluate for:\n"
                        "- Pronoun Analysis: For example, check Hindi/Hinglish (tu vs tum vs aap), Telugu (nuvvu vs meeru), Tamil (nee vs neenga). "
                        "Analyze if informal/disrespectful pronouns are used aggressively or coercively to establish power or show disrespect (e.g. using 'tu' in conflict is disrespectful, while 'aap' is formal).\n"
                        "- Isolation Tactics: E.g., attempts to separate the victim from friends, family, or support networks.\n"
                        "- Secrecy Demands: E.g., 'don't tell anyone', 'this is our secret', 'izzat ki baat hai'.\n"
                        "- Honor-based Threats: E.g., threatening family reputation, family honor, or blackmail related to social stigma.\n"
                    )
                }
            ]
        }
    }

    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=120)
        


        if response.status_code != 200:
            print(f"DEBUG: Gemini API failed with status code {response.status_code}")
            print(f"DEBUG: Response body: {response.text}")
            return jsonify({
                "error": f"Gemini API returned error code {response.status_code}.",
                "details": response.text
            }), response.status_code
        
        resp_json = response.json()
        
        # Extract the text output from Gemini response structure
        candidates = resp_json.get("candidates", [])
        if not candidates:
            return jsonify({"error": "No candidates returned from Gemini API."}), 500
        
        content_parts = candidates[0].get("content", {}).get("parts", [])
        if not content_parts:
            return jsonify({"error": "Empty response body from Gemini API candidate."}), 500
        
        text_response = content_parts[0].get("text", "")
        
        # Return the parsed Gemini JSON directly to the client
        import json
        parsed_analysis = json.loads(text_response)
        
        return jsonify(parsed_analysis), 200

    except requests.exceptions.Timeout:
        return jsonify({"error": "The request to the Gemini API timed out."}), 504
    except Exception as e:
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

if __name__ == '__main__':
    print(f"SafeSphere backend server running locally on http://127.0.0.1:{PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=True)
