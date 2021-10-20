"""
Braze-related exception classes.
"""


class BrazeError(Exception):
    """
    Base class for Braze-related errors.
    """


class BrazeClientError(BrazeError):
    """
    Represents any Braze client error.
    """


class BrazeBadRequestError(BrazeClientError):
    """
    Represents a 400 bad request error.
    """


class BrazeUnauthorizedError(BrazeClientError):
    """
    Represents a 401 unauthorized error.
    """


class BrazeForbiddenError(BrazeClientError):
    """
    Represents a 403 forbidden error.
    """


class BrazeNotFoundError(BrazeClientError):
    """
    Represents a 404 forbidden error.
    """


class BrazeRateLimitError(BrazeClientError):
    """
    Represents a 429 rate limited error.
    """

    def __init__(self, reset_epoch_s):
        """
        Create a BrazeRateLimitError.

        Arguments:
            reset_epoch_s (float): Unix timestamp for when the API may be
            called again.
        """
        self.reset_epoch_s = reset_epoch_s
        super().__init__()


class BrazeInternalServerError(BrazeClientError):
    """
    Represents a 5XX internal server error.
    """
