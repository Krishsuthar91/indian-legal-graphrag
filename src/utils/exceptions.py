"""Custom exception classes."""

from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base application exception."""

    def __init__(self, detail: str, code: str = "APP_ERROR", status_code: int = 500):
        self.code = code
        super().__init__(status_code=status_code, detail=detail)


class NotFoundException(AppException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(detail=detail, code="NOT_FOUND", status_code=status.HTTP_404_NOT_FOUND)


class ValidationException(AppException):
    def __init__(self, detail: str = "Validation failed"):
        super().__init__(
            detail=detail,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class ServiceUnavailableException(AppException):
    def __init__(self, detail: str = "Service temporarily unavailable"):
        super().__init__(
            detail=detail,
            code="SERVICE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
