import ipaddress
import socket
from urllib.parse import urlsplit

from app.core.config import get_settings
from app.core.exceptions import ApiError


def validate_public_url(url, provider=False):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.port not in (None,80,443):
        raise ApiError(422,'UNSUPPORTED_PUBLIC_URL','只允许标准HTTP/HTTPS公网地址')
    if provider and p.hostname.lower() not in {x.strip().lower() for x in get_settings().outbound_allowed_hosts.split(',')}:
        raise ApiError(422,'UNSUPPORTED_PUBLIC_URL','请先由管理员将供应商域名加入服务端允许列表')
    try:
        addresses={x[4][0] for x in socket.getaddrinfo(p.hostname,p.port or (443 if p.scheme=='https' else 80),type=socket.SOCK_STREAM)}
    except socket.gaierror:
        raise ApiError(422,'UNSUPPORTED_PUBLIC_URL','无法解析公开地址') from None
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ApiError(422,'UNSUPPORTED_PUBLIC_URL','禁止请求内网或保留地址')
    return url
