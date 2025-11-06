import os
import httpx
from logging_config import setup_logger

logger = setup_logger('chat.llm')

class LLMClient:
    """Client for LLM API (OpenRouter)."""
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.model_name = os.getenv("LLM_MODEL", "anthropic/claude-3.5-sonnet")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.mock_mode = not self.api_key or self.api_key == "MOCK_KEY_FOR_TESTING"
        
        if self.mock_mode:
            logger.warning("LLM Client running in MOCK mode (no API key configured)")
        else:
            logger.info(f"LLM Client initialized with model: {self.model_name}")
    
    def is_configured(self) -> bool:
        """Check if LLM client is properly configured."""
        return not self.mock_mode
    
    def generate(self, prompt: str) -> str:
        """Generate answer using LLM."""
        if self.mock_mode:
            logger.info("Using MOCK LLM response")
            return (
                "Based on the MARP regulations, students must achieve a minimum "
                "weighted average of 40% to be eligible for awards. This is a "
                "mock response for testing purposes."
            )
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1
                    }
                )
                response.raise_for_status()
                data = response.json()
                answer = data['choices'][0]['message']['content'].strip()
                
                logger.info(f"LLM generated answer (length: {len(answer)})")
                return answer
                
        except httpx.HTTPError as e:
            logger.error(f"LLM API request failed: {e}")
            return "Error: Failed to communicate with the LLM API."
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return "Error: Failed to generate answer."