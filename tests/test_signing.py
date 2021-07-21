from datetime import datetime, timedelta, timezone

import itsdangerous
import pytest
from pydantic import ValidationError

from hatch import signing


def test_token_sign_verify_roundtrip():
    token1 = signing.AuthToken(
        url="https://example.com/url",
        user="user",
        expiry=datetime.now(timezone.utc) + timedelta(minutes=1),
        scope="view",
    )
    token_string = token1.sign()

    token2 = signing.AuthToken.verify(token_string)
    assert token1 == token2


def test_token_url_invalid():
    with pytest.raises(ValidationError):
        signing.AuthToken(
            url="bad",
            user="user",
            expiry=datetime.now(timezone.utc) + timedelta(minutes=1),
            scope="view",
        )


def test_token_scope_invalid():
    with pytest.raises(ValidationError):
        signing.AuthToken(
            url="https://example.com/url",
            user="user",
            expiry=datetime.now(timezone.utc) + timedelta(minutes=1),
            scope="bad scope",
        )


def test_token_expired():
    with pytest.raises(ValidationError):
        signing.AuthToken(
            url="https://example.com/url",
            user="user",
            expiry=datetime.now(timezone.utc) - timedelta(minutes=1),
            scope="view",
        )


def test_token_mismatched_secrets():
    token = signing.AuthToken(
        url="https://example.com/url",
        user="user",
        expiry=datetime.now(timezone.utc) + timedelta(minutes=1),
        scope="view",
    )
    token_string = token.sign()
    serializer = itsdangerous.Signer("bad secret")

    with pytest.raises(ValidationError):
        signing.AuthToken.verify(token_string, serializer)


def test_token_bad_payload():
    payload = "not a json object"
    signer = signing.get_default_signer()
    token_string = signer.sign(payload)
    with pytest.raises(ValidationError):
        signing.AuthToken.verify(token_string)
