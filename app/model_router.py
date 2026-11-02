import logging
import time

from app.ai_analyzer import analyze_incident as analyze_with_gemini
from app.groq_analyzer import analyze_incident as analyze_with_groq

logger = logging.getLogger(__name__)

MAX_PRIMARY_RETRIES = 1
RETRY_DELAY = 3


def analyze_incident(incident):
    """
    Try Gemini first, then automatically fall back to Groq.
    Both providers must return the same validated analysis structure.
    """

    for attempt in range(MAX_PRIMARY_RETRIES + 1):
        try:
            result = analyze_with_gemini(incident)
            result["model_provider"] = "gemini"
            return result

        except Exception as exc:
            logger.warning(
                "Gemini analysis failed (attempt %s/%s): %s",
                attempt + 1,
                MAX_PRIMARY_RETRIES + 1,
                exc,
            )

            if attempt < MAX_PRIMARY_RETRIES:
                time.sleep(RETRY_DELAY)

    logger.warning("Switching to Groq fallback provider.")

    result = analyze_with_groq(incident)
    result["model_provider"] = "groq"

    return result
