import base64, hashlib, hmac, secrets, time
from collections import defaultdict, deque
from fastapi import HTTPException
from urllib.parse import urlsplit


def password_hash(password):
    salt=secrets.token_bytes(16)
    digest=hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1,dklen=32)
    return base64.b64encode(salt+digest).decode()

def verify_password(password,stored):
    try:
        raw=base64.b64decode(stored,validate=True)
        if len(raw)!=48: return False
        digest=hashlib.scrypt(password.encode(),salt=raw[:16],n=16384,r=8,p=1,dklen=32)
        return hmac.compare_digest(raw[16:],digest)
    except (ValueError,TypeError): return False

def token_hash(token): return hashlib.sha256(token.encode()).hexdigest()

class Limiter:
    def __init__(self): self.buckets=defaultdict(deque)
    def check(self,key,limit=10,period=60):
        now=time.monotonic()
        if len(self.buckets)>10000: self.buckets.clear()
        q=self.buckets[key]
        while q and q[0]<=now-period: q.popleft()
        if len(q)>=limit: raise HTTPException(429,"Too many requests; please wait and retry")
        q.append(now)

# Restrict registered push endpoints to browser push services, not arbitrary URLs.
# This prevents turning this home-server app into an unauthenticated LAN proxy.
PUSH_HOSTS={"fcm.googleapis.com","updates.push.services.mozilla.com","web.push.apple.com"}

def validate_push_endpoint(endpoint):
    p=urlsplit(endpoint)
    host=(p.hostname or "").lower()
    allowed=(host in PUSH_HOSTS or host.endswith(".push.apple.com") or host.endswith(".notify.windows.com"))
    if p.scheme!="https" or not allowed or p.username or p.password or p.port not in (None,443) or p.fragment:
        raise ValueError("Unsupported browser push service; HTTPS Chrome, Firefox, Apple and Windows endpoints are allowed")
    return endpoint
