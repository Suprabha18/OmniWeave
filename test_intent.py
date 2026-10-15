
from core.domain_resolver import resolve_domain
from core.intent_resolver import resolve_intent


test_goals = [
    ("Find courses that teach web development.", "find_course"),
    ("Compare colleges offering artificial intelligence degrees.",
     "compare_institutions"),
    ("Find scholarships for my university studies.",
     "find_scholarship"),
    ("Find a hospital with a cardiology department.",
     "find_provider"),
    ("Compare hospitals that provide cardiac care.",
     "compare_providers"),
    ("Help me find an available medical appointment.",
     "find_appointment"),
    ("Prepare questions to ask my doctor at my appointment.",
     "prepare_for_appointment"),
]

failed = 0

for goal, expected_intent in test_goals:
    domain_result = resolve_domain(goal)
    domain = domain_result["domain"]

    result = resolve_intent(goal, domain)
    actual_intent = result["intent"]
    passed = actual_intent == expected_intent

    if not passed:
        failed += 1

    print("\nGoal:", goal)
    print("Expected:", expected_intent)
    print("Actual:", actual_intent)
    print("Method:", result.get("method"))
    print("Result:", "PASS" if passed else "FAIL")

print(f"\nTests passed: {len(test_goals) - failed}/{len(test_goals)}")

if failed:
    raise SystemExit(1)
