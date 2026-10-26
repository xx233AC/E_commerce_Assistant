class ModelError(Exception):
    """Messages are deliberately safe for display in a job error response."""
    def __init__(self, code, message, *, retryable=False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

