from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from models import NewsRequest, PublishRequest
from api_clients import process_article
import aiohttp
import logging
import traceback
import subprocess

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def home():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@router.post("/rewrite")
async def rewrite(request: NewsRequest):
    try:
        news_content = request.news
        selected_api = request.api

        if not news_content.strip():
            raise HTTPException(status_code=400, detail="News content cannot be empty")

        async with aiohttp.ClientSession() as session:
            result = await process_article(session, news_content, selected_api)

        if result == "RATE_LIMIT_REACHED":
            api_mapping = {
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
            api_name = api_mapping.get(selected_api, selected_api)
            raise HTTPException(
                status_code=429, 
                detail=f"Rate limit reached for {api_name}. Please try a different API option from the dropdown."
            )
        elif result:
            return {"rewritten_news": result}
        else:
            api_mapping = {
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
            api_name = api_mapping.get(selected_api, selected_api)
            raise HTTPException(
                status_code=500, 
                detail=f"Unable to process your request with {api_name}. Please try another API option."
            )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected error in rewrite endpoint: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

@router.post("/publish")
async def publish(request: PublishRequest):
    try:
        news_content = request.news

        if not news_content.strip():
            raise HTTPException(status_code=400, detail="News content cannot be empty")

        # Split news content into title and body
        lines = news_content.strip().split('\n')
        if len(lines) < 2:
            raise HTTPException(status_code=400, detail="News content must have at least a title and body")
        
        title = lines[0].strip()
        body = '\n'.join(lines[1:]).strip()

        if not title or not body:
            raise HTTPException(status_code=400, detail="Both title and body are required")

        # Execute the publish.py script with title and body as separate arguments
        result = subprocess.run(['python', 'publish.py', title, body], capture_output=True, text=True)

        if result.returncode == 0:
            return {"message": "News published successfully"}
        else:
            error_msg = result.stderr or result.stdout or "Unknown error occurred"
            raise HTTPException(status_code=500, detail=f"Publishing failed: {error_msg}")

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected error in publish endpoint: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
