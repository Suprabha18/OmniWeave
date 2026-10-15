
import re

from sentence_transformers import util
from core.domain_resolver import _load_model


INTENT_DESCRIPTIONS = {
    "education": {
        "find_course": (
            "Find, search for, or discover courses, classes, "
            "training programs, or learning programs."
        ),
        "explain_concept": (
            "Explain a subject, teach a concept, or help someone "
            "understand a topic step by step."
        ),
        "compare_institutions": (
            "Compare colleges, universities, institutions, "
            "or degree programs."
        ),
        "check_eligibility": (
            "Check admission requirements, eligibility, qualifications, "
            "or whether someone qualifies for a program."
        ),
        "find_scholarship": (
            "Find scholarships, grants, or education funding."
        ),
        "prepare_application": (
            "Prepare, fill out, or submit an educational application."
        ),
    },
    "healthcare": {
        "find_provider": (
            "Find a hospital, clinic, doctor, specialist, or healthcare provider."
        ),
        "compare_providers": (
            "Compare hospitals, clinics, doctors, or healthcare providers."
        ),
        "find_appointment": (
            "Find available medical appointments or book a healthcare visit."
        ),
        "prepare_for_appointment": (
            "Prepare questions, documents, or information for a medical appointment."
        ),
    },
}


# Explicit phrases take priority over the semantic model.
INTENT_RULES = {
    "education": [
        (
            "find_course",
            [
                r"\bfind\b.*\bcourses?\b",
                r"\bsearch\b.*\bcourses?\b",
                r"\bcourses?\b.*\b(for|to learn|that teach|teaching)\b",
                r"\btraining programs?\b",
                r"\blearning programs?\b",
                r"\brecommend\b.*\bcourses?\b",
            ],
        ),
        (
            "compare_institutions",
            [
                r"\bcompare\b.*\b(colleges?|universities|institutions|degree programs?)\b",
                r"\b(colleges?|universities)\b.*\bcomparison\b",
            ],
        ),
        (
            "find_scholarship",
            [
                r"\b(find|search for|look for|discover)\b.*\bscholarships?\b",
                r"\bfinancial aid\b",
                r"\beducation funding\b",
            ],
        ),
        (
            "check_eligibility",
            [
                r"\b(check|verify|assess)\b.*\b(eligibility|eligible|qualifications?)\b",
                r"\bdo i qualify\b",
                r"\badmission requirements\b",
            ],
        ),
        (
            "prepare_application",
            [
                r"\b(prepare|fill out|submit|complete)\b.*\b(application|admission form)\b",
                r"\bapply to\b.*\b(college|university|program|course)\b",
            ],
        ),
        (
            "explain_concept",
            [
                r"\b(explain|teach me|help me understand)\b",
                r"\blearn\b.*\b(from scratch|the basics|step by step)\b",
            ],
        ),
    ],
    "healthcare": [
        (
            "prepare_for_appointment",
            [
                r"\bprepare\b.*\b(for|my)\b.*\bappointment\b",
                r"\bquestions to ask\b.*\b(doctor|specialist)\b",
            ],
        ),
        (
            "find_appointment",
            [
                r"\b(available|availability)\b.*\bappointments?\b",
                r"\b(find|book|schedule|reschedule)\b.*\bappointments?\b",
                r"\bbook\b.*\b(doctor|clinic|hospital|medical visit)\b",
                r"\bmedical appointment\b",
            ],
        ),
        (
            "compare_providers",
            [
                r"\bcompare\b.*\b(hospitals?|clinics?|doctors?|providers?|healthcare facilities)\b",
                r"\bcomparison\b.*\b(hospitals?|clinics?|doctors?)\b",
            ],
        ),
        (
            "find_provider",
            [
                r"\b(find|search for|locate|recommend)\b.*\b(hospitals?|clinics?|doctors?|specialists?|healthcare providers?)\b",
                r"\bhospital\b.*\b(with|that has|offering|providing)\b",
                r"\bclinics?\b.*\b(with|that has|offering|providing)\b",
            ],
        ),
    ],
}


MIN_INTENT_SCORE = 0.30
MIN_INTENT_MARGIN = 0.02


def _match_explicit_intent(goal, domain):
    """Return an intent when the goal clearly matches an action phrase."""
    rules = INTENT_RULES.get(domain, [])

    for intent, patterns in rules:
        if any(re.search(pattern, goal, re.IGNORECASE) for pattern in patterns):
            return intent

    return None


def resolve_intent(goal, domain):
    """Resolve intent using explicit phrases first, then semantic similarity."""
    if domain not in INTENT_DESCRIPTIONS:
        return {
            "intent": None,
            "status": "needs_clarification",
            "scores": {},
        }

    # Step 1: Use clear action phrases where possible.
    explicit_intent = _match_explicit_intent(goal, domain)

    if explicit_intent:
        return {
            "intent": explicit_intent,
            "status": "resolved",
            "method": "explicit_phrase",
            "scores": {},
        }

    # Step 2: Fall back to sentence embeddings.
    model = _load_model()
    descriptions = INTENT_DESCRIPTIONS[domain]
    intent_names = list(descriptions.keys())

    goal_embedding = model.encode(
        [goal],
        convert_to_tensor=True,
        normalize_embeddings=True,
    )

    intent_embeddings = model.encode(
        [descriptions[name] for name in intent_names],
        convert_to_tensor=True,
        normalize_embeddings=True,
    )

    similarities = util.cos_sim(
        goal_embedding,
        intent_embeddings,
    )[0]

    scores = {
        name: round(float(similarity), 4)
        for name, similarity in zip(intent_names, similarities)
    }

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_intent, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else -1.0

    if (
        best_score < MIN_INTENT_SCORE
        or best_score - second_score < MIN_INTENT_MARGIN
    ):
        return {
            "intent": None,
            "status": "needs_clarification",
            "method": "semantic_similarity",
            "scores": scores,
        }

    return {
        "intent": best_intent,
        "status": "resolved",
        "method": "semantic_similarity",
        "scores": scores,
    }
