
class RecoveryManager:
    def __init__(self, max_retries=2):
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        self.max_retries = max_retries

    def classify_exception(self, exc):
        """Classify an exception and suggest a practical recovery."""
        error_type = type(exc).__name__
        message = str(exc)
        text = message.lower()

        if isinstance(exc, FileNotFoundError):
            retryable = False
            suggestion = (
                "Check that the file exists and that its path is correct."
            )
        elif isinstance(exc, PermissionError):
            retryable = False
            suggestion = (
                "Check file permissions and whether another process "
                "is locking the resource."
            )
        elif isinstance(exc, (TimeoutError, ConnectionError)):
            retryable = True
            suggestion = (
                "Check service availability and network connectivity. "
                "Retry after the service is reachable."
            )
        elif isinstance(exc, (ValueError, TypeError)):
            retryable = False
            suggestion = (
                "Check the input values and tool argument types."
            )
        elif "timeout" in text or "timed out" in text:
            retryable = True
            suggestion = (
                "The operation timed out. Check service availability "
                "and retry."
            )
        elif "connection" in text or "temporarily unavailable" in text:
            retryable = True
            suggestion = (
                "Check whether the dependent service is running, "
                "then retry."
            )
        else:
            retryable = False
            suggestion = (
                "Inspect the error details and backend logs before "
                "retrying this operation."
            )

        return {
            "success": False,
            "error": f"{error_type}: {message}",
            "error_type": error_type,
            "retryable": retryable,
            "recovery_suggestion": suggestion,
        }

    def should_retry(self, result, attempt):
        """
        attempt is the current attempt number, starting at 1.
        max_retries=2 allows one initial attempt and two retries.
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
