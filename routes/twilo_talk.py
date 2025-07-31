import os
import io
import logging
from fastapi import Request, HTTPException, Form
from fastapi.responses import Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
import requests
import logging
from dotenv import load_dotenv
from config.twilio_config_handler import load_twilio_config
import logging
from fastapi import HTTPException
from twilio.rest import Client
from config.config_handler import load_config
from vectordb_files.utils import text_to_speech , get_response_for_message
from vectordb_files.pre_pocess import rag_qna_chatbot,extract_text_from_pdf, chunk_text,initialize_qdrant,store_chunks_in_qdrant,search_document_vector_db,TTS_response
from fastapi import FastAPI, Request, HTTPException, File, UploadFile, Form



from fastapi import APIRouter
load_dotenv(override=True)
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")
stt_client = OpenAI(api_key=openai_api_key)
embedding_model = OpenAIEmbeddings(model='text-embedding-ada-002', api_key=openai_api_key)

# Qdrant configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = "task_pdf_documents"
qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

# Load config from JSON
twilio_config = load_twilio_config()

TWILIO_ACCOUNT_SID = twilio_config.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = twilio_config.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = twilio_config.get("TWILIO_PHONE_NUMBER")
webhook_url =  twilio_config.get("webhook_url")

# [Refactored: All business logic, setup, and utility functions have been moved to the 'services' package.]
# Only FastAPI route definitions and request/response handling remain here, importing from services.

from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from services.twilio_client import (
    twilio_client, TWILIO_PHONE_NUMBER, validate_twilio_credentials, list_phone_numbers_service, setup_webhook_service, get_webhook_info_service, test_twilio_auth_service
)
from services.openai_client import openai_api_key
from services.call_logic import (
    handle_incoming_call_logic, process_recording_logic, handle_continue_logic, handle_transcription_logic, make_outbound_call_logic, handle_outbound_call_logic, make_interactive_call_logic
)
import os

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), '..', 'templates'))

@router.get("/")
async def root():
    return {"status": "Twilio Voice Bot is running", "bot_name": "RAG_Voice_Bot", "version": "1.0.0", "twilio_number": TWILIO_PHONE_NUMBER}

@router.get("/health")
async def health_check():
    return {"status": "healthy", "twilio_configured": bool(twilio_client), "openai_configured": bool(openai_api_key)}

@router.post("/voice/incoming", tags=["twilio test apis"])
async def handle_incoming_call(request: Request):
    return await handle_incoming_call_logic(request)

@router.post("/voice/process_recording", tags=["twilio test apis"])
async def process_recording(request: Request):
    return await process_recording_logic(request)

@router.post("/voice/continue")
async def handle_continue(request: Request):
    return await handle_continue_logic(request)

@router.post("/voice/transcription")
async def handle_transcription(request: Request):
    return await handle_transcription_logic(request)

@router.post("/make_call", tags=["twilio test apis"])
async def make_outbound_call(phone_number: str, message: str = None, interactive: bool = False):
    return await make_outbound_call_logic(phone_number, message, interactive)

@router.post("/voice/outbound", tags=["twilio test apis"])
async def handle_outbound_call(request: Request):
    return await handle_outbound_call_logic(request)

@router.post("/make_interactive_call", tags=["twilio test apis"])
async def make_interactive_call(phone_number: str = Form(...), initial_message: str = Form(None)):
    return await make_interactive_call_logic(phone_number, initial_message)

@router.get("/make_interactive_call_form", response_class=HTMLResponse)
async def make_interactive_call_form(request: Request, message: str = None, error: str = None):
    return templates.TemplateResponse("make_interactive_call.html", {"request": request, "message": message, "error": error, "phone_number": "", "initial_message": ""})

@router.post("/make_interactive_call_form", response_class=HTMLResponse)
async def make_interactive_call_form_post(request: Request, phone_number: str = Form(...), initial_message: str = Form("")):
    try:
        result = await make_interactive_call_logic(phone_number, initial_message)
        return templates.TemplateResponse("make_interactive_call.html", {"request": request, "message": result.get("message", "Interactive call initiated successfully!"), "error": None, "phone_number": phone_number, "initial_message": initial_message})
    except HTTPException as he:
        return templates.TemplateResponse("make_interactive_call.html", {"request": request, "message": None, "error": he.detail, "phone_number": phone_number, "initial_message": initial_message})
    except Exception as e:
        return templates.TemplateResponse("make_interactive_call.html", {"request": request, "message": None, "error": f"Failed to make interactive call: {str(e)}", "phone_number": phone_number, "initial_message": initial_message})

@router.get("/setup_webhook")
async def setup_webhook(webhook_url: str):
    return await setup_webhook_service(webhook_url)

@router.get("/webhook_info")
async def get_webhook_info():
    return await get_webhook_info_service()

@router.get("/list_phone_numbers")
async def list_phone_numbers():
    return await list_phone_numbers_service()

@router.get("/test_twilio_auth")
async def test_twilio_auth():
    return await test_twilio_auth_service()

@router.post("/upload_pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    username: str = Form(...),
    chunk_size: int = Form(1000),
    overlap: int = Form(200)
):
    """Upload PDF file, process it into chunks, and store in Qdrant"""
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    if not username or username.strip() == "":
        raise HTTPException(status_code=400, detail="Username is required")
    
    try:
        # Read file content
        file_content = await file.read()
        
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        logger.info(f"Processing PDF: {file.filename} for user: {username}")
        
        # Extract text from PDF
        text = extract_text_from_pdf(file_content)
        
        if not text or len(text.strip()) < 10:
            raise HTTPException(status_code=400, detail="No readable text found in PDF")
        
        # Create text chunks
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        
        if not chunks:
            raise HTTPException(status_code=400, detail="Failed to create text chunks")
        
        # Initialize Qdrant if needed
        await initialize_qdrant()
        
        # Store chunks in Qdrant
        storage_result = await store_chunks_in_qdrant(chunks, username.strip(), file.filename)
        
        return {
            "status": "success",
            "message": "PDF processed and stored successfully",
            "filename": file.filename,
            "username": username,
            "file_size_bytes": len(file_content),
            "extracted_text_length": len(text),
            "total_chunks": len(chunks),
            "chunk_size": chunk_size,
            "overlap": overlap,
            "storage_result": storage_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing PDF upload: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

