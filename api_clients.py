
import aiohttp
import asyncio
import json
import logging
import traceback
import os
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

github_token = os.getenv("GITHUB_TOKEN")
if not github_token:
    logger.error("GITHUB_TOKEN environment variable must be set.")
    raise ValueError("GITHUB_TOKEN environment variable must be set.")

try:
    azure_client = ChatCompletionsClient(
        endpoint="https://models.github.ai/inference",
        credential=AzureKeyCredential(github_token),
    )
    logger.info("Azure ChatCompletionsClient initialized successfully.")
except Exception as e:
    logger.critical(f"Failed to initialize Azure ChatCompletionsClient: {e}")
    raise

async def call_api(session, model, prompt):
    api_url = "https://openrouter.ai/api/v1/chat/completions"
    api_key = os.getenv("API_KEY")

    if not api_key:
        logger.error("API_KEY environment variable is not set for OpenRouter API.")
        return None

    try:
        logger.info(f"Calling OpenRouter API with model {model}")
        async with session.post(
            url=api_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a professional Nepali news editor. Generate a short and relevant headline, then rewrite the article in totally new style and structure by not losing originality using standard journalistic Nepali. Result must be in the same paragraph count. No need to mention Explanation of changes, Key Changes & style notes just focus on best rewritting result."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
            })
        ) as response:
            response.raise_for_status()
            data = await response.json()
            logger.info(f"Successfully received response from OpenRouter model {model}")
            return data["choices"][0]["message"]["content"].strip()
    except aiohttp.ClientResponseError as e:
        logger.error(f"OpenRouter ClientResponseError for model {model} (Status: {e.status}): {str(e)}")
        if e.status == 429:
            logger.warning(f"Rate limit hit for OpenRouter model {model}")
            return "RATE_LIMIT_REACHED"
        else:
            traceback.print_exc()
            return None
    except Exception as e:
        logger.error(f"Generic error calling OpenRouter API with model {model}: {str(e)}")
        traceback.print_exc()
        return None

async def call_azure_api(model, prompt):
    def sync_azure_call():
        try:
            logger.info(f"Starting Azure API call to model: {model}")
            response = azure_client.complete(
                messages=[
                    SystemMessage("You are a professional Nepali news editor. Generate a short and relevant headline, then rewrite the article in totally new style and structure by not losing originality using standard journalistic Nepali. Result must be in the same paragraph count."),
                    UserMessage(prompt),
                ],
                temperature=0.7,
                top_p=1,
                model=model
            )
            logger.info(f"Successfully got response from Azure model: {model}")
            return response.choices[0].message.content.strip()
        except HttpResponseError as e:
            logger.error(f"Azure HttpResponseError - Status: {e.status_code}")
            if e.status_code == 429:
                logger.warning(f"Azure Rate limit hit for model {model}")
                return "RATE_LIMIT_REACHED"
            else:
                logger.error(f"Error processing request with model {model}: HTTP {e.status_code} - {str(e)}")
                traceback.print_exc()
                return None
        except Exception as e:
            logger.error(f"Exception during sync Azure call: {type(e).__name__}: {str(e)}")
            error_str = str(e).lower()
            if ("ratelimitreached" in error_str or
                "rate limit" in error_str or
                "429" in error_str or
                "quota exceeded" in error_str or
                "too many requests" in error_str):
                logger.warning(f"Azure Rate limit detected in exception for model {model}")
                return "RATE_LIMIT_REACHED"
            else:
                logger.error(f"Error processing request with model {model}: {str(e)}")
                traceback.print_exc()
                return None

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, sync_azure_call)
        logger.info(f"Azure API call completed for model {model}")
        return result
    except Exception as e:
        logger.error(f"Error in async wrapper for Azure model {model}: {str(e)}")
        traceback.print_exc()
        return None

def format_output(raw_output):
    paragraphs = raw_output.split('\n\n')
    formatted_news = '\n\n'.join(paragraphs)
    return formatted_news

async def process_article(session, article, selected_api):
    news_text = article.replace("\n\n", "\n\n[PARAGRAPH_BREAK]\n\n")
    prompt = f"""Original news:
{news_text}

Rewritten news:
"""

    api_mapping = {
        "azure_gpt41": ("azure", "openai/gpt-4.1"),
        "azure_gpt41_nano": ("azure", "openai/gpt-4.1-nano"),
        "openrouter_gpt41_nano": ("openrouter", "openai/gpt-4.1-nano"),
        "openrouter_deepseek": ("openrouter", "deepseek/deepseek-r1-0528:free"),
        "azure_gpt41_mini": ("azure", "openai/gpt-4.1-mini"),
        "azure_grok": ("azure", "xai/grok-3-mini"),
        "openrouter_gpt35": ("openrouter", "openai/gpt-3.5-turbo"),
        "openrouter_gemma": ("openrouter", "google/gemma-3-27b-it:free"),
        "openrouter_claude3": ("openrouter", "anthropic/claude-3-haiku")
    }

    if selected_api not in api_mapping:
        logger.error(f"Invalid API selected: {selected_api}")
        raise ValueError("Invalid API selected")

    api_type, model = api_mapping[selected_api]

    try:
        logger.info(f"Trying {api_type} model: {model}")
        if api_type == "azure":
            raw_output = await call_azure_api(model, prompt)
        else:
            raw_output = await call_api(session, model, prompt)

        if raw_output == "RATE_LIMIT_REACHED":
            logger.warning(f"Rate limit reached for {api_type} model {model}")
            return "RATE_LIMIT_REACHED"
        elif raw_output:
            logger.info(f"Successfully got response from {api_type} model: {model}")
            return format_output(raw_output)
        else:
            logger.warning(f"No response from {api_type} model {model}")
            return None
    except Exception as e:
        logger.error(f"Error with {api_type} model {model}: {str(e)}")
        traceback.print_exc()
        return None
