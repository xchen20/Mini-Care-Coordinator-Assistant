from flask import Blueprint, jsonify, request, Response, current_app
import json
import logging
import openai

from .db import get_db

bp = Blueprint('api', __name__, url_prefix='/')

@bp.route('/patients', methods=['GET'])
def get_all_patients():
    """API endpoint to return a summary list of all patients."""
    db = get_db()
    cursor = db.execute("SELECT id, name FROM patients")
    summaries = [{"id": row["id"], "name": row["name"]} for row in cursor.fetchall()]
    return jsonify(summaries)

@bp.route('/patient/<int:patient_id>', methods=['GET'])
def get_data(patient_id):
    """API endpoint to return detailed data for a specific patient."""
    db = get_db()
    row = db.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    if row:
        patient_data = dict(row)
        patient_data['referred_providers'] = json.loads(patient_data['referred_providers'])
        patient_data['appointments'] = json.loads(patient_data['appointments'])
        patient_data['insurance'] = json.loads(patient_data['insurance'])
        return jsonify(patient_data)
    else:
        return jsonify({"error": "Patient not found"}), 404

@bp.route('/chat', methods=['POST'])
def chat():
    """Handles the main chat interaction by performing RAG."""
    data = request.get_json()
    user_prompt = data.get('prompt')
    patient_id = data.get('patient_id')

    if not user_prompt or not patient_id:
        return jsonify({"error": "prompt and patient_id are required"}), 400

    # Retrieve service managers from the application context
    vector_manager = current_app.config['VECTOR_MANAGER']
    data_manager = current_app.config['DATA_MANAGER']

    # RAG Logic 
    semantic_context = vector_manager.query_relevant_context(user_prompt)
    patient_data = data_manager.get_patient_data(patient_id)

    if not patient_data:
        return jsonify({"error": "Patient not found"}), 404

    primary_insurance = patient_data.get('insurance', {}).get('primary', {}).get('payer')
    if primary_insurance:
        is_accepted = data_manager.get_insurance_status(primary_insurance)
        patient_data['insurance']['primary']['is_accepted'] = is_accepted

    for provider in data_manager.get_all_providers():
        # Dynamically enrich the patient data based on the user's prompt
        provider_name_parts = provider['name'].replace(',', '').lower().split()
        if any(part in user_prompt.lower() for part in provider_name_parts if len(part) > 2):
            is_established = data_manager.check_established_patient(patient_id, provider['name'])
            status = "ESTABLISHED" if is_established else "NEW"
            patient_data[f"status_with_{provider['provider_id']}"] = status
            appointment_rules = data_manager.hospital_data.get("Appointments", {})
            if status in appointment_rules.get("Types", {}):
                patient_data[f"rules_for_{provider['provider_id']}"] = {
                    "duration_minutes": appointment_rules["Types"][status].get("duration_minutes"),
                    "arrival_instructions": appointment_rules["Arrival"].get(status)
                }
            
            for referral in patient_data.get('referred_providers', []):
                if referral.get('provider_id') == provider.get('provider_id'):
                    referred_dept_name = referral.get('department')
                    for dept in provider.get('departments', []):
                        if dept.get('name') == referred_dept_name:
                            patient_data[f"referred_location_for_{provider['provider_id']}"] = dept
                            break

    combined_context = {
        "Semantically Relevant Hospital Knowledge": semantic_context,
        "Full Patient Record": patient_data
    }
    context_str = json.dumps(combined_context, indent=2)

    system_prompt = """
    You are a highly capable Care Coordinator Assistant. Your task is to help a nurse take the correct next steps for the currently selected patient.
    Use the provided context below to answer the nurse's questions accurately and concisely. Be proactive and guiding.
    Format your answers for clarity using Markdown (e.g., bolding for names, lists for steps).
    
    **Crucial Instructions:**
    - Your context has two main parts: `Semantically Relevant Hospital Knowledge` and the `Full Patient Record`.
    - For general hospital questions (e.g., "which doctors treat bone problems?"), use `Semantically Relevant Hospital Knowledge`.
    - For specific patient questions (e.g., "what is his insurance?"), use the `Full Patient Record`.
    - **Appointment Type & Details (EXTREMELY IMPORTANT):**
        - To determine if a patient is 'NEW' or 'ESTABLISHED', you **MUST** use the `status_with_{provider_id}` field inside the `Full Patient Record`. This is the definitive truth.
        - To find the appointment duration and arrival instructions, you **MUST** use the corresponding `rules_for_{provider_id}` field.
    - **Scheduling Logic (EXTREMELY IMPORTANT):**
        - When asked to book an appointment, you must follow these steps in order:
        - 1. Find the provider's exact hours in the `Semantically Relevant Hospital Knowledge` context.
        - 2. State these hours in your response. **You are forbidden from assuming or making up provider hours.**
        - 3. Compare the nurse's requested day and time with the hours you found.
        - 4. If there is a conflict, you **MUST** state the conflict clearly and suggest alternative times. Do not proceed with booking steps.
        - 5. If there is no conflict, you may proceed with the next steps for booking.
        - **If a `referred_location_for_{provider_id}` field exists in the `Full Patient Record`, you MUST use the hours and address from that specific location for scheduling.** This is the most important location.
    - **Insurance Rejection Flow:** If you determine that an insurance is not accepted, you **MUST** then look for "Self-Pay Rates" in the `Semantically Relevant Hospital Knowledge` context and present those rates to the nurse as the next step.
        - To check if insurance is accepted, look for the `is_accepted` boolean field inside the patient's `insurance` object. This is the definitive truth.
    - **DO NOT** attempt to re-calculate the status or find the rules in the `Semantically Relevant Hospital Knowledge`. The `status_with_...` and `rules_for_...` fields are your **ONLY** source of truth for these details. Ignore any other conflicting information.
    """

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context:\n{context_str}\n\nQuestion:\n{user_prompt}"}
        ]
    )
    return jsonify({"response": response.choices[0].message.content})

@bp.route('/transcribe', methods=['POST'])
def transcribe_audio():
    """API endpoint to transcribe an audio file using OpenAI Whisper."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    try:
        file_tuple = (file.filename, file.read(), file.mimetype)
        transcript = openai.audio.transcriptions.create(model="whisper-1", file=file_tuple)
        return jsonify({"text": transcript.text})
    except Exception as e:
        logging.error(f"Error during transcription: {e}")
        return jsonify({"error": "Failed to transcribe audio"}), 500

@bp.route('/synthesize-speech', methods=['POST'])
def synthesize_speech():
    """API endpoint to synthesize text to speech and stream the audio back."""
    data = request.get_json()
    text_to_speak = data.get('text')

    if not text_to_speak:
        return jsonify({"error": "text is required"}), 400

    try:
        response = openai.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text_to_speak
        )
        return Response(response.iter_bytes(), mimetype="audio/mpeg")
    except Exception as e:
        logging.error(f"Error during speech synthesis: {e}")
        return jsonify({"error": "Failed to synthesize speech"}), 500