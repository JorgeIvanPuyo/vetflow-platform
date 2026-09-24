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
