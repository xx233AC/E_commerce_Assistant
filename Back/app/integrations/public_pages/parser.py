"""Extract explicit public metadata. Missing values remain missing."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import unescape
from html.parser import HTMLParser
import json
import re
from urllib.parse import urljoin, urlsplit

from app.core.exceptions import ApiError
from app.integrations.public_pages.client import check_url_syntax


def _text(value, max_length):
    if not isinstance(value, str):
        return None
    value = re.sub(r'\s+', ' ', unescape(value)).strip()
    return value[:max_length] or None


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.title_parts = []
        self.jsonld = []
        self.in_title = False
        self.in_jsonld = False
        self.script_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            key = (attrs.get('property') or attrs.get('name') or attrs.get('itemprop') or '').lower()
            if key and attrs.get('content'):
                self.meta.setdefault(key, attrs['content'])
        elif tag == 'title':
            self.in_title = True
        elif tag == 'script' and attrs.get('type', '').lower() == 'application/ld+json':
            self.in_jsonld, self.script_parts = True, []

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        elif tag == 'script' and self.in_jsonld:
            if len(self.jsonld) < 30:
                try:
                    self.jsonld.append(json.loads(''.join(self.script_parts)))
                except (ValueError, RecursionError):
                    pass
            self.in_jsonld, self.script_parts = False, []

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        if self.in_jsonld:
            self.script_parts.append(data)


def _products(value, depth=0):
    if depth > 12:
        return []
    if isinstance(value, list):
        return [product for item in value[:100] for product in _products(item, depth + 1)]
    if not isinstance(value, dict):
        return []
    types = value.get('@type', [])
    types = [types] if isinstance(types, str) else types
    if not isinstance(types, list):
        types = []
    if 'Product' in types:
        return [value]
    return _products(value.get('@graph', []), depth + 1)


def _price(amount, currency, warnings):
    if amount is None:
        return None
    if str(currency or '').upper() not in {'CNY', 'RMB'}:
        warnings.append('页面价格币种未明确为人民币，未自动写入 price。')
        return None
    try:
        value = Decimal(str(amount))
        if not value.is_finite() or value < 0 or value > Decimal('999999999999.99'):
            return None
        return format(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), '.2f')
    except (InvalidOperation, ValueError):
        return None


def parse_metadata(source_url, html, *, final_url=None):
    parser = MetadataParser()
    parser.feed(html)
    meta = parser.meta
    title = _text(meta.get('og:title') or ''.join(parser.title_parts), 500)
    if title and any(marker in title.casefold() for marker in ('captcha', 'access denied', 'verify you are human', '安全验证', '验证码', '请先登录')):
        raise ApiError(422, 'PUBLIC_ACCESS_RESTRICTED', '页面要求登录或验证，请人工录入；系统不会绕过访问限制')
    candidates = [p for block in parser.jsonld for p in _products(block)]
    product = candidates[0] if candidates else {}
    warnings = ['解析内容仅为公开页面候选信息，采纳前请人工核对；系统不会覆盖竞品资料。']
    if len(candidates) > 1:
        warnings.append('页面包含多个商品结构化条目，当前展示第一条候选，请核对是否为目标商品。')
    name = _text(product.get('name') or meta.get('og:title'), 200)
    offers = product.get('offers', {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
        warnings.append('页面包含多个报价，仅读取第一项明确报价。')
    if not isinstance(offers, dict):
        offers = {}
    price = _price(offers.get('price', meta.get('product:price:amount')), offers.get('priceCurrency', meta.get('product:price:currency')), warnings)
    description = _text(product.get('description') or meta.get('og:description') or meta.get('description'), 4000)
    images = product.get('image', [])
    if isinstance(images, (str, dict)):
        images = [images]
    if not isinstance(images, list):
        images = []
    images = images + [meta.get('og:image')]
    image_urls = []
    for image in images[:100]:
        if isinstance(image, dict):
            image = image.get('url') or image.get('contentUrl')
        if not isinstance(image, str) or not image.strip():
            continue
        target = urljoin(final_url or source_url, image)
        try:
            check_url_syntax(target)
        except ApiError:
            continue
        if target not in image_urls:
            image_urls.append(target)
        if len(image_urls) == 20:
            break
    if final_url and final_url != source_url:
        warnings.append('目标页面发生公开重定向；候选信息来自最终公开页面。')
    result = {'source_url': source_url, 'name': name, 'title': title or _text(product.get('name'), 500), 'price': price,
        'sales_hint': None, 'selling_points': [description] if description else [], 'candidate_image_urls': image_urls,
        'missing_fields': [], 'warnings': warnings, 'captured_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}
    result['missing_fields'] = [key for key in ('name', 'title', 'price', 'sales_hint', 'selling_points', 'candidate_image_urls') if not result[key]]
    return result
