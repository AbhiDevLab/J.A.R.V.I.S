import os
from typing import Optional
import sys
import traceback

# Try to import the Google Generative AI client, but do not crash at import time
try:
    import google.generativeai as genai  # type: ignore
except Exception:
    # keep genai as None if import fails; avoid printing environment info or stack that could expose sensitive data
    genai = None  # type: ignore

def is_available() -> bool:
    """Return True if google-generativeai is importable in this environment."""
    return genai is not None

class GeminiClient:
    def __init__(self, api_key: Optional[str] = None):
        # Start in a disabled state; initialize() will enable if possible
        self.api_key: Optional[str] = None
        self.model = None
        self.available = False

        # If an api_key is provided at creation, try to initialize now
        if api_key:
            try:
                self.initialize(api_key)
            except Exception:
                # keep client in disabled state if initialization fails
                self.available = False

    def initialize(self, api_key: str):
        """Configure the client with an API key. Safe to call multiple times."""
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            # leave client unavailable if no key
            self.available = False
            self.model = None
            return

        if genai is None:
            # module not available
            self.available = False
            self.model = None
            return

        # configure and create model
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
        self.available = True

    def ask_gemini(self, prompt: str) -> str:
        """Send prompt to Gemini and return response (safe even when unavailable)."""
        if not self.available or self.model is None:
            return "Gemini is not available in this environment. Install google-generativeai and configure GEMINI_API_KEY."
        try:
            response = self.model.generate_content(prompt)
            return getattr(response, "text", str(response))
        except Exception as e:
            return f"Gemini request failed: {str(e)}"

# Create a singleton instance at import so other modules that imported this object
# keep a valid reference even before initialization occurs.
gemini_client = GeminiClient()

def get_client() -> GeminiClient:
    """Return the singleton Gemini client (may be disabled until initialize is called)."""
    return gemini_client

def ask(prompt: str) -> str:
    """Convenience wrapper that uses the singleton to ask Gemini safely."""
    return gemini_client.ask_gemini(prompt)

def init_gemini(api_key: str):
    """Initialize the global Gemini client (configures the existing singleton)."""
    gemini_client.initialize(api_key)
    return gemini_client