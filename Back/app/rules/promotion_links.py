import ipaddress
import socket
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.exceptions import ApiError


def validate_public_url(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError()
        if any(ord(c) < 32 or ord(c) == 127 for c in url) or '\\' in url:
            raise ValueError()
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        addresses = {ipaddress.ip_address(r[4][0]) for r in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)}
        if not addresses or any(not a.is_global for a in addresses):
            raise ValueError()
    except (ValueError, OSError):
        raise ApiError(422, 'UNSUPPORTED_PUBLIC_URL', '目标必须是可解析的公网 HTTP(S) 地址，禁止内网、回环地址或带账号密码的地址') from None
    return url


def with_utm(url, utm):
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key not in {'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'}]
    query.extend(('utm_' + key, value) for key, value in utm.items() if value is not None)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
