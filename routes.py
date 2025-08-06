
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from models import NewsRequest, PublishRequest
from api_clients import process_article
import aiohttp
import logging
import traceback
import subprocess
import os
import json
import requests
import base64

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_class=HTMLResponse)
async def home():
    try:
        possible_paths = [
            os.path.join(os.path.dirname(__file__), 'templates', 'index.html'),
            os.path.join(os.path.dirname(__file__), '..', 'templates', 'index.html'),
            os.path.join(os.getcwd(), 'templates', 'index.html'),
            os.path.join(os.getcwd(), 'index.html')
        ]

        html_file_path = None
        for path in possible_paths:
            if os.path.exists(path):
                html_file_path = path
                break

        if not html_file_path:
            logger.error(f"index.html not found in any of these locations: {possible_paths}")
            raise FileNotFoundError("index.html not found.")

        with open(html_file_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError as e:
        logger.error(f"Failed to load index.html: {e}")
        raise HTTPException(status_code=500, detail="Frontend application file not found.")
    except Exception as e:
        logger.error(f"An unexpected error occurred while serving index.html: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@router.post("/rewrite")
async def rewrite(request: NewsRequest):
    try:
        news_content = request.news
        selected_api = request.api

        if not news_content.strip():
            logger.warning("Rewrite request received with empty news content.")
            raise HTTPException(status_code=400, detail="News content cannot be empty")

        logger.info(f"Received rewrite request for API: {selected_api}")
        async with aiohttp.ClientSession() as session:
            result = await process_article(session, news_content, selected_api)

        api_mapping_names = {
            "azure_gpt41": "Azure GPT-4.1",
            "azure_gpt41_nano": "Azure GPT-4.1 Nano",
            "openrouter_gpt41_nano": "OpenRouter GPT-4.1 Nano",
            "openrouter_deepseek": "OpenRouter DeepSeek",
            "azure_gpt41_mini": "Azure GPT-4.1 Mini",
            "azure_grok": "Azure Grok",
            "openrouter_gpt35": "OpenRouter GPT-3.5",
            "openrouter_gemma": "OpenRouter Gemma",
            "openrouter_claude3": "OpenRouter Claude-3"
        }
        api_name_for_display = api_mapping_names.get(selected_api, selected_api)

        if result == "RATE_LIMIT_REACHED":
            logger.warning(f"Rate limit reached for {api_name_for_display} during rewrite.")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit reached for {api_name_for_display}. Please try a different API option from the dropdown."
            )
        elif result:
            logger.info(f"Successfully rewrote news using {api_name_for_display}.")
            return {"rewritten_news": result}
        else:
            logger.error(f"No result returned from {api_name_for_display} for rewrite request.")
            raise HTTPException(
                status_code=500,
                detail=f"Unable to process your request with {api_name_for_display}. Please try another API option."
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in rewrite endpoint: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An unexpected error occurred during news rewriting.")

@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    wordpress_site_url = os.getenv("WORDPRESS_SITE_URL")
    wordpress_app_password = os.getenv("WORDPRESS_APP_PASSWORD")

    if not wordpress_site_url or not wordpress_app_password:
        logger.error("WORDPRESS_SITE_URL or WORDPRESS_APP_PASSWORD environment variables are not set for image upload.")
        raise HTTPException(status_code=500, detail="Server configuration error: WordPress credentials missing.")

    upload_url = f"{wordpress_site_url}/wp-json/wp/v2/media"

    try:
        file_content = await file.read()
        auth_string = wordpress_app_password
        encoded_auth = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')

        headers = {
            "Content-Disposition": f"attachment; filename={file.filename}",
            "Content-Type": file.content_type,
            "Authorization": f"Basic {encoded_auth}"
        }

        logger.info(f"Proxying image upload to WordPress: {upload_url} for file {file.filename}")
        wp_response = requests.post(upload_url, headers=headers, data=file_content, timeout=30)

        if wp_response.status_code == 201:
            wp_data = wp_response.json()
            logger.info(f"Image uploaded to WordPress successfully. Media ID: {wp_data.get('id')}")
            return {"message": "Image uploaded successfully", "id": wp_data.get("id")}
        else:
            logger.error(f"WordPress media upload failed with status {wp_response.status_code}: {wp_response.text}")
            raise HTTPException(status_code=wp_response.status_code, detail=f"WordPress upload failed: {wp_response.text}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to WordPress for image upload: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to WordPress: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during image upload proxy: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

@router.post("/publish")
async def publish(request: PublishRequest):
    try:
        news_content = request.news
        featured_image_id = request.featured_image_id
        categories = request.categories
        tags = request.tags

        if not news_content.strip():
            logger.warning("Publish request received with empty news content.")
            raise HTTPException(status_code=400, detail="News content cannot be empty")

        logger.info("Calling publish.py script to publish news with additional metadata.")

        publish_data = {
            "news": news_content,
            "featured_image_id": featured_image_id,
            "categories": categories,
            "tags": tags
        }

        json_data_to_pass = json.dumps(publish_data)

        result = subprocess.run(
            ['python', 'publish.py', json_data_to_pass],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0:
            logger.info("News published successfully by publish.py script.")
            return {"message": "News published successfully"}
        else:
            error_msg = result.stderr or result.stdout or "Unknown error occurred"
            logger.error(f"Publishing failed via publish.py script. Error: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Publishing failed: {error_msg}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in publish endpoint: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An unexpected error occurred during news publishing.")
