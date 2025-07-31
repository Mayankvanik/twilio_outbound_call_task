import io
import requests
import logging
from fastapi import Request, HTTPException, Response
from twilio.twiml.voice_response import VoiceResponse
from services.twilio_client import twilio_client, TWILIO_PHONE_NUMBER
from services.openai_client import stt_client
from vectordb_files.utils import get_response_for_message

logger = logging.getLogger(__name__)

call_states = {}

async def handle_incoming_call_logic(request: Request):
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From")
        to_number = form_data.get("To")
        logger.info(f"Incoming call from {from_number} to {to_number}, CallSid: {call_sid}")
        call_states[call_sid] = {"from": from_number, "step": "greeting"}
        response = VoiceResponse()
        welcome_text = "Hello! Welcome to the RAG Voice Assistant. Please speak your question after the beep, and I'll help you find the information you need."
        response.say(welcome_text, voice='alice')
        response.record(
            action="/voice/process_recording",
            method="POST",
            max_length=30,
            finish_on_key="#",
            play_beep=True,
            transcribe=True,
            transcribe_callback="/voice/transcription"
        )
        response.say("I didn't receive your recording. Please try calling again.", voice='alice')
        response.hangup()
        return Response(content=str(response), media_type="application/xml")
    except Exception as e:
        logger.error(f"Error handling incoming call: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error processing your call. Please try again later.", voice='alice')
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

async def process_recording_logic(request: Request):
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        recording_url = form_data.get("RecordingUrl")
        recording_duration = form_data.get("RecordingDuration")
        logger.info(f"Processing recording for call {call_sid}, duration: {recording_duration}s")
        response = VoiceResponse()
        if not recording_url or float(recording_duration or 0) < 1:
            response.say("I didn't receive a clear recording. Please try again.", voice='alice')
            response.hangup()
            return Response(content=str(response), media_type="application/xml")
        audio_response = requests.get(recording_url + ".wav", auth=(twilio_client.username, twilio_client.password))
        if audio_response.status_code == 200:
            audio_file = io.BytesIO(audio_response.content)
            audio_file.name = "recording.wav"
            transcription = stt_client.audio.transcriptions.create(
                model="gpt-4o-transcribe",
                file=audio_file,
                language="en"
            )
            user_question = transcription.text.strip()
            logger.info(f"\n\n\n Transcribed question: {user_question}\n\n\n")
            if user_question:
                rag_response = await get_response_for_message(user_question)
                response.say(f"Based on your Question {rag_response}", voice='alice')
                response.say("Would you like to ask another question? Press 1 for yes, or simply hang up if you're done.", voice='alice')
                gather = response.gather(
                    action="/voice/continue",
                    method="POST",
                    num_digits=1,
                    timeout=10
                )
                gather.say("Press 1 to ask another question, or hang up to end the call.", voice='alice')
                response.say("Thank you for using the RAG Voice Assistant. Goodbye!", voice='alice')
                response.hangup()
            else:
                response.say("I couldn't understand your question. Please try calling again and speak clearly.", voice='alice')
                response.hangup()
        else:
            response.say("There was an error processing your recording. Please try again.", voice='alice')
            response.hangup()
        return Response(content=str(response), media_type="application/xml")
    except Exception as e:
        logger.error(f"Error processing recording: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error processing your question. Please try again.", voice='alice')
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

async def handle_continue_logic(request: Request):
    try:
        form_data = await request.form()
        digits = form_data.get("Digits")
        call_sid = form_data.get("CallSid")
        response = VoiceResponse()
        if digits == "1":
            response.say("Great! Please speak your next question after the beep.", voice='alice')
            response.record(
                action="/voice/process_recording",
                method="POST",
                max_length=30,
                finish_on_key="#",
                play_beep=True,
                transcribe=True
            )
            response.say("I didn't receive your recording. Goodbye!", voice='alice')
            response.hangup()
        else:
            response.say("Thank you for using the RAG Voice Assistant. Have a great day!", voice='alice')
            response.hangup()
        return Response(content=str(response), media_type="application/xml")
    except Exception as e:
        logger.error(f"Error handling continue: {e}")
        response = VoiceResponse()
        response.say("Thank you for calling. Goodbye!", voice='alice')
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

async def handle_transcription_logic(request: Request):
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        transcription_text = form_data.get("TranscriptionText")
        logger.info(f"Transcription for call {call_sid}: {transcription_text}")
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Error handling transcription: {e}")
        return {"status": "error"}

async def make_outbound_call_logic(phone_number: str, message: str = None, interactive: bool = False):
    try:
        if not phone_number.startswith('+'):
            raise HTTPException(status_code=400, detail="Phone number must include country code (e.g., +1234567890)")
        if interactive:
            from config.twilio_config_handler import load_twilio_config
            twilio_config = load_twilio_config()
            webhook_url = twilio_config.get("webhook_url")
            outbound_webhook = f"{webhook_url}/voice/outbound"
            call = twilio_client.calls.create(
                to=phone_number,
                from_=TWILIO_PHONE_NUMBER,
                url=outbound_webhook,
                method='POST'
            )
        else:
            if not message:
                message = "Hello! This is a call from your RAG Voice Assistant. You can call us anytime for questions."
            call = twilio_client.calls.create(
                to=phone_number,
                from_=TWILIO_PHONE_NUMBER,
                twiml=f'<Response><Say voice="alice">{message}</Say></Response>'
            )
        logger.info(f"{'Interactive' if interactive else 'Simple'} outbound call initiated to {phone_number}, SID: {call.sid}")
        return {
            "status": "success",
            "call_sid": call.sid,
            "to": phone_number,
            "from": TWILIO_PHONE_NUMBER,
            "interactive": interactive,
            "message": "Call initiated successfully"
        }
    except Exception as e:
        logger.error(f"Error making outbound call: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to make call: {str(e)}")

async def handle_outbound_call_logic(request: Request):
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        to_number = form_data.get("To")
        from_number = form_data.get("From")
        logger.info(f"Outbound call answered by {to_number}, CallSid: {call_sid}")
        call_states[call_sid] = {"to": to_number, "step": "outbound_greeting", "direction": "outbound"}
        response = VoiceResponse()
        greeting_text = ("Hello! This is your RAG Voice Assistant calling. "
                        "I can help answer questions based on our knowledge base. "
                        "Please speak your question after the beep, and I'll provide you with information.")
        response.say(greeting_text, voice='alice')
        response.record(
            action="/voice/process_recording",
            method="POST",
            max_length=8,
            finish_on_key="#",
            play_beep=True,
            transcribe=True
        )
        response.say("I didn't receive your response. Thank you for your time. Goodbye!", voice='alice')
        response.hangup()
        return Response(content=str(response), media_type="application/xml")
    except Exception as e:
        logger.error(f"Error handling outbound call: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error with this call. Goodbye!", voice='alice')
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

async def make_interactive_call_logic(phone_number: str, initial_message: str = None):
    try:
        if not phone_number.startswith('+'):
            raise HTTPException(status_code=400, detail="Phone number must include country code (e.g., +1234567890)")
        from config.twilio_config_handler import load_twilio_config
        twilio_config = load_twilio_config()
        webhook_url = twilio_config.get("webhook_url")
        if not webhook_url:
            raise HTTPException(status_code=400, detail="WEBHOOK_URL environment variable must be set for interactive calls")
        webhook_url = webhook_url.strip().rstrip('/')
        if not webhook_url.startswith('http'):
            raise HTTPException(status_code=400, detail="WEBHOOK_URL must be a valid HTTP/HTTPS URL")
        outbound_webhook = f"{webhook_url}/voice/outbound"
        logger.info(f"Using webhook URL: {outbound_webhook}")
        call = twilio_client.calls.create(
            to=phone_number,
            from_=TWILIO_PHONE_NUMBER,
            url=outbound_webhook,
            method='POST'
        )
        logger.info(f"Interactive outbound call initiated to {phone_number}, SID: {call.sid}")
        return {
            "status": "success",
            "call_sid": call.sid,
            "to": phone_number,
            "from": TWILIO_PHONE_NUMBER,
            "type": "interactive",
            "webhook_url": outbound_webhook,
            "message": "Interactive call initiated successfully - user can have full conversation with RAG system"
        }
    except Exception as e:
        logger.error(f"Error making interactive outbound call: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to make interactive call: {str(e)}") 