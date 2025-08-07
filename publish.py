import requests
import sys
import os
import json
import logging
import time
import traceback
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

WORDPRESS_CATEGORY_MAP = {
    "मुख्य समाचार": 12,
    "समाचार": 9,
    "देश": 11,
    "राजनिति": 10,
    "अर्थ": 5,
    "खेलकुद": 1,
    "फिचर": 2,
    "मनोरञ्जन": 7,
    "विचार": 16,
    "विदेश": 20,
    "स्वास्थ्य/जीवनशैली": 15,
    "Banner": 59,
}

def publish_news_to_wordpress(news_data):
    WORDPRESS_SITE_URL = os.environ.get("WORDPRESS_SITE_URL")
    API_TOKEN = os.environ.get("WORDPRESS_API_TOKEN")

    if not WORDPRESS_SITE_URL:
        logger.error("Error: WORDPRESS_SITE_URL environment variable is not set.")
        sys.exit(1)
    if not API_TOKEN:
        logger.error("Error: WORDPRESS_API_TOKEN environment variable is not set.")
        sys.exit(1)

    POST_API_ENDPOINT = f"{WORDPRESS_SITE_URL}/wp-json/news-rewrite-onrender/v1/createpost"

    news_content = news_data.get("news", "")
    featured_image_id = news_data.get("featured_image_id")
    selected_categories = news_data.get("categories", [])
    selected_tags = news_data.get("tags", [])

    lines = news_content.split('\n', 1)
    title = lines[0].strip() if lines else "Untitled News Article"
    body = lines[1].strip() if len(lines) > 1 else ""

    if not title or not body:
        logger.error("News content must contain both a title and a body.")
        sys.exit(1)

    category_ids = []
    for cat_name in selected_categories:
        cat_id = WORDPRESS_CATEGORY_MAP.get(cat_name)
        if cat_id:
            category_ids.append(cat_id)
            logger.info(f"Mapped category '{cat_name}' to ID: {cat_id}")
        else:
            logger.warning(f"Category '{cat_name}' not found in WORDPRESS_CATEGORY_MAP. Skipping.")

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
        if keyword in content_lower and tag not in selected_tags:
            auto_tags.append(tag)

    all_tags = list(set(selected_tags + auto_tags))
    logger.info(f"Final tags to be used: {all_tags}")

    payload = {
        "title": title,
        "content": body,
        "wpToken": API_TOKEN,
        "post_status": "publish",
        "catIds": category_ids,
        "tagNames": all_tags,
        "featured_image_id": featured_image_id
    }

    logger.info(f"Attempting to publish news to: {POST_API_ENDPOINT}")
    logger.info(f"Title: {title}")
    logger.info(f"Body length: {len(body)} characters")
    logger.info(f"Categories (IDs): {category_ids}")
    logger.info(f"Tags (Names): {all_tags}")
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

        try:
            logger.info(f"Making initial GET request to {WORDPRESS_SITE_URL} to establish session.")
            requests.get(WORDPRESS_SITE_URL, headers={
                'User-Agent': headers['User-Agent'],
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }, timeout=10)
            time.sleep(2)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Initial GET request failed: {e}")
            pass

        logger.info(f"Sending POST request to {POST_API_ENDPOINT} with JSON payload.")
        time.sleep(3)

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
                    sys.exit(0)
                else:
                    logger.error(f"Error publishing news: {json_response.get('msg', 'Unknown error')}")
                    sys.exit(1)
            except json.JSONDecodeError as e:
                logger.error(f"Error: Could not decode JSON response. Exception: {e}")
                sys.exit(1)
        else:
            logger.error(f"Error: HTTP Status Code {response.status_code}")
            try:
                error_json = response.json()
                logger.error(f"Error response JSON: {json.dumps(error_json, indent=2)}")
            except json.JSONDecodeError:
                logger.error(f"Error response text (not JSON): {response.text[:1000]}")
            sys.exit(1)

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection Error: Could not connect to WordPress site. Error: {e}")
        sys.exit(1)
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout Error: Request to WordPress site timed out. Error: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        logger.error(f"An unexpected error occurred during the request: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"A critical unexpected error occurred: {e}")
        traceback.print_exc()
        sys.exit(1)

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

    publish_news_to_wordpress(news_data)
