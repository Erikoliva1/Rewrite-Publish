from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from routes import router
import uvicorn
import os
from dotenv import load_dotenv
import logging
import secrets
from passlib.hash import bcrypt

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

api_key = os.getenv("API_KEY")
github_token = os.getenv("GITHUB_TOKEN")
wordpress_api_token = os.getenv("WORDPRESS_API_TOKEN")
wordpress_app_password = os.getenv("WORDPRESS_APP_PASSWORD")
wordpress_site_url = os.getenv("WORDPRESS_SITE_URL")
ACCESS_PASSWORD_HASH = os.getenv("ACCESS_PASSWORD")
SESSION_TOKEN_FILE = os.getenv("SESSION_TOKEN_FILE", "session_token.txt")

if not api_key:
    logger.warning("API_KEY is not set in environment variables. OpenRouter API calls might fail.")
if not github_token:
    logger.warning("GITHUB_TOKEN is not set in environment variables. Azure API calls might fail.")
if not wordpress_api_token:
    logger.warning("WORDPRESS_API_TOKEN is not set in environment variables. WordPress publishing might fail.")
if not wordpress_app_password:
    logger.warning("WORDPRESS_APP_PASSWORD is not set in environment variables. Direct WordPress media uploads and category/tag fetching might fail.")
if not wordpress_site_url:
    logger.warning("WORDPRESS_SITE_URL is not set in environment variables. WordPress publishing might fail.")
if not ACCESS_PASSWORD_HASH:
    logger.critical("ACCESS_PASSWORD environment variable (bcrypt hash) is not set. Public access will not be password protected!")
else:
    try:
        bcrypt.verify("test", ACCESS_PASSWORD_HASH)
        logger.info("ACCESS_PASSWORD_HASH loaded and appears to be a valid bcrypt hash.")
    except ValueError:
        logger.critical("ACCESS_PASSWORD environment variable is not a valid bcrypt hash. Please generate one using `bcrypt.hash('your_password')`.")
        ACCESS_PASSWORD_HASH = None

logger.info(f"API_KEY: {'*' * len(api_key) if api_key else 'N/A'}")
logger.info(f"GITHUB_TOKEN: {'*' * len(github_token) if github_token else 'N/A'}")
logger.info(f"WORDPRESS_API_TOKEN: {'*' * len(wordpress_api_token) if wordpress_api_token else 'N/A'}")
logger.info(f"WORDPRESS_APP_PASSWORD: {'*' * len(wordpress_app_password) if wordpress_app_password else 'N/A'}")
logger.info(f"WORDPRESS_SITE_URL: {wordpress_site_url if wordpress_site_url else 'N/A'}")
logger.info(f"ACCESS_PASSWORD_HASH: {'*' * len(ACCESS_PASSWORD_HASH) if ACCESS_PASSWORD_HASH else 'N/A'}")
logger.info(f"SESSION_TOKEN_FILE: {SESSION_TOKEN_FILE}")

app = FastAPI()

if os.path.exists(SESSION_TOKEN_FILE):
    with open(SESSION_TOKEN_FILE, "r") as f:
        app.state.valid_session_token = f.read().strip()
    logger.info(f"Loaded session token from {SESSION_TOKEN_FILE}")
else:
    app.state.valid_session_token = secrets.token_urlsafe(32)
    with open(SESSION_TOKEN_FILE, "w") as f:
        f.write(app.state.valid_session_token)
    logger.info(f"Generated new session token and saved to {SESSION_TOKEN_FILE}")

app.state.access_password_hash = ACCESS_PASSWORD_HASH

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(router)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    host = os.environ.get("HOST", "0.0.0.0")
    logger.info(f"Starting Uvicorn server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
