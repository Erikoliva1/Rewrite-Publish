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
import uuid # For generating unique filenames
import base64
import hashlib # ADDED for debugging hashes

router = APIRouter()
logger = logging.getLogger(__name__)

# Define a temporary directory for uploads within the project
# Ensure this directory exists and is writable by the FastAPI process
TEMP_UPLOAD_DIR = "temp_uploads"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)


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
    temp_file_path = None # Initialize to None

    try:
        # 1. Read the incoming file content (the watermarked blob)
        file_content = await file.read()
        file_size = len(file_content)
        logger.info(f"Received file: {file.filename}, size: {file_size} bytes, content-type: {file.content_type}")
        # Log SHA256 hash of the content *received by FastAPI*
        logger.info(f"FastAPI received content SHA256 (first 1KB): {hashlib.sha256(file_content[:1024]).hexdigest()}")


        # 2. Generate a unique temporary filename with the correct extension
        # Ensure file.filename is not None before splitting
        original_filename = file.filename if file.filename else "uploaded_file"
        file_extension = os.path.splitext(original_filename)[1]
        if not file_extension: # Fallback if no extension is found
            # Try to infer from content_type if filename has no extension
            if file.content_type and file.content_type.startswith("image/"):
                file_extension = "." + file.content_type.split("/")[1]
            else:
                file_extension = ".bin" # Generic binary fallback

        temp_filename = f"{uuid.uuid4()}{file_extension}"
        temp_file_path = os.path.join(TEMP_UPLOAD_DIR, temp_filename)

        # 3. Save the received content to the temporary file
        with open(temp_file_path, "wb") as buffer:
            buffer.write(file_content)
        logger.info(f"Saved temporary file to: {temp_file_path}")
        # Log SHA256 hash of the content *written to temp file*
        with open(temp_file_path, "rb") as check_buffer:
            temp_file_content_check = check_buffer.read()
            logger.info(f"Temp file content SHA256 (first 1KB, from disk): {hashlib.sha256(temp_file_content_check[:1024]).hexdigest()}")
            logger.info(f"Temp file size on disk: {os.path.getsize(temp_file_path)} bytes")


        # 4. Prepare for WordPress upload using the saved file
        auth_string = wordpress_app_password
        encoded_auth = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')

        # Use the actual content type from the UploadFile
        actual_content_type = file.content_type if file.content_type else "application/octet-stream"

        headers = {
            "Content-Disposition": f"attachment; filename={original_filename}", # Use original_filename for header
            "Content-Type": actual_content_type,
            "Authorization": f"Basic {encoded_auth}"
        }

        # Open the saved temporary file in binary read mode
        with open(temp_file_path, "rb") as f_to_upload:
            logger.info(f"Proxying image upload to WordPress from temporary file: {upload_url} for file {original_filename} ({file_size} bytes) with Content-Type: {actual_content_type}")
            wp_response = requests.post(upload_url, headers=headers, data=f_to_upload, timeout=30) # <--- Send the file object

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
    finally:
        # 5. Clean up: Delete the temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Cleaned up temporary file: {temp_file_path}")
            except Exception as e:
                logger.error(f"Error cleaning up temporary file {temp_file_path}: {e}")


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
