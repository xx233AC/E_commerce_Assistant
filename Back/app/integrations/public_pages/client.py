"""Public HTML reader with DNS-pinned connections and bounded redirects.

No cookies, browser session, proxy environment, credentials or challenge solving.
TLS certificates and SNI are checked against the original URL hostname.
"""
from dataclasses import dataclass
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from app.core.exceptions import ApiError

USER_AGENT = 'CommerceAssistantPublicReader/1.0'
MAX_BYTES = 2 * 1024 * 1024
MAX_ROBOTS_BYTES = 256 * 1024
MAX_REDIRECTS = 4
TOTAL_SECONDS = 30


@dataclass(frozen=True)
class PublicPage:
    url: str
    text: str
    content_type: str


def check_url_syntax(url):
    """No DNS or network here: suitable for creating an undispatched task."""
    try:
        if not isinstance(url, str) or len(url) > 2048 or '\\' in url or any(ord(c) < 32 or ord(c) == 127 for c in url):
            raise ValueError()
        parts = urlsplit(url)
        if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password or parts.port not in {None, 80, 443}:
            raise ValueError()
        hostname = parts.hostname.encode('idna').decode('ascii').lower()
        if hostname in {'localhost', 'localhost.localdomain'} or hostname.endswith(('.localhost', '.local')):
            raise ValueError()
        try:
            literal = ipaddress.ip_address(hostname)
        except ValueError:
            literal = None
        if literal is not None and not literal.is_global:
            raise ValueError()
    except (ValueError, UnicodeError):
        raise ApiError(422, 'UNSUPPORTED_PUBLIC_URL', '仅支持标准端口的公开 HTTP(S) 地址，不允许凭据、内网或保留地址') from None
    return parts


def resolve_public_target(url):
    parts = check_url_syntax(url)
    host = parts.hostname.encode('idna').decode('ascii')
    port = parts.port or (443 if parts.scheme == 'https' else 80)
    try:
        addresses = list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise ValueError()
    except (OSError, ValueError):
        raise ApiError(422, 'UNSUPPORTED_PUBLIC_URL', '公开地址无法解析或解析到了内网、回环及保留地址') from None
    return parts, host, port, addresses


class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, port, address, timeout):
        super().__init__(host, port, timeout=timeout)
        self.address = address

    def connect(self):
        self.sock = socket.create_connection((self.address, self.port), self.timeout)


class _PinnedHTTPS(_PinnedHTTP):
    def connect(self):
        super().connect()
        context = ssl.create_default_context()
        context.set_alpn_protocols(['http/1.1'])
        try:
            self.sock = context.wrap_socket(self.sock, server_hostname=self.host)
        except Exception:
            self.sock.close()
            raise


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ApiError(503, 'PUBLIC_PAGE_TIMEOUT', '公开页面读取超时', retryable=True)
    return min(10.0, remaining)


def _request_once(url, deadline, limit):
    parts, host, port, addresses = resolve_public_target(url)
    # Use the already-validated numeric IP: the transport never resolves hostname again.
    connection_class = _PinnedHTTPS if parts.scheme == 'https' else _PinnedHTTP
    connection = connection_class(host, port, addresses[0], _remaining(deadline))
    target = urlunsplit(('', '', quote(parts.path or '/', safe="/%:@!$&'()*+,;=-._~"), quote(parts.query, safe="%/?@!$&'()*+,;=:-._~"), ''))
    try:
        connection.request('GET', target, headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,text/plain;q=0.5', 'Accept-Encoding': 'identity', 'Connection': 'close'})
        response = connection.getresponse()
        headers = dict(response.getheaders())
        headers = {key.lower(): value for key, value in headers.items()}
        if response.status in {301, 302, 303, 307, 308}:
            return response.status, headers, b''
        if headers.get('content-encoding', 'identity').lower() not in {'identity', ''}:
            raise ApiError(422, 'PUBLIC_PAGE_ENCODING_UNSUPPORTED', '页面未提供可安全读取的未压缩内容')
        length = headers.get('content-length')
        if length and (not length.isdigit() or int(length) > limit):
            raise ApiError(422, 'PUBLIC_PAGE_TOO_LARGE', '公开页面大小超过读取上限')
        chunks, size = [], 0
        while True:
            if connection.sock is not None:
                connection.sock.settimeout(_remaining(deadline))
            else:
                _remaining(deadline)
            chunk = response.read1(min(65536, limit - size + 1))
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise ApiError(422, 'PUBLIC_PAGE_TOO_LARGE', '公开页面大小超过读取上限')
            chunks.append(chunk)
        return response.status, headers, b''.join(chunks)
    except (socket.timeout, TimeoutError):
        raise ApiError(503, 'PUBLIC_PAGE_TIMEOUT', '公开页面读取超时', retryable=True) from None
    except (OSError, http.client.HTTPException):
        raise ApiError(503, 'PUBLIC_PAGE_UNAVAILABLE', '公开页面暂时无法读取', retryable=True) from None
    finally:
        connection.close()


def _fetch_bytes(url, deadline, limit):
    for _ in range(MAX_REDIRECTS + 1):
        status, headers, body = _request_once(url, deadline, limit)
        if status not in {301, 302, 303, 307, 308}:
            return status, headers, body, url
        if not headers.get('location'):
            raise ApiError(422, 'PUBLIC_REDIRECT_INVALID', '公开页面重定向缺少目标')
        url = urljoin(url, headers['location'])
        check_url_syntax(url)
    raise ApiError(422, 'PUBLIC_REDIRECT_LIMIT', '公开页面重定向次数超过上限')


def _robot_policy(url, deadline):
    parts = check_url_syntax(url)
    origin = urlunsplit((parts.scheme, parts.netloc, '', '', ''))
    status, headers, body, _ = _fetch_bytes(origin + '/robots.txt', deadline, MAX_ROBOTS_BYTES)
    robot = RobotFileParser()
    if status == 404:
        robot.parse([])
    elif status == 200:
        robot.parse(body.decode('utf-8', errors='replace').splitlines())
    else:
        raise ApiError(422, 'PUBLIC_ACCESS_RESTRICTED', '站点访问规则不可用或不允许自动读取，请改为人工录入')
    return robot


def fetch_public_html(url):
    deadline = time.monotonic() + TOTAL_SECONDS
    policies = {}
    for _ in range(MAX_REDIRECTS + 1):
        parts = check_url_syntax(url)
        origin = (parts.scheme, parts.netloc)
        if origin not in policies:
            policies[origin] = _robot_policy(url, deadline)
        if not policies[origin].can_fetch(USER_AGENT, url):
            raise ApiError(422, 'PUBLIC_ACCESS_RESTRICTED', '站点公开访问规则不允许读取此页面，请改为人工录入')
        status, headers, body = _request_once(url, deadline, MAX_BYTES)
        if status in {301, 302, 303, 307, 308}:
            if not headers.get('location'):
                raise ApiError(422, 'PUBLIC_REDIRECT_INVALID', '公开页面重定向缺少目标')
            url = urljoin(url, headers['location'])
            continue
        if status != 200:
            raise ApiError(422, 'PUBLIC_ACCESS_RESTRICTED', '目标页面不可公开读取，请改为人工录入')
        content_type = headers.get('content-type', '').lower()
        if content_type.split(';', 1)[0].strip() not in {'text/html', 'application/xhtml+xml'}:
            raise ApiError(422, 'PUBLIC_PAGE_TYPE_UNSUPPORTED', '仅解析公开 HTML 商品页面')
        charset = 'utf-8'
        for part in content_type.split(';')[1:]:
            if part.strip().startswith('charset='):
                charset = part.strip().split('=', 1)[1].strip('"\'')
        try:
            text = body.decode(charset, errors='replace')
        except LookupError:
            text = body.decode('utf-8', errors='replace')
        return PublicPage(url, text, content_type)
    raise ApiError(422, 'PUBLIC_REDIRECT_LIMIT', '公开页面重定向次数超过上限')
