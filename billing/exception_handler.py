"""
Custom DRF exception handler for consistent frontend error responses.

Every error response will have the shape:
{
    "success": false,
    "error": "Human-readable error message",
    // optional field-level errors for validation
    "errors": { "field_name": ["..."] }
}

This makes it easy for the frontend to always check:
    if (!response.data.success) showError(response.data.error)
"""

from rest_framework.views import exception_handler as drf_exception_handler


def custom_exception_handler(exc, context):
    """
    Wrap the default DRF exception handler to produce consistent
    { success, error, errors? } responses for the frontend.
    """
    response = drf_exception_handler(exc, context)

    if response is None:
        # DRF didn't handle it (e.g. unhandled server error)
        return response

    # Build a normalised payload
    data = response.data

    # DRF returns `{"detail": "..."}` for auth/permission/throttle errors
    if isinstance(data, dict) and "detail" in data:
        error_message = str(data["detail"])
        response.data = {
            "success": False,
            "error": error_message,
        }

    # DRF validation: `{"field": ["msg", ...], ...}` (no "detail" key)
    elif isinstance(data, dict) and "success" not in data:
        # Field-level validation errors from serializers
        error_messages = []
        for field, msgs in data.items():
            if isinstance(msgs, list):
                for msg in msgs:
                    error_messages.append(f"{field}: {msg}")
            else:
                error_messages.append(f"{field}: {msgs}")

        response.data = {
            "success": False,
            "error": (
                "; ".join(error_messages) if error_messages else "Validation error"
            ),
            "errors": data,
        }

    # DRF can also return a list of errors (rare)
    elif isinstance(data, list):
        response.data = {
            "success": False,
            "error": "; ".join(str(e) for e in data),
        }

    # Already has "success" key — leave it alone (our own views)
    # but ensure "error" key exists for failed responses
    elif isinstance(data, dict) and data.get("success") is False:
        if "error" not in data and "message" in data:
            data["error"] = data.pop("message")
        elif "error" not in data:
            data["error"] = "An error occurred"

    return response
