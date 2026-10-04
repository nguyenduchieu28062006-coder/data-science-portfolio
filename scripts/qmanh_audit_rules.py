"""Independent conservative rules used only for source audit, never modeling."""
import math
import re
import unicodedata

RULE_VERSION = 'qmanh-source-audit-v5'


def normalize(raw):
    return ''.join(c for c in unicodedata.normalize('NFD', str(raw or '').lower())
                   if unicodedata.category(c) != 'Mn').replace('đ', 'd')


SALE = re.compile(r'\b(?:can ban|chinh chu ban|ban gap|ban nhanh|gia ban|chuyen nhuong|rao ban|ban (?:nha|can ho|chung cu|dat|biet thu|lo|nen|shophouse|khach san|toa nha|mat tien|kho|xuong|trang trai|van phong))\b')
RENT = re.compile(r'\b(?:cho thue|gia thue|can cho thue)\b')
MONTHLY = re.compile(r'(?:/\s*thang\b|\b(?:trieu|tr|trd)\s*/\s*thang\b)')
CASHFLOW = re.compile(r'\b(?:dang cho thue|hien (?:dang )?cho thue|hop dong (?:cho )?thue|dong tien|thu nhap|doanh thu|khai thac cho thue)\b')
DUAL = re.compile(r'\b(?:ban\s*(?:hoac|va|hay|/)\s*(?:cho )?thue|vua ban vua cho thue|cho thue (?:hoac|va) ban)\b')
WANTED = re.compile(r'\b(?:can mua|tim mua|can thue|tim thue|khong ban|chua ban)\b')
RENT_OPEN = re.compile(r'^\W*(?:(?:chinh chu |can |gap )*cho thue\b|(?:villa )?for\s*rent\b)')
SALE_OPEN = re.compile(r'^\W*(?:chinh chu |can |gap )?(?:ban\b|chuyen nhuong\b)')


def classify(title, description):
    t = normalize(title)
    d = normalize(description)[:300]
    tsale = bool(SALE.search(t))
    cash = bool(CASHFLOW.search(t))
    trent = bool(RENT.search(t) or MONTHLY.search(t)) and not cash
    if WANTED.search(t):
        return 'AMBIGUOUS', 'wanted_or_negated_title'
    if DUAL.search(t) or DUAL.search(d):
        return 'AMBIGUOUS', 'dual_offer'
    if tsale and (trent or RENT_OPEN.search(d)):
        return 'AMBIGUOUS', 'sale_title_rental_offer_conflict'
    if trent and SALE_OPEN.search(d):
        return 'AMBIGUOUS', 'rent_title_sale_opening_conflict'
    if tsale:
        return 'SALE_HIGH_CONFIDENCE', 'explicit_sale_with_cashflow' if cash else 'explicit_sale_title'
    # Rental cashflow, installment payments and future rental potential do not
    # create a high-confidence RENT label. Require a primary rental offer.
    if trent and (RENT_OPEN.search(t) or RENT_OPEN.search(d)):
        return 'RENT_HIGH_CONFIDENCE', 'explicit_rental_title'
    if trent:
        return 'AMBIGUOUS', 'rental_context_without_primary_rental_offer'
    return 'AMBIGUOUS', 'insufficient_primary_title_intent'


PRICE_PATTERN = re.compile(r'(?<![\d.,])(\d+(?:[.,]\d+)*)\s*(ty|ti|trieu|trd|tr)(?![a-z])')
EXCLUDE = re.compile(r'\b(?:thue|thu nhap|doanh thu|dong tien|tra gop|tra truoc|chi can|dat coc|tien coc|von|lai suat|hoa hong|vay|qua tang|tang tien|giam|booking|chi phi|dat cho)\b')
APPROX = re.compile(r'\b(?:hon|nhinh|duoi|tu|chi tu|khoang|tam)\s*$')
PER_M2 = re.compile(r'^\s*(?:vnd|vnđ|dong)?\s*(?:/|moi)\s*(?:1\s*)?m\s*(?:2|²)(?!\d)')
OTHER_AREA_RATE = re.compile(r'^\s*(?:/|moi)\s*(?:1\s*)?(?:sao|ha\b|hecta|cong\b|mn\b|met ngang|m\s+ngang|m(?!\s*[2²])\b)')


def number(token):
    # Three trailing digits may be thousands or fractional currency. Keep unresolved.
    if re.fullmatch(r'\d{1,3}[.,]\d{3}', token) and not token.startswith('0'):
        return None
    if re.fullmatch(r'\d{1,3}(?:[.,]\d{3}){2,}', token):
        return float(token.replace('.', '').replace(',', ''))
    try:
        value = float(token.replace(',', '.'))
        return value if math.isfinite(value) else None
    except ValueError:
        return None


def parse_prices(title, description, area):
    output = []
    for source, raw in (('title', title), ('description', description)):
        text = normalize(raw)
        consumed = -1
        for match in PRICE_PATTERN.finditer(text):
            if match.start() < consumed:
                continue
            before = text[max(0, match.start()-90):match.start()]
            if re.search(r'\d\s*m$', before):
                # Example: 89m23.4ty has no separator after m2; do not read 23.4.
                continue
            # Delimit on clauses, not decimal dots inside a price.
            clause = re.split(r'[;\n!•]', before)[-1]
            after = text[match.end():match.end()+65]
            explicit_sale = bool(re.search(r'gia ban\s*[:=]?\s*$', clause))
            if EXCLUDE.search(clause) and not explicit_sale:
                continue
            if re.match(r'\s*(?:/|moi|mot)\s*(?:thang|ngay|nam|tuan)', after):
                continue
            if re.match(r'\s*x+', after):
                # 6 ty x / 6 ty xx is an intentionally undisclosed range.
                continue
            value = number(match[1])
            if value is None or value <= 0:
                continue
            value *= 1e9 if match[2] in ('ty', 'ti') else 1e6
            endpoint = match.end()
            if match[2] in ('ty', 'ti'):
                compound = re.match(r'\s*(\d{1,3})\s*(?:trieu|tr)\b', after)
                if compound:
                    value += int(compound[1]) * 1e6
                    endpoint += compound.end()
                    consumed = endpoint
                    after = text[endpoint:endpoint+65]
                else:
                    bare = re.match(r'\s*(\d{1,3})(?!\d)(?=$|[\s,;.)/\-])', after)
                    if bare:
                        value += int(bare[1]) * 10**(9-len(bare[1]))
                        endpoint += bare.end()
                        consumed = endpoint
                        after = text[endpoint:endpoint+65]
                    elif re.match(r'\s*\d', after):
                        # Unsupported compound price; do not use just its integer ty.
                        continue
            per_m2 = bool(PER_M2.match(after))
            other_rate = bool(OTHER_AREA_RATE.match(after)) and not per_m2
            total = None if other_rate else value * area if per_m2 and area is not None and math.isfinite(area) and area > 0 else None if per_m2 else value
            output.append({'source': source, 'basis': 'other_area_rate' if other_rate else 'per_m2' if per_m2 else 'total',
                           'amount_vnd': value, 'total_equivalent_vnd': total,
                           'approximate': bool(APPROX.search(clause)),
                           'text_excerpt': text[max(0, match.start()-20):endpoint+15]})
    return output


def text_reference(candidates):
    """Pick a reference independently of stored Price; conflicting prices unresolved."""
    if any(x['basis'] == 'other_area_rate' for x in candidates):
        # A sao/cong depends on locality; do not invent a size or accept an
        # unqualified title amount when the description specifies another basis.
        return None, 'unsupported_area_rate_basis'
    for rate in (x for x in candidates if x['basis']=='per_m2'):
        for total in (x for x in candidates if x['basis']=='total'):
            if abs(total['amount_vnd']-rate['amount_vnd'])/rate['amount_vnd'] <= .01 and rate['total_equivalent_vnd'] is not None and abs(total['amount_vnd']-rate['total_equivalent_vnd'])/rate['total_equivalent_vnd'] > .01:
                return None, 'conflicting_total_and_rate_basis'
    preferred = [x for x in candidates if x['source'] == 'title'] or candidates
    values = []
    for item in preferred:
        value = item['total_equivalent_vnd']
        if value is not None and not any(abs(value-x)/max(value, x) <= .01 for x in values):
            values.append(value)
    if len(values) != 1:
        return None, 'multiple_reference_amounts' if values else 'no_supported_reference'
    return values[0], 'title_reference' if any(x['source'] == 'title' for x in preferred) else 'description_reference'


def audit_target(price, area, candidates, tolerance=.02):
    """Classifies evidence under hypothesis million VND, not a production label."""
    reference, reason = text_reference(candidates)
    if reference is None or price is None or not math.isfinite(price) or price <= 0:
        return 'AMBIGUOUS', reason
    preferred = [x for x in candidates if x['source'] == 'title'] or candidates
    rates = [x['amount_vnd'] for x in preferred if x['basis'] == 'per_m2']
    stored = price * 1e6
    total_match = abs(stored-reference)/reference <= tolerance
    rate_match = any(abs(stored-v)/v <= tolerance for v in rates)
    if total_match and not rate_match:
        return 'TOTAL_PRICE', 'matches_text_total_or_rate_times_area'
    if rate_match and not total_match:
        return 'PRICE_PER_M2', 'matches_explicit_text_rate'
    return 'AMBIGUOUS', 'total_rate_indistinguishable' if total_match else 'text_price_mismatch'
