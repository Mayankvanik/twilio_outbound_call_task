import os
from twilio.rest import Client
from fastapi import HTTPException
from config.twilio_config_handler import load_twilio_config
import logging

logger = logging.getLogger(__name__)

twilio_config = load_twilio_config()
TWILIO_ACCOUNT_SID = twilio_config.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = twilio_config.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = twilio_config.get("TWILIO_PHONE_NUMBER")

def validate_twilio_credentials():
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        return twilio_client
    except Exception as e:
        logger.error(f"Twilio credential validation failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid Twilio credentials.")

twilio_client = validate_twilio_credentials()

async def list_phone_numbers_service():
    try:
        incoming_numbers = twilio_client.incoming_phone_numbers.list()
        numbers_list = []
        for number in incoming_numbers:
            numbers_list.append({
                "phone_number": number.phone_number,
                "sid": number.sid,
                "friendly_name": number.friendly_name,
                "voice_url": number.voice_url,
                "voice_method": number.voice_method,
                "capabilities": {
                    "voice": number.capabilities.get('voice', False),
                    "sms": number.capabilities.get('sms', False),
                    "mms": number.capabilities.get('mms', False)
                }
            })
        return {
            "status": "success",
            "total_numbers": len(numbers_list),
            "phone_numbers": numbers_list
        }
    except Exception as e:
        logger.error(f"Error listing phone numbers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list phone numbers: {str(e)}")

async def setup_webhook_service(webhook_url: str):
    try:
        voice_webhook_url = f"{webhook_url}/voice/incoming"
        # Test Twilio connection
        try:
            account = twilio_client.api.accounts(TWILIO_ACCOUNT_SID).fetch()
            logger.info(f"Twilio connection verified for account: {account.friendly_name}")
        except Exception as auth_error:
            logger.error(f"Twilio authentication failed: {auth_error}")
            raise HTTPException(status_code=401, detail=f"Twilio authentication failed: {str(auth_error)}")
        # List all incoming phone numbers to find the right one
        try:
            incoming_numbers = twilio_client.incoming_phone_numbers.list()
            logger.info(f"Found {len(incoming_numbers)} phone numbers in account")
            target_number = None
            for number in incoming_numbers:
                logger.info(f"Available number: {number.phone_number} (SID: {number.sid})")
                if number.phone_number == TWILIO_PHONE_NUMBER:
                    target_number = number
                    break
            if not target_number:
                if incoming_numbers:
                    target_number = incoming_numbers[0]
                    logger.warning(f"Exact number match not found. Using first available: {target_number.phone_number}")
                else:
                    raise HTTPException(status_code=404, detail=f"No phone numbers found in Twilio account")
        except Exception as list_error:
            logger.error(f"Error listing phone numbers: {list_error}")
            raise HTTPException(status_code=500, detail=f"Error accessing phone numbers: {str(list_error)}")
        # Update the phone number's webhook
        try:
            updated_number = twilio_client.incoming_phone_numbers(target_number.sid).update(
                voice_url=voice_webhook_url,
                voice_method='POST'
            )
            logger.info(f"Webhook updated successfully for {updated_number.phone_number}")
            return {
                "status": "success",
                "phone_number": updated_number.phone_number,
                "voice_webhook_url": voice_webhook_url,
                "message": "Webhook configured successfully",
                "number_sid": updated_number.sid
            }
        except Exception as update_error:
            logger.error(f"Error updating webhook: {update_error}")
            raise HTTPException(status_code=500, detail=f"Error updating webhook: {str(update_error)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error setting up webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

async def get_webhook_info_service():
    try:
        incoming_numbers = twilio_client.incoming_phone_numbers.list()
        if not incoming_numbers:
            raise HTTPException(status_code=404, detail="No phone numbers found in account")
        target_number = None
        for number in incoming_numbers:
            if number.phone_number == TWILIO_PHONE_NUMBER:
                target_number = number
                break
        if not target_number:
            target_number = incoming_numbers[0]
        return {
            "phone_number": target_number.phone_number,
            "sid": target_number.sid,
            "voice_url": target_number.voice_url,
            "voice_method": target_number.voice_method,
            "status_callback": target_number.status_callback,
            "status_callback_method": target_number.status_callback_method,
            "friendly_name": target_number.friendly_name
        }
    except Exception as e:
        logger.error(f"Error getting webhook info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get webhook info: {str(e)}")

async def test_twilio_auth_service():
    try:
        account = twilio_client.api.accounts(TWILIO_ACCOUNT_SID).fetch()
        incoming_numbers = twilio_client.incoming_phone_numbers.list()
        numbers_info = []
        for number in incoming_numbers:
            numbers_info.append({
                "phone_number": number.phone_number,
                "sid": number.sid,
                "friendly_name": number.friendly_name,
                "voice_url": number.voice_url,
                "voice_method": number.voice_method
            })
        return {
            "status": "success",
            "account_name": account.friendly_name,
            "account_sid": account.sid,
            "account_status": account.status,
            "phone_numbers": numbers_info,
            "total_numbers": len(numbers_info)
        }
    except Exception as e:
        logger.error(f"Twilio authentication test failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "account_sid": TWILIO_ACCOUNT_SID[:8] + "...",
            "message": "Check your Twilio credentials"
        } 