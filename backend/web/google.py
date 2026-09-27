"""
Google 로그인 — OpenID Connect 인가 코드 흐름 (새 의존성 없이)

1. start: state(CSRF) · nonce 를 세션에 두고 Google 로 보낸다
2. callback: state 확인 → 서버가 토큰 엔드포인트에서 코드를 ID 토큰으로 바꾼다
3. ID 토큰 확인: iss · aud(우리 client_id) · exp · nonce · email_verified
   토큰 엔드포인트와 TLS 로 직접 주고받은 ID 토큰이라 서명 검증 대신 TLS 서버 확인을 쓴다 (OIDC Core §3.1.3.7)

GOOGLE_CLIENT_ID · GOOGLE_CLIENT_SECRET 이 없으면 꺼져 있다(버튼도 없다).
"""
import base64
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

AUTHORIZE_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
ISSUERS = {'https://accounts.google.com', 'accounts.google.com'}
SESSION_KEY = 'google_oauth'
CLOCK_SKEW = 60


class GoogleLoginError(Exception):
    pass


def enabled():
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def authorization_url(request, redirect_uri, next_url='', invite=''):
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    request.session[SESSION_KEY] = {'state': state, 'nonce': nonce, 'next': next_url, 'invite': invite,
                                    'redirect_uri': redirect_uri, 'at': int(time.time())}
    query = urllib.parse.urlencode({
        'client_id': settings.GOOGLE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'nonce': nonce,
        'prompt': 'select_account',
    })
    return f'{AUTHORIZE_URL}?{query}'


def exchange_code(code, redirect_uri):
    """코드 → 토큰 응답(dict). 테스트에서 바꿔 끼운다"""
    body = urllib.parse.urlencode({
        'code': code,
        'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }).encode()
    request = urllib.request.Request(TOKEN_URL, data=body, method='POST',
                                     headers={'Content-Type': 'application/x-www-form-urlencoded'})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, ValueError) as exc:
        raise GoogleLoginError('Could not reach Google.') from exc


def _decode_payload(id_token):
    try:
        payload = id_token.split('.')[1]
        return json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
    except (IndexError, ValueError) as exc:
        raise GoogleLoginError('Malformed ID token.') from exc


def verify_callback(request, params):
    """콜백 → 확인된 claims(dict: sub, email, name …)와 세션에 둔 next · invite"""
    saved = request.session.pop(SESSION_KEY, None)
    if not saved:
        raise GoogleLoginError('Login session expired. Start again.')
    if params.get('error'):
        raise GoogleLoginError('Google login was cancelled.')
    if not params.get('state') or not secrets.compare_digest(params['state'], saved['state']):
        raise GoogleLoginError('Login state mismatch. Start again.')
    if int(time.time()) - saved.get('at', 0) > 600:
        raise GoogleLoginError('Login took too long. Start again.')
    if not params.get('code'):
        raise GoogleLoginError('No authorization code.')

    tokens = exchange_code(params['code'], saved['redirect_uri'])
    claims = _decode_payload(tokens.get('id_token', ''))
    now = int(time.time())
    if claims.get('iss') not in ISSUERS:
        raise GoogleLoginError('Unexpected issuer.')
    audience = claims.get('aud')
    if audience != settings.GOOGLE_CLIENT_ID and not (isinstance(audience, list) and settings.GOOGLE_CLIENT_ID in audience):
        raise GoogleLoginError('ID token is not for this app.')
    if int(claims.get('exp', 0)) < now - CLOCK_SKEW:
        raise GoogleLoginError('ID token expired.')
    if not claims.get('nonce') or not secrets.compare_digest(str(claims['nonce']), saved['nonce']):
        raise GoogleLoginError('Nonce mismatch.')
    if not claims.get('sub'):
        raise GoogleLoginError('No subject.')
    if claims.get('email_verified') not in (True, 'true'):
        raise GoogleLoginError('This Google account has no verified email.')
    return claims, saved.get('next') or '', saved.get('invite') or ''
