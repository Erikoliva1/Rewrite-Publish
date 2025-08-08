import requests
import sys
import os
import json
import logging
import traceback
import time
import base64  # Added missing import
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_wordpress_categories(site_url, app_password):
    """Fetches categories from WordPress REST API using Application Password."""
    categories_url = f"{site_url}/wp-json/wp/v2/categories?per_page=100"
    encoded_auth = base64.b64encode(app_password.encode('utf-8')).decode('utf-8')
    headers = {
        'Authorization': f'Basic {encoded_auth}',
        'Content-Type': 'application/json',
        'User-Agent': 'NewsRewriteApp/1.0'
    }
    try:
        response = requests.get(categories_url, headers=headers, timeout=10)
        response.raise_for_status()
        categories_data = response.json()
        category_map = {cat['name']: cat['id'] for cat in categories_data}
        logger.info(f"Successfully fetched {len(category_map)} categories from WordPress.")
        return category_map
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching categories from WordPress: {e}")
        return {}

def get_wordpress_tags(site_url, app_password):
    """Fetches tags from WordPress REST API using Application Password."""
    tags_url = f"{site_url}/wp-json/wp/v2/tags?per_page=100"
    encoded_auth = base64.b64encode(app_password.encode('utf-8')).decode('utf-8')
    headers = {
        'Authorization': f'Basic {encoded_auth}',
        'Content-Type': 'application/json',
        'User-Agent': 'NewsRewriteApp/1.0'
    }
    try:
        response = requests.get(tags_url, headers=headers, timeout=10)
        response.raise_for_status()
        tags_data = response.json()
        tag_map = {tag['name']: tag['id'] for tag in tags_data}
        logger.info(f"Successfully fetched {len(tag_map)} tags from WordPress.")
        return tag_map
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching tags from WordPress: {e}")
        return {}

def publish_news_to_wordpress(news_data):
    WORDPRESS_SITE_URL = os.environ.get("WORDPRESS_SITE_URL")
    WORDPRESS_API_TOKEN = os.environ.get("WORDPRESS_API_TOKEN")
    WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")

    if not WORDPRESS_SITE_URL:
        logger.error("Error: WORDPRESS_SITE_URL environment variable is not set.")
        return {"status": "error", "detail": "WORDPRESS_SITE_URL not set."}
    if not WORDPRESS_API_TOKEN:
        logger.error("Error: WORDPRESS_API_TOKEN environment variable is not set.")
        return {"status": "error", "detail": "WORDPRESS_API_TOKEN not set."}
    if not WORDPRESS_APP_PASSWORD:
        logger.warning("WORDPRESS_APP_PASSWORD environment variable is not set. Category/Tag fetching might fail if WP REST API is protected.")
        wp_categories = {}
    else:
        wp_categories = get_wordpress_categories(WORDPRESS_SITE_URL, WORDPRESS_APP_PASSWORD)

    POST_API_ENDPOINT = f"{WORDPRESS_SITE_URL}/wp-json/news-rewrite-onrender/v1/createpost"

    news_content = news_data.get("news", "")
    featured_image_id = news_data.get("featured_image_id")
    selected_categories_names = news_data.get("categories", [])
    selected_tags_names = news_data.get("tags", [])

    lines = news_content.split('\n', 1)
    title = lines[0].strip() if lines else "Untitled News Article"
    body = lines[1].strip() if len(lines) > 1 else ""

    if not title or not body:
        logger.error("News content must contain both a title and a body.")
        return {"status": "error", "detail": "News content must contain both a title and a body."}

    category_ids = []
    for cat_name in selected_categories_names:
        cat_id = wp_categories.get(cat_name)
        if cat_id:
            category_ids.append(cat_id)
            logger.info(f"Mapped category '{cat_name}' to ID: {cat_id}")
        else:
            logger.warning(f"Category '{cat_name}' not found in WordPress. Skipping.")

    content_lower = (title + " " + body).lower()
    auto_tags = []

    keyword_tags = {
        "सुन": "सुनको भाउ",
        "चाँदी": "चाँदीको भाउ",
        "डलर": "विदेशी मुद्रा",
        "शेयर": "शेयर बजार",
        "बैंक": "बैंकिङ",
        "निर्वाचन": "निर्वाचन",
        "राजनीति": "राजनीति",
        "अर्थ": "अर्थतन्त्र",
        "खेल": "खेलकुद",
        "फुटबल": "खेलकुद",
        "क्रिकेट": "खेलकुद",
        "मौसम": "मौसम",
        "कोभिड": "स्वास्थ्य",
        "स्वास्थ्य": "स्वास्थ्य",
        "शिक्षा": "शिक्षा",
        "प्रविधि": "प्रविधि",
        "Banner": "Banner"
    }

    for keyword, tag in keyword_tags.items():
        if keyword in content_lower and tag not in selected_tags_names:
            auto_tags.append(tag)

    all_tags_to_send = list(set(selected_tags_names + auto_tags))
    logger.info(f"Final tags to be used: {all_tags_to_send}")

    payload = {
        "title": title,
        "content": body,
        "wpToken": WORDPRESS_API_TOKEN,
        "post_status": "publish",
        "catIds": category_ids,
        "tagNames": all_tags_to_send,
        "featured_image_id": featured_image_id
    }

    logger.info(f"Attempting to publish news to: {POST_API_ENDPOINT}")
    logger.info(f"Title: {title}")
    logger.info(f"Body length: {len(body)} characters")
    logger.info(f"Categories (IDs): {category_ids}")
    logger.info(f"Tags (Names): {all_tags_to_send}")
    logger.info(f"Featured Image ID: {featured_image_id if featured_image_id else 'None'}")

    try:
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': WORDPRESS_SITE_URL,
            'Origin': WORDPRESS_SITE_URL,
            'DNT': '1',
            'Connection': 'keep-alive',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty'
        }

        logger.info(f"Sending POST request to {POST_API_ENDPOINT} with JSON payload.")
        response = requests.post(POST_API_ENDPOINT, json=payload, headers=headers, timeout=30)

        logger.info(f"Response status code: {response.status_code}")

        raw_response_text = response.text
        logger.info(f"Raw response content (first 500 chars): {raw_response_text[:500]}...")

        if response.status_code == 200:
            try:
                json_response = response.json()
                if json_response.get("status") == "success":
                    logger.info("News published successfully!")
                    logger.info(f"Permalink: {json_response.get('permalink')}")
                    logger.info(f"Post ID: {json_response.get('postId')}")
                    if json_response.get('thumbnail'):
                        logger.info(f"Thumbnail: {json_response.get('thumbnail')}")

                    logger.info("Waiting 2 seconds to allow WordPress to process metadata for social sharing...")
                    time.sleep(2)

                    return {"status": "success", "message": "News published successfully!", "permalink": json_response.get('permalink')}
                else:
                    logger.error(f"Error publishing news: {json_response.get('msg', 'Unknown error')}")
                    return {"status": "error", "detail": json_response.get('msg', 'Unknown error from WordPress.')}
            except json.JSONDecodeError as e:
                logger.error(f"Error: Could not decode JSON response. Exception: {e}")
                return {"status": "error", "detail": f"Invalid JSON response from WordPress: {e}"}
        else:
            logger.error(f"Error: HTTP Status Code {response.status_code}")
            try:
                error_json = response.json()
                logger.error(f"Error response JSON: {json.dumps(error_json, indent=2)}")
                return {"status": "error", "detail": f"WordPress API error: {error_json.get('message', 'Unknown error')}"}
            except json.JSONDecodeError:
                logger.error(f"Error response text (not JSON): {response.text[:1000]}")
                return {"status": "error", "detail": f"WordPress API error (non-JSON response): {response.text[:200]}"}

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection Error: Could not connect to WordPress site. Error: {e}")
        return {"status": "error", "detail": f"Connection to WordPress failed: {e}"}
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout Error: Request to WordPress site timed out. Error: {e}")
        return {"status": "error", "detail": f"Request to WordPress timed out: {e}"}
    except requests.exceptions.RequestException as e:
        logger.error(f"An unexpected error occurred during the request: {e}")
        return {"status": "error", "detail": f"An unexpected request error occurred: {e}"}
    except Exception as e:
        logger.critical(f"A critical unexpected error occurred: {e}")
        traceback.print_exc()
        return {"status": "error", "detail": f"A critical internal error occurred: {e}"}

if __name__ == "__main__":
    load_dotenv()

    if len(sys.argv) < 2:
        logger.error("Usage: python publish.py \"{'news': '...', 'featured_image_id': ..., 'categories': [...], 'tags': []}\"")
        sys.exit(1)

    json_data_arg = sys.argv[1]
    try:
        news_data = json.loads(json_data_arg)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON argument: {e}")
        sys.exit(1)

    required_keys = ["news"]
    for key in required_keys:
        if key not in news_data:
            logger.error(f"Missing required key in JSON argument: '{key}'")
            sys.exit(1)

    if "categories" not in news_data or not isinstance(news_data["categories"], list):
        news_data["categories"] = []
        logger.warning("Categories not provided or invalid, defaulting to empty list.")
    if "tags" not in news_data or not isinstance(news_data["tags"], list):
        news_data["tags"] = []
        logger.warning("Tags not provided or invalid, defaulting to empty list.")

    result = publish_news_to_wordpress(news_data)
    if result.get("status") == "success":
        logger.info(f"Script execution successful: {result.get('message')}")
        sys.exit(0)
    else:
        logger.error(f"Script execution failed: {result.get('detail')}")
        sys.exit(1)
