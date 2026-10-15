
from core.domain_resolver import resolve_domain

goals = [
    "I want to continue learning after my undergraduate degree.",
    "Help me find a place where I can get my heart checked.",
    "I need financial support to continue my studies.",
    "I want to compare medical specialists and university courses.",
    "Find the best laptop for programming.",
]

for goal in goals:
    result = resolve_domain(goal)

    print(f"\nGoal: {goal}")
    print(f"Domain: {result['domain']}")
    print(f"Status: {result['status']}")
    print(f"Scores: {result['scores']}")
