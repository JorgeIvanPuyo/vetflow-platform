import json
from typing import Any

from app.core.config import get_settings

_firebase_app: Any | None = None


class FirebaseTokenVerificationError(Exception):
    """Raised when Firebase Admin cannot validate an ID token."""


class FirebaseUserProvisioningError(Exception):
    """Raised when Firebase Admin cannot create or manage a user account."""


def initialize_firebase_app() -> Any:
    global _firebase_app

    if _firebase_app is not None:
        return _firebase_app

    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError as exc:
        raise RuntimeError("firebase-admin dependency is not installed") from exc

    if firebase_admin._apps:
        _firebase_app = firebase_admin.get_app()
        return _firebase_app

    settings = get_settings()
    options = {"projectId": settings.firebase_project_id} if settings.firebase_project_id else None

    if settings.firebase_service_account_json:
        try:
            service_account_info = json.loads(settings.firebase_service_account_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON must be valid JSON") from exc

        credential = credentials.Certificate(service_account_info)
        _firebase_app = firebase_admin.initialize_app(credential, options=options)
        return _firebase_app

    if settings.firebase_service_account_json_path:
        credential = credentials.Certificate(settings.firebase_service_account_json_path)
        _firebase_app = firebase_admin.initialize_app(credential, options=options)
        return _firebase_app

    # Fallback for same-project Cloud Run deployments. If Firebase Auth lives in
    # another GCP project, production must provide FIREBASE_SERVICE_ACCOUNT_JSON.
    _firebase_app = firebase_admin.initialize_app(options=options)
    return _firebase_app


def verify_id_token(id_token: str) -> dict[str, Any]:
    try:
        initialize_firebase_app()
        from firebase_admin import auth

        return auth.verify_id_token(id_token)
    except Exception as exc:  # Firebase exceptions vary by credentials/runtime.
        raise FirebaseTokenVerificationError("Invalid Firebase ID token") from exc


def create_firebase_user(email: str, display_name: str, password: str) -> str:
    """Create a Firebase Auth account and return its uid."""
    try:
        initialize_firebase_app()
        from firebase_admin import auth

        record = auth.create_user(
            email=email,
            display_name=display_name,
            password=password,
        )
        return record.uid
    except Exception as exc:  # Firebase exceptions vary by credentials/runtime.
        raise FirebaseUserProvisioningError(
            "Could not create Firebase user"
        ) from exc


def generate_password_reset_link(email: str) -> str:
    """Generate a password reset link to share with a newly invited user."""
    try:
        initialize_firebase_app()
        from firebase_admin import auth

        return auth.generate_password_reset_link(email)
    except Exception as exc:  # Firebase exceptions vary by credentials/runtime.
        raise FirebaseUserProvisioningError(
            "Could not generate password reset link"
        ) from exc
