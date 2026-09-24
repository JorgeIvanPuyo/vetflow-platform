from app.core import firebase


def test_create_firebase_user_reuses_existing_account_on_email_already_exists(
    monkeypatch,
):
    monkeypatch.setattr(firebase, "initialize_firebase_app", lambda: None)

    from firebase_admin import auth

    class _FakeUserRecord:
        uid = "existing-uid"

    def _raise_email_exists(**kwargs):
        raise auth.EmailAlreadyExistsError("email already exists", None, None)

    monkeypatch.setattr(auth, "create_user", _raise_email_exists)
    monkeypatch.setattr(auth, "get_user_by_email", lambda email: _FakeUserRecord())

    uid = firebase.create_firebase_user(
        email="orphaned@example.com",
        display_name="Orphaned Admin",
        password="temp-pass",
    )

    assert uid == "existing-uid"


def test_create_firebase_user_wraps_other_errors(monkeypatch):
    monkeypatch.setattr(firebase, "initialize_firebase_app", lambda: None)

    from firebase_admin import auth

    def _raise_unexpected(**kwargs):
        raise RuntimeError("network error")

    monkeypatch.setattr(auth, "create_user", _raise_unexpected)

    try:
        firebase.create_firebase_user(
            email="new@example.com",
            display_name="New Admin",
            password="temp-pass",
        )
        raise AssertionError("expected FirebaseUserProvisioningError")
    except firebase.FirebaseUserProvisioningError:
        pass


# Use the installed SDK's exception classes, not synthetic lookalikes.
import pytest
from firebase_admin import auth, exceptions


@pytest.mark.parametrize("failure", [
    auth.InvalidIdTokenError("sensitive detail"),
    auth.ExpiredIdTokenError("sensitive detail", None),
    auth.RevokedIdTokenError("sensitive detail"),
    auth.UserDisabledError("sensitive detail"),
])
def test_confirmed_invalid_credentials_return_401(client, monkeypatch, failure):
    monkeypatch.setattr(firebase, "initialize_firebase_app", lambda: None)
    def reject(_token):
        raise failure
    monkeypatch.setattr(auth, "verify_id_token", reject)
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_auth_token"
    assert "sensitive detail" not in response.text
    assert "data" not in response.json()


@pytest.mark.parametrize("failure", [
    auth.CertificateFetchError("sensitive detail", None),
    exceptions.UnavailableError("sensitive detail"),
    exceptions.InternalError("sensitive detail"),
    ConnectionError("sensitive detail"),
    TimeoutError("sensitive detail"),
    RuntimeError("sensitive detail"),
    ValueError("sensitive detail"),
])
def test_verification_unavailable_fails_closed_with_503(client, monkeypatch, failure):
    monkeypatch.setattr(firebase, "initialize_firebase_app", lambda: None)
    def reject(_token):
        raise failure
    monkeypatch.setattr(auth, "verify_id_token", reject)
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 503
    assert response.json() == {"error": {
        "code": "auth_verification_unavailable",
        "message": "Authentication verification temporarily unavailable",
    }}
    assert "sensitive detail" not in response.text


def test_initialization_failure_is_not_invalid_credentials(client, monkeypatch):
    def fail():
        raise ValueError("sensitive configuration")
    monkeypatch.setattr(firebase, "initialize_firebase_app", fail)
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 503
    assert "sensitive configuration" not in response.text
