from fastapi import APIRouter, HTTPException, UploadFile, File, Request, Response, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from models import NewsRequest, PublishRequest
from pydantic import BaseModel
from api_clients import process_article
from publish import publish_news_to_wordpress, get_wordpress_categories
import aiohttp
import logging
import traceback
import os
import requests
import uuid
import base64
import hashlib
import secrets
from passlib.hash import bcrypt
from config import settings # Import settings

router = APIRouter()
logger = logging.getLogger(__name__)

TEMP_UPLOAD_DIR = "temp_uploads"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

SESSION_TOKEN_NAME = "app_session"
SESSION_TOKEN_LENGTH = 32
SESSION_TOKEN_EXPIRY_SECONDS = 3600 * 24 # 24 hours

def get_html_file_path(filename: str):
    # Prioritize 'static' directory for HTML files
    possible_paths = [
        os.path.join(os.getcwd(), 'static', filename), # Common for static files
        os.path.join(os.path.dirname(__file__), 'static', filename),
        os.path.join(os.path.dirname(__file__), 'templates', filename), # Fallback for older structure
        os.path.join(os.path.dirname(__file__), '..', 'templates', filename),
        os.path.join(os.getcwd(), 'templates', filename),
        os.path.join(os.getcwd(), filename)
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

async def verify_authentication(request: Request):
    session_token = request.cookies.get(SESSION_TOKEN_NAME)
    if not session_token or session_token != request.app.state.valid_session_token:
        logger.info("Unauthenticated access attempt. Redirecting to login.")
        # Use RedirectResponse for proper HTTP redirect
        response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        raise HTTPException(status_code=status.HTTP_302_FOUND, detail="Not authenticated", headers={"Location": "/login"})
    return True

class LoginRequest(BaseModel):
    password: str

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    login_html_path = get_html_file_path('login.html')
    if not login_html_path:
        logger.error("login.html not found.")
        raise HTTPException(status_code=500, detail="Login page not found.")
    with open(login_html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@router.post("/login")
async def perform_login(login_request: LoginRequest, request: Request, response: Response):
    stored_password_hash = request.app.state.settings.ACCESS_PASSWORD_HASH

    if not stored_password_hash:
        logger.error("ACCESS_PASSWORD_HASH is not set in app state. Cannot verify password.")
        raise HTTPException(status_code=500, detail="Server configuration error: Password hash not set.")

    logger.debug(f"Attempting login for password (first 5 chars): {login_request.password[:5]}...")
    logger.debug(f"Stored hash (first 10 chars): {stored_password_hash[:10]}...")

    try:
        is_valid_password = bcrypt.verify(login_request.password, stored_password_hash)
    except ValueError as ve:
        logger.error(f"ValueError during password verification (likely malformed hash): {ve}")
        raise HTTPException(status_code=500, detail="Server error: Password hash configuration issue.")
    except Exception as e:
        logger.critical(f"A truly unexpected error occurred during password verification: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unhandled internal server error occurred during password verification.")

    if is_valid_password:
        new_session_token = secrets.token_urlsafe(SESSION_TOKEN_LENGTH)
        request.app.state.valid_session_token = new_session_token

        try:
            with open(request.app.state.settings.SESSION_TOKEN_FILE, "w") as f:
                f.write(new_session_token)
            logger.info(f"New session token saved to {request.app.state.settings.SESSION_TOKEN_FILE}")
        except IOError as e:
            logger.error(f"Failed to save session token to file {request.app.state.settings.SESSION_TOKEN_FILE}: {e}")

        response.set_cookie(
            key=SESSION_TOKEN_NAME,
            value=new_session_token,
            httponly=True,
            samesite="lax",
            secure=True,
            max_age=SESSION_TOKEN_EXPIRY_SECONDS # Set cookie expiry
        )
        logger.info("Login successful. Session cookie set.")
        return {"message": "Login successful"}
    else:
        logger.warning("Login failed: Invalid password provided.")
        raise HTTPException(status_code=401, detail="Invalid password.")

@router.post("/logout")
async def perform_logout(request: Request, response: Response):
    # Invalidate the current session token in memory and file
    request.app.state.valid_session_token = secrets.token_urlsafe(SESSION_TOKEN_LENGTH)
    try:
        with open(request.app.state.settings.SESSION_TOKEN_FILE, "w") as f:
            f.write(request.app.state.valid_session_token)
        logger.info(f"New random token written to {request.app.state.settings.SESSION_TOKEN_FILE} on logout.")
    except IOError as e:
        logger.error(f"Failed to write new random token to file {request.app.state.settings.SESSION_TOKEN_FILE} on logout: {e}")

    # Clear the session cookie
    response.delete_cookie(key=SESSION_TOKEN_NAME, httponly=True, samesite="lax", secure=True)
    logger.info("Logout successful. Session cookie cleared.")
    return {"message": "Logout successful"}


@router.get("/", response_class=HTMLResponse)
async def home(authenticated: bool = Depends(verify_authentication)):
    try:
        html_file_path = get_html_file_path('index.html')
        if not html_file_path:
            logger.error("index.html not found.")
            raise FileNotFoundError("index.html not found.")

        with open(html_file_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except HTTPException as e:
        raise e
    except FileNotFoundError as e:
        logger.error(f"Failed to load index.html: {e}")
        raise HTTPException(status_code=500, detail="Frontend application file not found.")
    except Exception as e:
        logger.error(f"An unexpected error occurred while serving index.html: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@router.get("/wp-categories", dependencies=[Depends(verify_authentication)])
async def get_categories_from_wp_route():
    try:
        categories_list = []
        # Use the get_wordpress_categories function from publish.py
        wp_categories_map = get_wordpress_categories(
            settings.WORDPRESS_SITE_URL,
            settings.WORDPRESS_APP_PASSWORD
        )
        for name, id_val in wp_categories_map.items():
            # Note: get_wordpress_categories only returns name:id. Slug is not available directly.
            # If slug is critical, you'd need a more detailed WP API call or cache.
            categories_list.append({"id": id_val, "name": name, "slug": name.lower().replace(" ", "-")}) # Placeholder slug

        return categories_list
    except Exception as e:
        logger.error(f"Error fetching categories from WordPress: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch categories from WordPress: {str(e)}")

@router.post("/rewrite", dependencies=[Depends(verify_authentication)])
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
            "openrouter_gemma": "Openrouter Gemma",
            "openrouter_claude3": "Openrouter Claude-3"
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
            logger.warning(f"No response from {api_name_for_display} for rewrite request.")
            raise HTTPException(
                status_code=500,
                detail=f"Unable to process your request with {api_name_for_display}. No content returned."
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in rewrite endpoint: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An unexpected error occurred during news rewriting.")

@router.post("/upload-image", dependencies=[Depends(verify_authentication)])
async def upload_image(file: UploadFile = File(...)):
    if not settings.WORDPRESS_SITE_URL or not settings.WORDPRESS_APP_PASSWORD:
        logger.error("WORDPRESS_SITE_URL or WORDPRESS_APP_PASSWORD environment variables are not set for image upload.")
        raise HTTPException(status_code=500, detail="Server configuration error: WordPress credentials missing.")

    upload_url = f"{settings.WORDPRESS_SITE_URL}/wp-json/wp/v2/media"
    temp_file_path = None

    try:
        file_content = await file.read()
        file_size = len(file_content)
        logger.info(f"Received file: {file.filename}, size: {file_size} bytes, content-type: {file.content_type}")
        logger.debug(f"FastAPI received content SHA256 (first 1KB): {hashlib.sha256(file_content[:1024]).hexdigest()}")

        original_filename = file.filename if file.filename else "uploaded_file"
        file_extension = os.path.splitext(original_filename)[1]
        if not file_extension:
            if file.content_type and file.content_type.startswith("image/"):
                file_extension = "." + file.content_type.split("/")[1]
            else:
                file_extension = ".bin"

        temp_filename = f"{uuid.uuid4()}{file_extension}"
        temp_file_path = os.path.join(TEMP_UPLOAD_DIR, temp_filename)

        with open(temp_file_path, "wb") as buffer:
            buffer.write(file_content)
        logger.info(f"Saved temporary file to: {temp_file_path}")
        with open(temp_file_path, "rb") as check_buffer:
            temp_file_content_check = check_buffer.read()
            logger.debug(f"Temp file content SHA256 (first 1KB, from disk): {hashlib.sha256(temp_file_content_check[:1024]).hexdigest()}")
            logger.debug(f"Temp file size on disk: {os.path.getsize(temp_file_path)} bytes")

        auth_string = settings.WORDPRESS_APP_PASSWORD
        encoded_auth = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')

        actual_content_type = file.content_type if file.content_type else "application/octet-stream"

        headers = {
            "Content-Disposition": f"attachment; filename={original_filename}",
            "Content-Type": actual_content_type,
            "Authorization": f"Basic {encoded_auth}"
        }

        with open(temp_file_path, "rb") as f_to_upload:
            logger.info(f"Proxying image upload to WordPress from temporary file: {upload_url} for file {original_filename} ({file_size} bytes) with Content-Type: {actual_content_type}")
            wp_response = requests.post(upload_url, headers=headers, data=f_to_upload, timeout=30)

        if wp_response.status_code == 201:
            wp_data = wp_response.json()
            logger.info(f"Image uploaded to WordPress successfully. Media ID: {wp_data.get('id')}")
            return {"message": "Image uploaded successfully", "id": wp_data.get("id")}
        else:
            error_detail = f"WordPress upload failed: Status {wp_response.status_code}. "
            try:
                error_json = wp_response.json()
                error_detail += f"Message: {error_json.get('message', 'No message provided.')}"
            except json.JSONDecodeError:
                error_detail += f"Response: {wp_response.text[:200]}..."
            logger.error(error_detail)
            raise HTTPException(status_code=wp_response.status_code, detail=error_detail)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to WordPress for image upload: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to WordPress: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during image upload proxy: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Cleaned up temporary file: {temp_file_path}")
            except Exception as e:
                logger.error(f"Error cleaning up temporary file {temp_file_path}: {e}")

@router.post("/publish", dependencies=[Depends(verify_authentication)])
async def publish(request: PublishRequest):
    try:
        news_content = request.news
        featured_image_id = request.featured_image_id
        categories = request.categories
        tags = request.tags
        post_status = request.post_status # Get post status from request

        if not news_content.strip():
            logger.warning("Publish request received with empty news content.")
            raise HTTPException(status_code=400, detail="News content cannot be empty")

        logger.info(f"Calling publish_news_to_wordpress function to publish news with status: {post_status}")

        publish_data = {
            "news": news_content,
            "featured_image_id": featured_image_id,
            "categories": categories,
            "tags": tags,
            "post_status": post_status # Pass post status
        }

        result = publish_news_to_wordpress(publish_data)

        if result.get("status") == "success":
            logger.info("News published successfully by publish_news_to_wordpress function.")
            return {"message": result.get("message"), "permalink": result.get("permalink")}
        else:
            error_msg = result.get("detail", "Unknown error occurred")
            logger.error(f"Publishing failed via publish_news_to_wordpress function. Error: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Publishing failed: {error_msg}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in publish endpoint: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An unexpected error occurred during news publishing.")
