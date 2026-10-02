from dataclasses import dataclass, field
from pathlib import Path
import os
from urllib.parse import urlsplit

@dataclass
class Settings:
    data_dir: Path=field(default_factory=lambda:Path(os.getenv("DATA_DIR","/data")))
    public_url: str=field(default_factory=lambda:os.getenv("PUBLIC_URL","").rstrip("/"))
    admin_password: str=field(default_factory=lambda:os.getenv("ADMIN_PASSWORD",""))
    invite_code: str=field(default_factory=lambda:os.getenv("REGISTRATION_CODE",""))
    vapid_subject: str=field(default_factory=lambda:os.getenv("VAPID_SUBJECT",""))
    ll2_key: str=field(default_factory=lambda:os.getenv("LL2_API_KEY",""))
    poll_seconds: int=field(default_factory=lambda:max(600,int(os.getenv("POLL_SECONDS","600"))))
    worker_enabled: bool=field(default_factory=lambda:os.getenv("WORKER_ENABLED","true").lower()=="true")
    demo_mode: bool=field(default_factory=lambda:os.getenv("DEMO_MODE","false").lower()=="true")
    sources_enabled: bool=field(default_factory=lambda:os.getenv("SOURCES_ENABLED","true").lower()=="true")
    flightclub_key: str=field(default_factory=lambda:os.getenv("FLIGHTCLUB_API_KEY",""))
    def __post_init__(self):
        self.data_dir=Path(self.data_dir)
        if self.public_url:
            p=urlsplit(self.public_url)
            if p.scheme!="https" or not p.netloc or p.path or p.query or p.fragment or p.username:
                raise ValueError("PUBLIC_URL must be an HTTPS origin without a path, e.g. https://launch.example.com")
        if self.admin_password and len(self.admin_password)<12:
            raise ValueError("ADMIN_PASSWORD must contain at least 12 characters")
        if self.invite_code and len(self.invite_code)<16:
            raise ValueError("REGISTRATION_CODE must contain at least 16 characters")
        if self.vapid_subject and not self.vapid_subject.startswith(("mailto:","https://")):
            raise ValueError("VAPID_SUBJECT must be mailto:you@example.com or an HTTPS contact URL")
    @property
    def push_subject(self):
        return self.vapid_subject or self.public_url
