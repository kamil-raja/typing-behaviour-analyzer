"""API error codes and JSON error-response helpers.

Routes use this module to return errors in the single documented shape.
It contains no database or metric logic.
"""

from flask import Response, jsonify

INVALID_JSON = "INVALID_JSON"
VALIDATION_ERROR = "VALIDATION_ERROR"
INVALID_EVENT_SEQUENCE = "INVALID_EVENT_SEQUENCE"
INCOMPLETE_SESSION = "INCOMPLETE_SESSION"
SESSION_TOO_SHORT = "SESSION_TOO_SHORT"
TEXT_NOT_FOUND = "TEXT_NOT_FOUND"
NOT_FOUND = "NOT_FOUND"
PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
INTERNAL_ERROR = "INTERNAL_ERROR"


def json_error(
    code: str,
    message: str,
    details: list[dict[str, str]] | None = None,
    status: int = 422,
) -> tuple[Response, int]:
    """Return a JSON error response in the documented API shape."""
    return (
        jsonify(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or [],
                }
            }
        ),
        status,
    )
