
from fastapi import FastAPI
from routes import router
import uvicorn
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

api_key = os.getenv("API_KEY")
github_token = os.getenv("GITHUB_TOKEN")
wordpress_api_token = os.getenv("WORDPRESS_API_TOKEN")
wordpress_app_password = os.getenv("WORDPRESS_APP_PASSWORD")
wordpress_site_url = os.getenv("WORDPRESS_SITE_URL")

if not api_key:
    logger.warning("API_KEY is not set in environment variables. OpenRouter API calls might fail.")
if not github_token:
    logger.warning("GITHUB_TOKEN is not set in environment variables. Azure API calls might fail.")
if not wordpress_api_token:
    logger.warning("WORDPRESS_API_TOKEN is not set in environment variables. WordPress publishing might fail.")
if not wordpress_app_password:
    logger.warning("WORDPRESS_APP_PASSWORD is not set in environment variables. Direct WordPress media uploads might fail.")
if not wordpress_site_url:
    logger.warning("WORDPRESS_SITE_URL is not set in environment variables. WordPress publishing might fail.")

logger.info(f"API_KEY: {'*' * len(api_key) if api_key else 'N/A'}")
logger.info(f"GITHUB_TOKEN: {'*' * len(github_token) if github_token else 'N/A'}")
logger.info(f"WORDPRESS_API_TOKEN: {'*' * len(wordpress_api_token) if wordpress_api_token else 'N/A'}")
logger.info(f"WORDPRESS_APP_PASSWORD: {'*' * len(wordpress_app_password) if wordpress_app_password else 'N/A'}")
logger.info(f"WORDPRESS_SITE_URL: {wordpress_site_url if wordpress_site_url else 'N/A'}")

app = FastAPI()
app.include_router(router)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    logger.info(f"Starting Uvicorn server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
