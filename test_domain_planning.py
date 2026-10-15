
from core.planner import create_plan

goals = [
    "Find courses that teach web development.",
    "Compare colleges offering artificial intelligence degrees.",
    "Find scholarships for my university studies.",
    "Find a hospital with a cardiology department.",
    "Compare hospitals that provide cardiac care.",
    "Help me find an available medical appointment.",
]

for goal in goals:
    result = create_plan(goal)

    print("\nGoal:", goal)
    print("Domain:", result.get("domain"))
    print("Intent:", result.get("intent"))
    print("Status:", result["status"])
    print("Errors:", result["errors"])
    print("Questions:", result["clarification_questions"])
