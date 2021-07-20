import hashlib
from datetime import datetime
from enum import Enum

import itsdangerous
from pydantic import BaseModel, Field, ValidationError, validator


_signer = None


def create_signer(secret_key, salt):
    """Create a signer configured how we like it.

    The secret_key should be a cyptographically random key.

    The salt should be specific to intend usage of the signature, but does not
    need to be random. It acts to partition signatures between use cases that
    shared the same secret_key.

    The length of secret_key and salt together should be more than the digest
    size, which for sha256 is 32 bytes.

    See https://itsdangerous.palletsprojects.com/en/2.0.x/concepts/ for more info.

    Ideally, we'd use cryptography for this, but that's a much heavier
    dependency than itsdangerous, which is pure python."""
    combined = (secret_key + salt).encode("utf8")
    assert len(combined) > 32, "secret_key+salt needs to be > 32 bytes"
    return itsdangerous.Signer(
        secret_key=secret_key,
        salt=salt,
        key_derivation="hmac",  # would like to use HDKF, but not supported
        digest_method=hashlib.sha256,
    )


def get_default_signer():
    if _signer is None:  # pragma: no cover
        raise RuntimeError("signer not configured - call signing.set_default_key(...)")
    return _signer


def set_default_key(key, salt):
    """Set the default signing key and salt for an app."""
    global _signer
    # Use the basic signer, which uses hmac with sha-1.
    # We encode our own payloads, so we can make use of pydantic's json
    # advanced serialization
    _signer = create_signer(key, salt)


class TokenScopes(str, Enum):
    view = "view"
    release = "release"
    upload = "upload"


class AuthToken(BaseModel):
    """An signed auth token.

    The signed format json serialized version this model, with a signature.

    This model includes all the logic needed to generate, sign, parse and
    validate a signed auth token. This is so that we can ensure that it is very
    difficult create an invalid token by accident, and so in future we can
    share one implementation of this token between projects.
    """

    url: str = Field(description="url prefix the token is valid for")
    user: str = Field(decription="the user this token was signed for")
    expiry: datetime = Field(
        description="the UTC datetime after which this token expires"
    )
    scope: TokenScopes = Field(TokenScopes.view, description="the scope of this token")

    class Config:
        # do not allow anyone to set values after instantiation
        allow_mutation = False

    @validator("url")
    def check_url(cls, v):
        """Enforce that we need a fully qualified url."""
        if v.startswith("http://") or v.startswith("https://"):
            return v
        raise ValueError(f"Invalid url {v}")

    @validator("expiry")
    def check_expiry(cls, v):
        """Enforce the token has not expired."""
        if datetime.utcnow() > v:
            raise ValueError(f"token expired on {v.isoformat()}")
        return v

    def sign(self, signer=None):
        if signer is None:
            signer = get_default_signer()
        # serialize to json with pydantic, which handles datetimes by default
        return signer.sign(self.json()).decode("utf8")

    @classmethod
    def verify(cls, token_string, signer=None):
        if signer is None:
            signer = get_default_signer()
        try:
            payload = signer.unsign(token_string)
        except itsdangerous.BadSignature:
            raise ValidationError(["bad signature"], cls)

        # Use pydantics json parsing. The individual fields will be validated
        # as normal
        return cls.parse_raw(payload)
