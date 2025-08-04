from fastapi import FastAPI
from routes import router
import uvicorn
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Check if environment variables are loaded correctly
api_key = os.getenv("API_KEY")
github_token = os.getenv("GITHUB_TOKEN")

if not api_key:
    raise RuntimeError("API_KEY is not set in environment variables.")
if not github_token:
    raise RuntimeError("GITHUB_TOKEN is not set in environment variables.")

logging.info(f"API_KEY: {api_key[:5]}... (truncated for security)")
logging.info(f"GITHUB_TOKEN: {github_token[:5]}... (truncated for security)")

app = FastAPI()

# Include the router
app.include_router(router)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
