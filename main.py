from fastapi import FastAPI
from routes.twilo_talk import router as api_router
from routes.config_twilio import config_router as config_router


tags_metadata = [
    {
        "name": "Config twilio Credentials",
        "description": "Endpoints to update and get Twilio credentials",
    },
    {
        "name": "twilio test apis",
        "description": "Test APIs related to Twilio functionality",
    },
]
# Initialize FastAPI app
app = FastAPI(
    title="Twilio Voice Bot API",
    description="A Twilio voice bot with RAG integration",
    openapi_tags=tags_metadata
)

# Include the routes
app.include_router(api_router, prefix="/api")
app.include_router(config_router, prefix="/config")

@app.get("/")
def root():
    return {"message": "Welcome to the main FastAPI app"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
