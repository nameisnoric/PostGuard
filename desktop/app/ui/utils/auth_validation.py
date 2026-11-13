"""Shared desktop validation for PostGuard authentication forms.

The rules in this module intentionally mirror ``backend.app.schemas.user`` so
the desktop can explain invalid input before sending it to the API.
"""

from __future__ import annotations

import re


KU_EMAIL_PATTERN = re.compile(r"^[^\s@]+@ku\.th$", re.IGNORECASE)


def email_validation_errors(email: str) -> list[str]:
    """Return user-facing KU email validation errors."""
    value = email.strip()
    if not value:
        return ["กรุณากรอกอีเมล KU"]
    if not KU_EMAIL_PATTERN.fullmatch(value):
        return ["อีเมลต้องอยู่ในรูปแบบที่ถูกต้องและลงท้ายด้วย @ku.th"]
    return []


def password_validation_errors(password: str) -> list[str]:
    """Return every password rule that is currently unmet."""
    errors: list[str] = []
    if len(password) < 8:
        errors.append("ต้องมีอย่างน้อย 8 ตัวอักษร")
    if not re.search(r"[A-Z]", password):
        errors.append("ต้องมีตัวอักษรภาษาอังกฤษพิมพ์ใหญ่อย่างน้อย 1 ตัว")
    if not re.search(r"[a-z]", password):
        errors.append("ต้องมีตัวอักษรภาษาอังกฤษพิมพ์เล็กอย่างน้อย 1 ตัว")
    if not re.search(r"\d", password):
        errors.append("ต้องมีตัวเลขอย่างน้อย 1 ตัว")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("ต้องมีอักขระพิเศษอย่างน้อย 1 ตัว เช่น ! @ # $ %")
    return errors


def validation_message(title: str, errors: list[str]) -> str:
    """Format validation failures as a readable bullet list."""
    if not errors:
        return ""
    return f"{title}\n" + "\n".join(f"• {error}" for error in errors)


def password_feedback(password: str) -> str:
    """Build live feedback for a password field."""
    if not password:
        return (
            "รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร พร้อมตัวพิมพ์ใหญ่ "
            "ตัวพิมพ์เล็ก ตัวเลข และอักขระพิเศษ"
        )
    errors = password_validation_errors(password)
    if not errors:
        return "✓ รหัสผ่านผ่านเงื่อนไขทั้งหมด"
    return validation_message("รหัสผ่านยังขาด:", errors)


def response_error_message(response, fallback: str) -> str:
    """Extract FastAPI validation details without exposing raw structures."""
    try:
        payload = response.json()
    except (ValueError, AttributeError, TypeError):
        return fallback
    if not isinstance(payload, dict):
        return fallback
    detail = payload.get("detail")
    if isinstance(detail, str) and detail.strip():
        translations = {
            "Current password is incorrect.": "รหัสผ่านปัจจุบันไม่ถูกต้อง",
            "New password must be different from the current password.": (
                "รหัสผ่านใหม่ต้องไม่เหมือนรหัสผ่านปัจจุบัน"
            ),
            "Invalid email or password": "อีเมลหรือรหัสผ่านไม่ถูกต้อง",
            "Email already registered": "อีเมลนี้ถูกลงทะเบียนแล้ว",
            "Email or username already registered": (
                "อีเมลหรือชื่อผู้ใช้นี้ถูกลงทะเบียนแล้ว"
            ),
        }
        return translations.get(detail.strip(), detail.strip())
    if isinstance(detail, list):
        messages: list[str] = []
        for item in detail:
            if not isinstance(item, dict):
                continue
            message = item.get("msg")
            if isinstance(message, str) and message.strip():
                message = message.removeprefix("Value error, ").strip()
                message = {
                    "Password must be at least 8 characters": "ต้องมีอย่างน้อย 8 ตัวอักษร",
                    "Password must be longer or equal 8 characters": "ต้องมีอย่างน้อย 8 ตัวอักษร",
                    "Password must contain at least one uppercase letter": "ต้องมีตัวพิมพ์ใหญ่อย่างน้อย 1 ตัว",
                    "Password must be have least 1 upper letter": "ต้องมีตัวพิมพ์ใหญ่อย่างน้อย 1 ตัว",
                    "Password must contain at least one lowercase letter": "ต้องมีตัวพิมพ์เล็กอย่างน้อย 1 ตัว",
                    "Password must be have least 1 lower letter": "ต้องมีตัวพิมพ์เล็กอย่างน้อย 1 ตัว",
                    "Password must contain at least one number": "ต้องมีตัวเลขอย่างน้อย 1 ตัว",
                    "Password must contain at least one special character": "ต้องมีอักขระพิเศษอย่างน้อย 1 ตัว",
                }.get(message, message)
                if message not in messages:
                    messages.append(message)
        if messages:
            return validation_message("ข้อมูลไม่ผ่านเงื่อนไข:", messages)
    return fallback
