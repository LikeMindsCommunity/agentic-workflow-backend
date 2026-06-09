from typing import Any


def success_response(data: Any = None) -> dict:
    return {"success": True, "data": data}


def error_response(message: str) -> dict:
    return {"success": False, "error_message": message}
