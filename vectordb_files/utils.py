from vectordb_files.pre_pocess import rag_qna_chatbot
import logging ,os 
from openai import OpenAI

from dotenv import load_dotenv



from fastapi import APIRouter
load_dotenv(override=True)
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")
stt_client = OpenAI(api_key=openai_api_key)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_response_for_message(message_text: str) -> str:
    """Get appropriate response from RAG chatbot"""
    try:
        message_lower = message_text.lower().strip()
        # Replace this with your actual RAG function
        answer = await rag_qna_chatbot(
        user_query=message_lower,
        username="string"
        )
        logger.info(f"\n\n\n>> Rag based Answer: {answer['answer']}\n\n\n")
        return answer['answer']
    except Exception as e:
        logger.error(f"Error getting RAG response: {e}")
        return "I'm sorry, I'm having trouble processing your request right now. Please try again."

async def text_to_speech(text: str, output_path: str = "response.mp3") -> str:
    """Convert text to speech using OpenAI TTS"""
    try:
        response = stt_client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        
        with open(output_path, "wb") as f:
            f.write(response.content)
        
        return output_path
    except Exception as e:
        logger.error(f"Error in text-to-speech: {e}")
        return None
