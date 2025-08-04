import requests
import sys
import json
import os

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
    # You'll likely want to extract the title from the news_content or pass it separately.
    # For simplicity, let's assume the first line of news_content is the title.
    lines = news_content.split('\n', 1)
    title = lines[0].strip() if lines else "Untitled News Article"
    content = news_content  # The full content

    # You can customize these parameters based on your needs
    payload = {
        "title": title,
        "content": content,
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
    # print(f"Content (first 200 chars): {content[:200]}...")  # For debugging, don't print full content in production logs

    try:
        response = requests.post(API_ENDPOINT, json=payload)  # Use 'json' for JSON body

        # --- Handle the response ---
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
                print(f"Error: Could not decode JSON response. Raw response: {response.text}")
                sys.exit(1)
        else:
            print(f"Error: HTTP Status Code {response.status_code}")
            print(f"Response text: {response.text}")
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
    if len(sys.argv) < 2:
        print("Usage: python publish.py \"Your news content here\"")
        print("Or:    python publish.py <path_to_news_file.txt>")
        sys.exit(1)

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
