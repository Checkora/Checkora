"""The Google side of "Continue with Google".

This is OpenID Connect's authorization code flow with PKCE. The browser goes
to Google, Google sends it back to /auth/google/callback/ with a code, and the
server trades that code for an ID token. Only the standard library is used,
so the Vercel build gains no dependency.
"""

import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
ISSUERS = ('https://accounts.google.com', 'accounts.google.com')
TIMEOUT_SECONDS = 10


class GoogleAuthError(Exception):
    """Google did not give us an identity we can trust."""


def is_configured():
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def new_attempt():
    """The random values that tie Google's answer to this one browser."""
    return {
        'state': secrets.token_urlsafe(24),
        'nonce': secrets.token_urlsafe(24),
        'verifier': secrets.token_urlsafe(48),
    }


def authorization_url(redirect_uri, attempt):
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(attempt['verifier'].encode()).digest()
    ).rstrip(b'=').decode()
    query = urllib.parse.urlencode({
        'client_id': settings.GOOGLE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': attempt['state'],
        'nonce': attempt['nonce'],
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
        'prompt': 'select_account',
    })
    return f'{AUTH_URL}?{query}'


def exchange_code(code, redirect_uri, verifier):
    """Trade the code from the callback for Google's ID token."""
    body = urllib.parse.urlencode({
        'code': code,
        'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
        'code_verifier': verifier,
    }).encode()
    request = urllib.request.Request(TOKEN_URL, data=body, method='POST')
    try:
        # TOKEN_URL is a fixed https address, never one taken from a request.
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310
            answer = json.load(response)
    except (OSError, ValueError) as exc:
        # HTTPError and URLError are both OSErrors; a bad body is a ValueError.
        raise GoogleAuthError(f'token request failed: {exc}') from exc

    id_token = answer.get('id_token') if isinstance(answer, dict) else None
    if not isinstance(id_token, str):
        raise GoogleAuthError('token response had no id_token')
    return id_token


def read_id_token(id_token, nonce):
    """Check the claims in an ID token and return the player's identity.

    The token came straight from Google's token endpoint over TLS, in answer
    to our client secret, so its signature is not checked again. Google's
    OpenID Connect guide allows this. The claims still are, because they say
    who the token was made for and whether it is still current.
    """
    try:
        payload = id_token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError) as exc:
        raise GoogleAuthError('id_token could not be read') from exc
    if not isinstance(claims, dict):
        raise GoogleAuthError('id_token payload is not an object')

    if claims.get('iss') not in ISSUERS:
        raise GoogleAuthError('id_token has the wrong issuer')
    if claims.get('aud') != settings.GOOGLE_CLIENT_ID:
        raise GoogleAuthError('id_token was made for another client')
    expires = claims.get('exp')
    if not isinstance(expires, (int, float)) or expires < time.time():
        raise GoogleAuthError('id_token has expired')
    token_nonce = claims.get('nonce')
    if not isinstance(token_nonce, str) or not secrets.compare_digest(
        token_nonce.encode(), nonce.encode()
    ):
        raise GoogleAuthError('id_token nonce does not match')

    sub = claims.get('sub')
    email = claims.get('email')
    if not isinstance(sub, str) or not sub:
        raise GoogleAuthError('id_token has no subject')
    if not isinstance(email, str) or '@' not in email:
        raise GoogleAuthError('id_token has no email')
    # Without this, someone could put another person's address on a Google
    # account and be signed in to that person's Checkora account.
    if claims.get('email_verified') not in (True, 'true'):
        raise GoogleAuthError('Google has not verified this email')

    return {'sub': sub, 'email': email.strip()}
