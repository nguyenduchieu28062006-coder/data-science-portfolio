"""Strict primary sale intent and independently corroborated TOTAL VND price."""
import math
import re
from tinix_audit_rules import normalize

PRICE = re.compile(r'(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(ty|ti|trieu)\b')
RENT = re.compile(r'\b(cho thue|tim nguoi thue|can thue|tim thue|gia thue)\b')
SALE = re.compile(r'\b(ban|chuyen nhuong)\b')
NEGATIVE = re.compile(r'\b(khong ban|chua ban|can mua|tim mua|ban va cho thue|ban hoac cho thue)\b')
CONTEXT = re.compile(r'\b(thue|thu nhap|doanh thu|dong tien|tra gop|tra truoc|dat coc|tien coc|von ban dau|gia cu|gia goc|gia truoc|gia thi truong|dinh gia)\b')
RATE = re.compile(r'^\s*(?:/|moi|mot)\s*(?:m\s*(?:2|²)|thang|ngay|nam|tuan)\b')

def sale_intent(title):
    t=normalize(title)
    # An occupied property mentioned in description is allowed. Primary title is strict.
    return bool(SALE.search(t)) and not RENT.search(t) and not NEGATIVE.search(t)

def total_prices(title,description):
    values=[]
    for raw in (title,description):
        text=normalize(raw);consumed=-1
        for m in PRICE.finditer(text):
            if m.start()<consumed:continue
            before=re.split(r'[;\n.!]',text[max(0,m.start()-90):m.start()])[-1]
            if CONTEXT.search(before) and not re.search(r'gia ban\s*[:=]?\s*$',before):continue
            after=text[m.end():];end=m.end()
            value=float(m[1].replace(',','.'))*(1e9 if m[2] in ('ty','ti') else 1e6)
            if m[2] in ('ty','ti'):
                # Three digits after a billion unit denote millions: 5 ty 200.
                tail=re.match(r'\s+(\d{3})(?:\s+trieu\b)?(?![\d.,])',after)
                if tail:value+=int(tail[1])*1e6;end+=tail.end();after=text[end:]
            consumed=end
            if RATE.search(after) or re.match(r'^\s*(?:usd|dollar|\$)',after):continue
            # Unresolved shorthand (e.g. 5 ty 2) or a further amount is rejected.
            if re.match(r'^\s+\d+(?:\s*(?:trieu|ty)\b)',after):continue
            if math.isfinite(value) and value>0:values.append(value)
    return values

def verified_price(title,description,structured):
    try:s=float(structured)
    except (ValueError,TypeError):return None
    values=total_prices(title,description)
    if not values or not math.isfinite(s) or s<=0:return None
    # Every candidate must corroborate structured price; never choose best match.
    if any(abs(v-s)/v>.05 for v in values):return None
    return s
