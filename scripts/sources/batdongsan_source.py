"""Approved feed interface only. Automated ingestion requires approved access.

No website HTML scraping, link discovery, CAPTCHA or rate-limit bypass. Configure
only an API/feed whose access and reuse rights were explicitly approved by its
owner. The name does not assert Batdongsan.vn has granted access to this project.
"""
import json
import os
from urllib.parse import urlparse
from urllib.request import Request,HTTPRedirectHandler,build_opener

class NoFeedRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        # Access is approved for one endpoint; don't forward tokens elsewhere.
        raise ValueError('Feed redirects are not supported; configure the approved direct URL.')

class BatdongsanSource:
    def fetch_listings(self):
        """Requires approved API/feed or explicit permission."""
        return self.load()
    def configured(self):
        return os.getenv('MARKET_SOURCE_APPROVED')=='true' and all(os.getenv(k) for k in ['APPROVED_MARKET_FEED_URL','MARKET_SOURCE_APPROVAL_REFERENCE','MARKET_SOURCE_NAME'])
    def load(self):
        if not self.configured():raise RuntimeError('No approved market source configured.')
        url=os.environ['APPROVED_MARKET_FEED_URL'];parts=urlparse(url)
        if parts.scheme!='https' or parts.username or parts.password or not parts.hostname:raise ValueError('Approved feed must use HTTPS without credentials in URL.')
        if parts.path.lower().endswith(('.html','.htm')):raise ValueError('HTML crawling is not supported.')
        headers={'Accept':'application/json','User-Agent':'PortfolioApprovedMarketFeed/1.0'}
        if os.getenv('APPROVED_MARKET_FEED_TOKEN'):headers['Authorization']='Bearer '+os.environ['APPROVED_MARKET_FEED_TOKEN']
        with build_opener(NoFeedRedirect()).open(Request(url,headers=headers),timeout=30) as response:
            if 'application/json' not in response.headers.get('Content-Type',''):raise ValueError('Approved feed must return JSON.')
            payload=response.read(15*1024*1024+1)
        if len(payload)>15*1024*1024:raise ValueError('Feed exceeds configured single-request limit.')
        data=json.loads(payload)
        if not isinstance(data,list):raise ValueError('Expected a JSON list of explicitly typed sale listings.')
        return data
