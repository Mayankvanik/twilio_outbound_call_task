import os
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from dotenv import load_dotenv

load_dotenv(override=True)

openai_api_key = os.getenv("OPENAI_API_KEY")
stt_client = OpenAI(api_key=openai_api_key)
embedding_model = OpenAIEmbeddings(model='text-embedding-ada-002', api_key=openai_api_key)

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = "task_pdf_documents"
qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT) 