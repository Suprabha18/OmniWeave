
from typing import Any
from functools import lru_cache

from sentence_transformers import SentenceTransformer, util


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# These describe the intent of each domain.
# They are descriptions, not lists of words to match.


DOMAIN_DESCRIPTIONS = {
    "education": (
        "Education, studying, learning, teaching, academic subjects, "
        "programming tutorials, learning Python or Java, coding lessons, "
        "web development courses, online courses, training programs, "
        "universities, colleges, school admissions, degree programs, "
        "artificial intelligence degrees, scholarships, grants, "
        "student financial aid, academic eligibility, exams, and "
        "educational applications. Examples include finding a scholarship, "
        "learning a programming language, comparing colleges, and "
        "finding courses that teach web development."
    ),
    "healthcare": (
        "Healthcare, medical care, hospitals, clinics, doctors, physicians, "
        "medical specialists, cardiologists, cardiology departments, "
        "heart care, cardiac treatment, medical consultations, patient "
        "appointments, appointment availability, finding a hospital, "
        "comparing healthcare providers, and accessing medical services. "
        "Examples include finding a hospital with a cardiology department, "
        "comparing hospitals that provide cardiac care, and finding an "
        "available medical appointment."
    ),
}



# These are initial thresholds and should be calibrated using tests
# representative of the actual OmniWeave users.
MIN_CONFIDENCE = 0.25
MIN_MARGIN = 0.05


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    """Load the model once and reuse it."""
    return SentenceTransformer(MODEL_NAME)


def resolve_domain(goal: str) -> dict[str, Any]:
    """
    Resolve a user's goal using semantic similarity,
    rather than matching predefined keywords.
    """
    if not isinstance(goal, str) or not goal.strip():
        return {
            "domain": None,
            "status": "needs_clarification",
            "message": "Please describe what you want to accomplish.",
            "confidence": None,
            "scores": {},
        }

    try:
        model = _load_model()

        domain_names = list(DOMAIN_DESCRIPTIONS.keys())
        descriptions = [
            DOMAIN_DESCRIPTIONS[name] for name in domain_names
        ]

        goal_embedding = model.encode(
            goal.strip(),
            convert_to_tensor=True,
            normalize_embeddings=True,
        )

        description_embeddings = model.encode(
            descriptions,
            convert_to_tensor=True,
            normalize_embeddings=True,
        )

        similarities = util.cos_sim(
            goal_embedding,
            description_embeddings,
        )[0]

        scores = {
            domain_names[i]: round(float(similarities[i]), 4)
            for i in range(len(domain_names))
        }

        ranked = sorted(
            scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        best_domain, best_score = ranked[0]
        second_score = ranked[1][1]

        # If neither domain is a reasonable match, ask for clarification.
        if best_score < MIN_CONFIDENCE:
            return {
                "domain": None,
                "status": "needs_clarification",
                "message": (
                    "I could not confidently identify this as an "
                    "Education or Healthcare goal. Please clarify."
                ),
                "confidence": best_score,
                "scores": scores,
            }

        # Similar scores can indicate a mixed or ambiguous goal.
        if best_score - second_score < MIN_MARGIN:
            return {
                "domain": "mixed",
                "status": "needs_clarification",
                "message": (
                    "This request may involve both domains or be "
                    "ambiguous. Please clarify your intended goal."
                ),
                "confidence": best_score,
                "scores": scores,
            }

        return {
            "domain": best_domain,
            "status": "resolved",
            "message": f"The goal most closely matches {best_domain}.",
            "confidence": best_score,
            "scores": scores,
        }

    except Exception as exc:
        # Do not silently fall back to keyword matching.
        return {
            "domain": None,
            "status": "error",
            "message": (
                "Domain detection failed. Check model installation, "
                "model availability, and network access."
            ),
            "error": str(exc),
            "confidence": None,
            "scores": {},
        }
