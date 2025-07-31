import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from twilio.rest import Client
from config.config_handler import load_config, save_config
from fastapi import APIRouter
from fastapi import Form
from fastapi import Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import os

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config_router = APIRouter()

# Load current config
current_config = load_config()

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), '..', 'templates'))

def validate_twilio_credentials(account_sid: str, auth_token: str) -> str:
    """Check if Twilio credentials are valid by fetching account info"""
    try:
        client = Client(account_sid, auth_token)
        account = client.api.accounts(account_sid).fetch()
        return account.friendly_name
    except Exception as e:
        logger.error(f"Twilio credential validation failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid Twilio credentials.")

@config_router.get("/twilio-config", tags=["Config twilio Credentials"])
def get_config():
    """Return the currently stored Twilio configuration (safe fields only)"""
    safe_config = {k: v for k, v in current_config.items() if "TOKEN" not in k}
    return safe_config

@config_router.get("/twilio-config-form", response_class=HTMLResponse)
def twilio_config_form(request: Request, message: str = None, error: str = None):
    return templates.TemplateResponse("twilio_config.html", {
        "request": request,
        "message": message,
        "error": error,
        "config": current_config
    })

@config_router.post("/twilio-config-form", response_class=HTMLResponse)
async def twilio_config_form_post(
    request: Request,
    TWILIO_ACCOUNT_SID: str = Form(...),
    TWILIO_AUTH_TOKEN: str = Form(...),
    TWILIO_PHONE_NUMBER: str = Form(...),
    webhook_url: str = Form(...)
):
    try:
        friendly_name = validate_twilio_credentials(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        global current_config
        current_config = {
            "TWILIO_ACCOUNT_SID": TWILIO_ACCOUNT_SID,
            "TWILIO_AUTH_TOKEN": TWILIO_AUTH_TOKEN,
            "TWILIO_PHONE_NUMBER": TWILIO_PHONE_NUMBER,
            "webhook_url": webhook_url
        }
        save_config(current_config)
        message = f"Twilio credentials valid for: {friendly_name}"
        return templates.TemplateResponse("twilio_config.html", {
            "request": request,
            "message": message,
            "error": None,
            "config": current_config
        })
    except HTTPException as e:
        return templates.TemplateResponse("twilio_config.html", {
            "request": request,
            "message": None,
            "error": e.detail,
            "config": current_config
        })