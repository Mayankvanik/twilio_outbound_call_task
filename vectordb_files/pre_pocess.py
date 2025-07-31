from fastapi import FastAPI, Request, HTTPException, File, UploadFile, Form
import httpx
import os
from typing import Dict, Any, List
import logging
import PyPDF2
import io
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from langchain_openai.embeddings import OpenAIEmbeddings
import uuid
from datetime import datetime
import re 
from typing import Optional, Dict, Any
import logging
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()  # Load variables from .env
openai_api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=openai_api_key)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = "task_pdf_documents"

# Initialize Qdrant client
qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

# Initialize sentence transformer for embeddings
embedding_model = OpenAIEmbeddings(model= 'text-embedding-ada-002',api_key=openai_api_key)

# Initialize FastAPI app



async def initialize_qdrant():
    """Initialize Qdrant collection if it doesn't exist"""
    try:
        # Check if collection exists
        collections = qdrant_client.get_collections()
        collection_exists = any(col.name == COLLECTION_NAME for col in collections.collections)
        
        if not collection_exists:
            # Create collection with vector configuration for OpenAI ada-002 (1536 dimensions)
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )
            logger.info(f"Created Qdrant collection: {COLLECTION_NAME}")
        else:
            logger.info(f"Qdrant collection {COLLECTION_NAME} already exists")
            
    except Exception as e:
        logger.error(f"Error initializing Qdrant: {e}")
        raise e

def extract_text_from_pdf(pdf_file: bytes) -> str:
    """Extract text from PDF file"""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_file))
        text = ""
        
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
            
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to extract text from PDF: {str(e)}")

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks"""
    if not text:
        return []
    
    # Clean and normalize text
    text = re.sub(r'\s+', ' ', text).strip()
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # If we're not at the end, try to break at a sentence or word boundary
        if end < len(text):
            # Look for sentence boundary (. ! ?)
            sentence_end = text.rfind('.', start, end)
            if sentence_end == -1:
                sentence_end = text.rfind('!', start, end)
            if sentence_end == -1:
                sentence_end = text.rfind('?', start, end)
            
            # If no sentence boundary, look for word boundary
            if sentence_end == -1:
                word_end = text.rfind(' ', start, end)
                if word_end != -1:
                    end = word_end
            else:
                end = sentence_end + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start position with overlap
        start = end - overlap
        if start < 0:
            start = end
            
    return chunks

async def store_chunks_in_qdrant(chunks: List[str], username: str, filename: str) -> Dict[str, Any]:
    """Store text chunks in Qdrant with metadata"""
    try:
        points = []
        document_id = str(uuid.uuid4())
        
        for i, chunk in enumerate(chunks):
            # Generate embedding using OpenAI
            embedding = await embedding_model.aembed_query(chunk)
            
            # Create point with metadata
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "text": chunk,
                    "username": username,
                    "filename": filename,
                    "document_id": document_id,
                    "chunk_index": i,
                    "created_at": datetime.now().isoformat(),
                    "chunk_length": len(chunk)
                }
            )
            points.append(point)
        
        # Upload points to Qdrant
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        
        return {
            "document_id": document_id,
            "chunks_stored": len(chunks),
            "total_points": len(points)
        }
        
    except Exception as e:
        logger.error(f"Error storing chunks in Qdrant: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to store chunks: {str(e)}")


async def search_document_vector_db(query,username,limit,score_threshold):
    """Search documents in Qdrant with optional username filtering"""
    try:
        if not query or query.strip() == "":
            raise HTTPException(status_code=400, detail="Query is required")
        
        # Generate query embedding using OpenAI
        query_embedding = await embedding_model.aembed_query(query) #.strip()
        
        # Prepare search filter
        search_filter = None
        if username:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="username",
                        match=MatchValue(value=username)
                    )
                ]
            )
        
        # Search in Qdrant  
            # query_filter=search_filter,
        search_results = qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_embedding,
            query_filter=search_filter,
            limit=limit,
            score_threshold=score_threshold
        )
        
        # Format results
        results = []
        for result in search_results:
            results.append({
                "id": result.id,
                "score": result.score,
                "text": result.payload.get("text", ""),
                "username": result.payload.get("username", ""),
                "filename": result.payload.get("filename", ""),
                "document_id": result.payload.get("document_id", ""),
                "chunk_index": result.payload.get("chunk_index", 0),
                "created_at": result.payload.get("created_at", "")
            })
        
        return {
            "status": "success",
            "query": query,
            "username_filter": username,
            "total_results": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
    

async def rag_qna_chatbot(
    user_query: str,
    username: str = None,
    search_limit: int = 5,
    score_threshold: float = 0.2,
    max_context_length: int = 4000,
    temperature: float = 0.3
) -> Dict[str, Any]:
    """
    RAG-powered Q&A chatbot for customer support/sales
    
    Args:
        user_query: User's question
        username: Optional username for filtering documents
        search_limit: Number of documents to retrieve
        score_threshold: Minimum similarity score for retrieved documents
        max_context_length: Maximum characters for context
        temperature: OpenAI temperature setting
    
    Returns:
        Dict containing the answer, sources, and metadata
    """
    try:
        # Step 1: Retrieve relevant documents using your search function
        search_response = await search_document_vector_db(
            query=user_query,
            username=username,
            limit=search_limit,
            score_threshold=score_threshold
        )
        print('search_response',search_response)
        if not search_response["results"]:
            return {
                "status": "success",
                "answer": "I apologize, but I couldn't find relevant information to answer your question. Could you please rephrase your question or provide more details? Our team is here to help you!",
                "sources": [],
                "confidence": "low",
                "query": user_query
            }
        
        # Step 2: Prepare context from retrieved documents
        context_chunks = []
        sources = []
        total_context_length = 0
        
        for result in search_response["results"]:
            chunk_text = result["text"]
            
            # Check if adding this chunk would exceed context limit
            if total_context_length + len(chunk_text) > max_context_length:
                break
                
            context_chunks.append(chunk_text)
            total_context_length += len(chunk_text)
            
            # Track sources
            source_info = {
                "filename": result["filename"],
                "document_id": result["document_id"],
                "chunk_index": result["chunk_index"],
                "score": round(result["score"], 3),
                "created_at": result["created_at"]
            }
            sources.append(source_info)
        
        context = "\n\n".join(context_chunks)
        
        # Step 3: Create the prompt for the LLM
        system_prompt = """You are a confident, helpful assistant designed to answer customer questions clearly and concisely. 

Your tone should be:
- Friendly but direct
- Human, not robotic
- Focused on giving short, useful answers

Rules:
- DO NOT start answers with phrases like "Based on the context" or "According to the information provided"
- Avoid unnecessary wrapping like "I'm happy to help" unless context demands it
- If you don't have the info, say so briefly and clearly
- If asked about a person, product, or feature, give the most relevant fact straight away
- Assume you're chatting with a human—sound like one
"""

        user_prompt = f"""Context Information:
{context}

Customer Question: {user_query}

Please provide a helpful and accurate answer based on the context above. If the context doesn't contain enough information to fully answer the question, please let the customer know politely and offer alternative assistance."""


        response = client.responses.create(
            model="gpt-4.1",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        answer = response.output_text
        
        # Step 5: Determine confidence based on search results
        avg_score = sum(result["score"] for result in search_response["results"]) / len(search_response["results"])
        
        if avg_score >= 0.85:
            confidence = "high"
        elif avg_score >= 0.7:
            confidence = "medium"
        else:
            confidence = "low"
        
        return {
            "status": "success",
            "answer": answer,
            "sources": sources,
            "confidence": confidence,
            "query": user_query,
            "total_sources_found": len(search_response["results"]),
            "context_used": len(context_chunks),
            "average_similarity_score": round(avg_score, 3)
        }
        
    except Exception as e:
        logger.error(f"Error in RAG Q&A: {e}")
        return {
            "status": "error",
            "answer": "I apologize, but I'm experiencing technical difficulties at the moment. Please try again in a few moments, or feel free to contact our support team directly for immediate assistance.",
            "sources": [],
            "confidence": "error",
            "query": user_query,
            "error": str(e)
        }


# Alternative version with synchronous OpenAI (if you prefer sync)
def rag_qna_chatbot_sync(
    user_query: str,
    username: str = None,
    search_limit: int = 5,
    score_threshold: float = 0.7,
    max_context_length: int = 4000,
    temperature: float = 0.3
) -> Dict[str, Any]:
    """
    Synchronous version of the RAG Q&A chatbot
    Note: You'll need to modify this to work with your async search_documents function
    """
    import asyncio
    
    # Run the async function in a sync context
    return asyncio.run(rag_qna_chatbot(
        user_query=user_query,
        username=username,
        search_limit=search_limit,
        score_threshold=score_threshold,
        max_context_length=max_context_length,
        temperature=temperature
    ))


# Example usage function
async def example_usage():
    """Example of how to use the RAG Q&A function"""
    
    # Example 1: General query
    response1 = await rag_qna_chatbot(
        user_query="What's skills mayank vanik have?",
        username="string"
    )
    print("Response 1:", response1["answer"])
    print("Confidence:", response1["confidence"])
    print("Sources used:", len(response1["sources"]))
    

import asyncio
