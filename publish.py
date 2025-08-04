import requests
import sys
import json
import os
import time

def publish_news_to_wordpress(news_content):
    """
    Publishes news content to a WordPress site using the news-rewrite.onrender API.

    Args:
        news_content (str): The content of the news article to be published.
    """

    # --- Configuration ---
    # Replace with your actual WordPress site URL where the plugin is installed
    WORDPRESS_SITE_URL = os.environ.get("WORDPRESS_SITE_URL", "https://therimonline.com")

    # IMPORTANT: Replace with your actual API Token from your WordPress news-rewrite.onrender plugin settings.
    # You can find this token in your WordPress admin panel under the 'news-rewrite.onrender' menu.
    # It's highly recommended to store this in an environment variable for security.
    API_TOKEN = os.environ.get("WORDPRESS_API_TOKEN", "7e523bdfa04efa076fb8e94d137c1a7657fbfb1f4ca7b2afe66c45b579761870")

    # API Endpoint for creating posts
    API_ENDPOINT = f"{WORDPRESS_SITE_URL}/wp-json/news-rewrite-onrender/v1/createpost"

    # --- Prepare the data for the API request ---
    # Split the news content into title and body
    lines = news_content.split('\n', 1)
    title = lines[0].strip() if lines else "Untitled News Article"
    body = lines[1].strip() if len(lines) > 1 else ""

    # You can customize these parameters based on your needs
    payload = {
        "title": title,
        "content": body,
        "wpToken": API_TOKEN,
        "post_status": "publish",  # 'publish', 'draft', 'pending'
        "catId": "1",  # Default category ID (e.g., 'Uncategorized'). Change as needed.
        # You can get category IDs from your WordPress admin or via the /getCategories API.
        "tags": "news, rewrite, AI",  # Comma-separated tags
        # "featuredImage": "https://example.com/path/to/your/image.jpg",  # Optional: URL or base64 of a featured image
        # "image_url": "https://example.com/path/to/another/image.jpg",  # Optional: If you have a primary image URL
        # "postTime": "2023-10-27 10:00:00",  # Optional: Specific post date/time
        # "serp_title": "SEO Title for " + title,  # Optional: For RankMath/Yoast SEO title
        # "serp_des": "This is a meta description for the news article.",  # Optional: For RankMath/Yoast meta description
        # "serp_score": "80"  # Optional: For RankMath/Yoast SEO score
    }

    # --- Send the POST request ---
    print(f"Attempting to publish news to: {API_ENDPOINT}")
    print(f"Title: {title}")
    print(f"Body length: {len(body)} characters")
    print(f"Payload keys: {list(payload.keys())}")
    # print(f"Content (first 200 chars): {body[:200]}...")  # For debugging, don't print full content in production logs

    try:
        # Create a session to maintain cookies and appear more like a browser
        session = requests.Session()
        
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
        
        # First, make a GET request to the main site to establish a session
        try:
            session.get(WORDPRESS_SITE_URL, headers={
                'User-Agent': headers['User-Agent'],
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }, timeout=10)
            time.sleep(2)  # Wait a bit between requests
        except:
            pass  # Continue even if this fails
        
        print(f"Sending JSON payload with headers: {headers}")
        
        # Add a longer delay to avoid being flagged as bot
        time.sleep(3)
        
        response = session.post(API_ENDPOINT, json=payload, headers=headers, timeout=30)

        # --- Handle the response ---
        print(f"Response status code: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                json_response = response.json()
                if json_response.get("status") == "success":
                    print("News published successfully!")
                    print(f"Permalink: {json_response.get('permalink')}")
                    print(f"Post ID: {json_response.get('postId')}")
                    if json_response.get('thumbnail'):
                        print(f"Thumbnail: {json_response.get('thumbnail')}")
                    sys.exit(0)  # Indicate success
                else:
                    print(f"Error publishing news: {json_response.get('msg', 'Unknown error')}")
                    print(f"Full response: {json.dumps(json_response, indent=2)}")
                    sys.exit(1)  # Indicate failure
            except json.JSONDecodeError:
                print(f"Error: Could not decode JSON response. Raw response: {response.text[:1000]}")
                sys.exit(1)
        else:
            print(f"Error: HTTP Status Code {response.status_code}")
            try:
                error_json = response.json()
                print(f"Error response JSON: {json.dumps(error_json, indent=2)}")
                
                # Check for specific bot protection error
                if "Imunify360" in response.text or "bot-protection" in response.text:
                    print("Bot protection detected. This may be due to server security settings.")
                    print("Consider contacting the website administrator to whitelist your IP or adjust security settings.")
                
            except json.JSONDecodeError:
                print(f"Error response text: {response.text[:1000]}")
            sys.exit(1)  # Indicate failure

    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error: Could not connect to WordPress site. Please check the URL and your internet connection. Error: {e}")
        sys.exit(1)
    except requests.exceptions.Timeout as e:
        print(f"Timeout Error: Request to WordPress site timed out. Error: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"An unexpected error occurred during the request: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python publish.py \"title\" \"body content\"")
        print("Or:    python publish.py \"Your news content here\" (single argument)")
        sys.exit(1)

    if len(sys.argv) == 3:
        # Two arguments: title and body
        title = sys.argv[1]
        body = sys.argv[2]
        news_content_to_publish = f"{title}\n{body}"
        print("Using title and body from command line arguments.")
    else:
        # Single argument: treat as full content
        input_arg = sys.argv[1]
        
        if os.path.exists(input_arg):
            # If the argument is a file path, read content from the file
            try:
                with open(input_arg, 'r', encoding='utf-8') as f:
                    news_content_to_publish = f.read()
                print(f"Reading news content from file: {input_arg}")
            except Exception as e:
                print(f"Error reading file {input_arg}: {e}")
                sys.exit(1)
        else:
            # Otherwise, treat the argument as direct news content
            news_content_to_publish = input_arg
            print("Using direct news content from command line.")

    if not news_content_to_publish.strip():
        print("Error: News content is empty.")
        sys.exit(1)

    publish_news_to_wordpress(news_content_to_publish)
