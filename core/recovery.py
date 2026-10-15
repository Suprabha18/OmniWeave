
class RecoveryManager:
    def __init__(self, max_retries=2):
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self.max_retries = max_retries

    def should_retry(self, result, attempt):
        """
        attempt is the current attempt number, starting at 1.

        max_retries=2 permits:
        attempt 1: initial attempt
        attempt 2: first retry
        attempt 3: second retry
        """
        if result.get("success", False):
            return False

        if result.get("retryable", True) is False:
            return False

        return attempt <= self.max_retries

    def next_action(self, result, attempt):
        if result.get("success", False):
            return "complete"

        if self.should_retry(result, attempt):
            return "retry"

        return "fail"

