"""Conservative transaction-intent rules. No price thresholds determine intent."""
import math
import re
import unicodedata

RULE_VERSION = 'title-intent-v1'
SALE = r'\b(can ban|chinh chu ban|ban gap|ban nhanh|gia ban|chuyen nhuong|ra ban|ban (nha|can ho|chung cu|dat|biet thu|lo|nen|shophouse|khach san|toa nha|mat tien))\b'
RENT = r'\b(cho thue|gia thue|can cho thue)\b'
MONTHLY = r'(/\s*thang\b|\b(trieu|tr|trd)\s*/\s*thang\b)'
CASHFLOW = r'\b(dang cho thue|hien (dang )?cho thue|hop dong (cho )?thue|dong tien|thu nhap|doanh thu|khai thac cho thue)\b'
DUAL = r'\b(ban (hoac|va|hay|/) (cho )?thue|ban/cho thue|ban va cho thue|vua ban vua cho thue|cho thue (hoac|va) ban)\b'
WANTED = r'\b(can mua|tim mua|can thue|tim thue|khong ban|khong cho thue|chua ban)\b'
RENT_OPEN = r'^\s*[-*.!: ]*(chinh chu |can |gap )?cho thue\b'
SALE_OPEN = r'^\s*[-*.!: ]*(chinh chu |can |gap )?(ban (nha|can ho|chung cu|dat|biet thu|lo|nen|shophouse)|chuyen nhuong)\b'


def sql_literal(value):
    return "'" + value.replace("'", "''") + "'"


def normalize_sql(column):
    return f"replace(strip_accents(lower(coalesce({column}, ''))), 'đ', 'd')"


def classifier_sql(raw_table='raw'):
    """SQL yields original columns plus label/reason, never mutates the listing."""
    def match(text, pattern):
        return f'regexp_matches({text}, {sql_literal(pattern)})'
    cash = match('_t', CASHFLOW)
    # A title advertising a sale of an occupied/income property can mention rent.
    title_rent = f"({match('_t', RENT)} OR {match('_t', MONTHLY)}) AND NOT ({cash})"
    condition = f"""
        WHEN wanted THEN 'AMBIGUOUS'
        WHEN dual THEN 'AMBIGUOUS'
        WHEN tsale AND (trent OR drent) THEN 'AMBIGUOUS'
        WHEN trent AND dsale THEN 'AMBIGUOUS'
        WHEN tsale THEN 'SALE_HIGH_CONFIDENCE'
        WHEN trent THEN 'RENT_HIGH_CONFIDENCE'
        ELSE 'AMBIGUOUS'
    """
    reason = """
        WHEN wanted THEN 'wanted_or_negated_offer'
        WHEN dual THEN 'dual_sale_rent_offer'
        WHEN tsale AND (trent OR drent) THEN 'sale_title_conflicts_with_rent_offer'
        WHEN trent AND dsale THEN 'rent_title_conflicts_with_sale_opening'
        WHEN tsale AND cashflow THEN 'explicit_sale_title_with_rental_cashflow_context'
        WHEN tsale THEN 'explicit_sale_title_no_opposing_primary_offer'
        WHEN trent THEN 'explicit_rent_or_monthly_title_no_sale_opening'
        ELSE 'insufficient_primary_intent_in_title'
    """
    return f"""
    WITH normalized AS (
        SELECT *, {normalize_sql('name')} AS _t,
            {normalize_sql('left(description, 240)')} AS _dstart FROM {raw_table}
    ), flags AS (
        SELECT *, {match('_t', SALE)} AS tsale, ({title_rent}) AS trent,
            {match('_t', CASHFLOW)} AS cashflow,
            {match('_t', WANTED)} AS wanted,
            ({match('_t', DUAL)} OR {match('_dstart', DUAL)}) AS dual,
            {match('_dstart', RENT_OPEN)} AS drent,
            {match('_dstart', SALE_OPEN)} AS dsale FROM normalized
    )
    SELECT * EXCLUDE (_t, _dstart, tsale, trent, cashflow, wanted, dual, drent, dsale),
        CASE {condition} END AS rule_label,
        CASE {reason} END AS rule_reason FROM flags
    """


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD', str(text or '').lower())
                   if unicodedata.category(c) != 'Mn').replace('đ', 'd')


PRICE_PATTERN = re.compile(r'(?<![\d.])(\d+(?:[.,]\d+)*)\s*(ty|ti|trieu|trd|tr)(?![a-z])')
EXCLUDE_CONTEXT = re.compile(r'\b(thue|thu nhap|doanh thu|dong tien|tra gop|tra truoc|chi can|dat coc|tien coc|von ban dau)\b')


def number(text):
    # Decimal comma/dot, with an explicit thousand separator only for groups of 3.
    if re.fullmatch(r'\d{1,3}(?:[.,]\d{3})+', text):
        return float(text.replace('.', '').replace(',', ''))
    return float(text.replace(',', '.'))


def parse_text_prices(title, description, area):
    """Audit candidates, excluding rent/deposits. Does not rewrite price.

    Supports decimal/composite ty/trieu and per-m2 rates. Multiple contradictory
    candidates remain unresolved; neither minimum nor best-matching price wins.
    """
    candidates = []
    for source, raw in [('title', title), ('description', description)]:
        text = normalize(raw)
        consumed = -1
        for match in PRICE_PATTERN.finditer(text):
            if match.start() < consumed:
                continue
            before = text[max(0, match.start()-65):match.start()]
            after = text[match.end():match.end()+40]
            # Scope preceding context to the nearest clause to avoid rejecting a
            # later explicit sale price after an earlier rental-income sentence.
            clause = re.split(r'[;\n.!]', before)[-1]
            explicit_sale_price = bool(re.search(r'gia ban\s*[:=]?\s*$', clause))
            if EXCLUDE_CONTEXT.search(clause) and not explicit_sale_price:
                continue
            if re.match(r'\s*(/|moi|mot)\s*(thang|ngay|nam|tuan)\b', after):
                continue
            if re.search(r'(usd|dollar|\$)', clause + after[:12]):
                continue
            try:
                value = number(match[1]) * (1e9 if match[2] in ('ty','ti') else 1e6)
            except ValueError:
                continue
            if match[2] in ('ty', 'ti'):
                tail = re.match(r'\s*(\d{1,3})(?:\s*(trieu|tr)\b)?', after)
                if tail and (tail[2] or tail.start() == 0 and after[0:1].isdigit()):
                    value += int(tail[1]) * (1e6 if tail[2] else 10**(9-len(tail[1])))
                    consumed = match.end() + tail.end()
                    after = text[consumed:consumed+40]
            per_m2 = bool(re.match(r'\s*(/|moi)\s*m\s*(2|²)\b', after))
            if per_m2:
                if area is None or not math.isfinite(area) or area <= 0:
                    continue
                total = value * area
            else:
                total = value
            if value > 0 and math.isfinite(total):
                candidates.append({'source': source, 'text': raw[match.start():match.end()+15],
                                   'parsed_value_vnd': value, 'basis': 'per_m2' if per_m2 else 'total',
                                   'total_equivalent_vnd': total})
    return candidates
