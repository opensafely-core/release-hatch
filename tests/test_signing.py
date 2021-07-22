import json
from datetime import datetime, timedelta, timezone

import itsdangerous
import pytest
from pydantic import ValidationError
from pydantic.json import pydantic_encoder

from hatch import signing


def create_raw_token(value, signer=None):
    """To be used to create bad tokens that AuthToken won't let you create."""
    if signer is None:
        signer = signing.get_default_signer()
    if isinstance(value, (dict, list)):
        value = json.dumps(value, default=pydantic_encoder)
    return signer.sign(value).decode("utf8")


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


def test_token_object_url_invalid():
    with pytest.raises(ValidationError):
        signing.AuthToken(
            url="bad",
            user="user",
            expiry=datetime.now(timezone.utc) + timedelta(minutes=1),
            scope="view",
        )


def test_token_object_scope_invalid():
    with pytest.raises(ValidationError):
        signing.AuthToken(
            url="https://example.com/url",
            user="user",
            expiry=datetime.now(timezone.utc) + timedelta(minutes=1),
            scope="bad scope",
        )


def test_token_object_expired():
    with pytest.raises(signing.AuthToken.Expired):
        signing.AuthToken(
            url="https://example.com/url",
            user="user",
            expiry=datetime.now(timezone.utc) - timedelta(minutes=1),
            scope="view",
        )


def test_token_verify_mismatched_secrets():
    payload = dict(
        url="https://example.com/url",
        user="user",
        expiry=datetime.now(timezone.utc) + timedelta(minutes=1),
        scope="view",
    )
    signer = itsdangerous.Signer("bad secret")
    token = create_raw_token(payload, signer)

    with pytest.raises(ValidationError):
        signing.AuthToken.verify(token)


def test_token_verify_bad_payload_format():
    payload = "not a json object"
    token = create_raw_token(payload)
    with pytest.raises(ValidationError):
        signing.AuthToken.verify(token)


def test_token_verify_expired():
    payload = dict(
        url="https://example.com/url",
        user="user",
        expiry=datetime.now(timezone.utc) - timedelta(minutes=1),
        scope="view",
    )
    token = create_raw_token(payload)
    with pytest.raises(signing.AuthToken.Expired):
        signing.AuthToken.verify(token)


def test_token_verify_wrong_all_the_things():
    payload = dict(
        url="bad url",
        # missing user
        expiry=datetime.now(timezone.utc) - timedelta(minutes=1),
        scope="bad scope",
    )
    token = create_raw_token(payload)
    with pytest.raises(ValidationError) as exc_info:
        signing.AuthToken.verify(token)

    errors = {e["loc"][0]: e for e in exc_info.value.errors()}
    assert "url" in errors
    assert "user" in errors
    assert "expiry" in errors
    assert "scope" in errors
