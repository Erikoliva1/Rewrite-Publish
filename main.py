from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from routes import router
import uvicorn
import os
import logging
import secrets
from passlib.hash import bcrypt
from config import settings # Import settings from the new config.py

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# Load settings from config.py
app.state.settings = settings

# Initialize session token
if os.path.exists(app.state.settings.SESSION_TOKEN_FILE):
    with open(app.state.settings.SESSION_TOKEN_FILE, "r") as f:
        app.state.valid_session_token = f.read().strip()
    logger.info(f"Loaded session token from {app.state.settings.SESSION_TOKEN_FILE}")
else:
    app.state.valid_session_token = secrets.token_urlsafe(32)
    with open(app.state.settings.SESSION_TOKEN_FILE, "w") as f:
        f.write(app.state.valid_session_token)
    logger.info(f"Generated new session token and saved to {app.state.settings.SESSION_TOKEN_FILE}")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(router)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    host = os.environ.get("HOST", "0.0.0.0")
    logger.info(f"Starting Uvicorn server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

