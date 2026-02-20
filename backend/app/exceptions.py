class TwelveDataError(Exception):
    """Raised when Twelve Data API returns an error."""

    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class FredError(Exception):
    """Raised when FRED API returns an error."""

    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)
