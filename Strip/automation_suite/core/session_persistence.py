import os
import json
import time
import hashlib
import pickle
import gzip
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path


@dataclass
class StoredCookie:
    name: str
    value: str
    domain: str
    path: str
    expires: Optional[float] = None
    secure: bool = False
    http_only: bool = False
    same_site: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    
    def is_expired(self) -> bool:
        if self.expires is None:
            return False
        return time.time() > self.expires
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoredCookie":
        return cls(**data)


@dataclass
class StoredHeader:
    name: str
    value: str
    order: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoredHeader":
        return cls(**data)


@dataclass
class StoredFingerprint:
    user_agent: str
    accept_language: str
    accept_encoding: str
    platform: str
    vendor: str
    screen_width: int
    screen_height: int
    color_depth: int
    pixel_ratio: float
    timezone: str
    timezone_offset: int
    languages: List[str]
    hardware_concurrency: int
    device_memory: int
    webgl_vendor: str
    webgl_renderer: str
    canvas_hash: str
    audio_hash: str
    fonts_hash: str
    plugins_hash: str
    do_not_track: Optional[str] = None
    touch_support: bool = False
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoredFingerprint":
        return cls(**data)


@dataclass
class StoredProxy:
    protocol: str
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    last_used: float = field(default_factory=time.time)
    success_count: int = 0
    failure_count: int = 0
    
    def get_url(self) -> str:
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoredProxy":
        return cls(**data)


@dataclass
class StoredTLSFingerprint:
    ja3_hash: str
    cipher_suites: List[str]
    extensions: List[str]
    elliptic_curves: List[str]
    ec_point_formats: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoredTLSFingerprint":
        return cls(**data)


@dataclass
class StoredHTTP2Settings:
    header_table_size: int
    enable_push: bool
    max_concurrent_streams: int
    initial_window_size: int
    max_frame_size: int
    max_header_list_size: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoredHTTP2Settings":
        return cls(**data)


@dataclass
class CheckoutSessionData:
    session_id: str
    checkout_url: str
    checkout_url_hash: str
    domain: str
    platform: str
    gateway: str
    status: str
    created_at: float
    updated_at: float
    expires_at: float
    fingerprint: Optional[StoredFingerprint] = None
    tls_fingerprint: Optional[StoredTLSFingerprint] = None
    http2_settings: Optional[StoredHTTP2Settings] = None
    proxy: Optional[StoredProxy] = None
    cookies: List[StoredCookie] = field(default_factory=list)
    headers: List[StoredHeader] = field(default_factory=list)
    request_count: int = 0
    last_request_at: Optional[float] = None
    cart_id: Optional[str] = None
    cart_token: Optional[str] = None
    checkout_token: Optional[str] = None
    nonce_values: Dict[str, str] = field(default_factory=dict)
    csrf_tokens: Dict[str, str] = field(default_factory=dict)
    payment_data: Dict[str, Any] = field(default_factory=dict)
    billing_data: Dict[str, Any] = field(default_factory=dict)
    shipping_data: Dict[str, Any] = field(default_factory=dict)
    order_data: Dict[str, Any] = field(default_factory=dict)
    custom_data: Dict[str, Any] = field(default_factory=dict)
    request_history: List[Dict[str, Any]] = field(default_factory=list)
    error_log: List[Dict[str, Any]] = field(default_factory=list)
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at
    
    def is_active(self) -> bool:
        return self.status in ["active", "in_progress"] and not self.is_expired()
    
    def add_cookie(self, cookie: StoredCookie):
        for i, existing in enumerate(self.cookies):
            if existing.name == cookie.name and existing.domain == cookie.domain:
                self.cookies[i] = cookie
                return
        self.cookies.append(cookie)
    
    def get_cookie(self, name: str, domain: str = None) -> Optional[StoredCookie]:
        for cookie in self.cookies:
            if cookie.name == name:
                if domain is None or cookie.domain == domain:
                    if not cookie.is_expired():
                        return cookie
        return None
    
    def get_all_cookies(self, domain: str = None) -> List[StoredCookie]:
        result = []
        for cookie in self.cookies:
            if not cookie.is_expired():
                if domain is None or cookie.domain in domain or domain in cookie.domain:
                    result.append(cookie)
        return result
    
    def get_cookie_header(self, domain: str = None) -> str:
        cookies = self.get_all_cookies(domain)
        return "; ".join([f"{c.name}={c.value}" for c in cookies])
    
    def add_header(self, name: str, value: str, order: int = 0):
        for i, existing in enumerate(self.headers):
            if existing.name.lower() == name.lower():
                self.headers[i] = StoredHeader(name=name, value=value, order=order)
                return
        self.headers.append(StoredHeader(name=name, value=value, order=order))
    
    def get_header(self, name: str) -> Optional[str]:
        for header in self.headers:
            if header.name.lower() == name.lower():
                return header.value
        return None
    
    def get_all_headers(self) -> Dict[str, str]:
        sorted_headers = sorted(self.headers, key=lambda h: h.order)
        return {h.name: h.value for h in sorted_headers}
    
    def log_request(self, method: str, url: str, status_code: int, 
                    response_time: float, error: str = None):
        self.request_count += 1
        self.last_request_at = time.time()
        self.updated_at = time.time()
        
        log_entry = {
            "timestamp": time.time(),
            "method": method,
            "url": url,
            "status_code": status_code,
            "response_time": response_time,
            "request_number": self.request_count
        }
        
        if error:
            log_entry["error"] = error
            self.error_log.append({
                "timestamp": time.time(),
                "error": error,
                "url": url
            })
        
        self.request_history.append(log_entry)
        
        if len(self.request_history) > 1000:
            self.request_history = self.request_history[-500:]
    
    def set_nonce(self, key: str, value: str):
        self.nonce_values[key] = value
        self.updated_at = time.time()
    
    def get_nonce(self, key: str) -> Optional[str]:
        return self.nonce_values.get(key)
    
    def set_csrf_token(self, key: str, value: str):
        self.csrf_tokens[key] = value
        self.updated_at = time.time()
    
    def get_csrf_token(self, key: str) -> Optional[str]:
        return self.csrf_tokens.get(key)
    
    def to_dict(self) -> Dict[str, Any]:
        data = {
            "session_id": self.session_id,
            "checkout_url": self.checkout_url,
            "checkout_url_hash": self.checkout_url_hash,
            "domain": self.domain,
            "platform": self.platform,
            "gateway": self.gateway,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "request_count": self.request_count,
            "last_request_at": self.last_request_at,
            "cart_id": self.cart_id,
            "cart_token": self.cart_token,
            "checkout_token": self.checkout_token,
            "nonce_values": self.nonce_values,
            "csrf_tokens": self.csrf_tokens,
            "payment_data": self.payment_data,
            "billing_data": self.billing_data,
            "shipping_data": self.shipping_data,
            "order_data": self.order_data,
            "custom_data": self.custom_data,
            "request_history": self.request_history,
            "error_log": self.error_log
        }
        
        if self.fingerprint:
            data["fingerprint"] = self.fingerprint.to_dict()
        
        if self.tls_fingerprint:
            data["tls_fingerprint"] = self.tls_fingerprint.to_dict()
        
        if self.http2_settings:
            data["http2_settings"] = self.http2_settings.to_dict()
        
        if self.proxy:
            data["proxy"] = self.proxy.to_dict()
        
        data["cookies"] = [c.to_dict() for c in self.cookies]
        data["headers"] = [h.to_dict() for h in self.headers]
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckoutSessionData":
        fingerprint = None
        if data.get("fingerprint"):
            fingerprint = StoredFingerprint.from_dict(data["fingerprint"])
        
        tls_fingerprint = None
        if data.get("tls_fingerprint"):
            tls_fingerprint = StoredTLSFingerprint.from_dict(data["tls_fingerprint"])
        
        http2_settings = None
        if data.get("http2_settings"):
            http2_settings = StoredHTTP2Settings.from_dict(data["http2_settings"])
        
        proxy = None
        if data.get("proxy"):
            proxy = StoredProxy.from_dict(data["proxy"])
        
        cookies = [StoredCookie.from_dict(c) for c in data.get("cookies", [])]
        headers = [StoredHeader.from_dict(h) for h in data.get("headers", [])]
        
        return cls(
            session_id=data["session_id"],
            checkout_url=data["checkout_url"],
            checkout_url_hash=data["checkout_url_hash"],
            domain=data["domain"],
            platform=data.get("platform", "unknown"),
            gateway=data.get("gateway", "unknown"),
            status=data["status"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            expires_at=data["expires_at"],
            fingerprint=fingerprint,
            tls_fingerprint=tls_fingerprint,
            http2_settings=http2_settings,
            proxy=proxy,
            cookies=cookies,
            headers=headers,
            request_count=data.get("request_count", 0),
            last_request_at=data.get("last_request_at"),
            cart_id=data.get("cart_id"),
            cart_token=data.get("cart_token"),
            checkout_token=data.get("checkout_token"),
            nonce_values=data.get("nonce_values", {}),
            csrf_tokens=data.get("csrf_tokens", {}),
            payment_data=data.get("payment_data", {}),
            billing_data=data.get("billing_data", {}),
            shipping_data=data.get("shipping_data", {}),
            order_data=data.get("order_data", {}),
            custom_data=data.get("custom_data", {}),
            request_history=data.get("request_history", []),
            error_log=data.get("error_log", [])
        )


class SessionPersistenceManager:
    def __init__(self, storage_dir: str = "sessions", session_ttl: int = 3600):
        self.storage_dir = Path(storage_dir)
        self.session_ttl = session_ttl
        self.active_sessions: Dict[str, CheckoutSessionData] = {}
        self.url_to_session: Dict[str, str] = {}
        
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self._load_index()
    
    def _get_url_hash(self, url: str) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        normalized = f"{parsed.netloc}{parsed.path}"
        return hashlib.sha256(normalized.encode()).hexdigest()[:32]
    
    def _get_session_file_path(self, session_id: str) -> Path:
        return self.storage_dir / f"{session_id}.session.gz"
    
    def _get_index_file_path(self) -> Path:
        return self.storage_dir / "session_index.json"
    
    def _load_index(self):
        index_path = self._get_index_file_path()
        if index_path.exists():
            try:
                with open(index_path, 'r') as f:
                    data = json.load(f)
                    self.url_to_session = data.get("url_to_session", {})
            except (json.JSONDecodeError, IOError):
                self.url_to_session = {}
    
    def _save_index(self):
        index_path = self._get_index_file_path()
        data = {
            "url_to_session": self.url_to_session,
            "updated_at": time.time()
        }
        with open(index_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _generate_session_id(self) -> str:
        import random
        import string
        timestamp = int(time.time() * 1000)
        random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
        return f"sess_{timestamp}_{random_part}"
    
    def create_session(self, checkout_url: str, platform: str = "unknown",
                       gateway: str = "unknown") -> CheckoutSessionData:
        from urllib.parse import urlparse
        
        url_hash = self._get_url_hash(checkout_url)
        
        existing_session = self.get_session_by_url(checkout_url)
        if existing_session and existing_session.is_active():
            return existing_session
        
        parsed_url = urlparse(checkout_url)
        domain = parsed_url.netloc
        
        session_id = self._generate_session_id()
        current_time = time.time()
        
        session = CheckoutSessionData(
            session_id=session_id,
            checkout_url=checkout_url,
            checkout_url_hash=url_hash,
            domain=domain,
            platform=platform,
            gateway=gateway,
            status="active",
            created_at=current_time,
            updated_at=current_time,
            expires_at=current_time + self.session_ttl
        )
        
        self.active_sessions[session_id] = session
        self.url_to_session[url_hash] = session_id
        
        self.save_session(session)
        self._save_index()
        
        return session
    
    def get_session(self, session_id: str) -> Optional[CheckoutSessionData]:
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            if session.is_active():
                return session
        
        session = self._load_session_from_file(session_id)
        if session and session.is_active():
            self.active_sessions[session_id] = session
            return session
        
        return None
    
    def get_session_by_url(self, checkout_url: str) -> Optional[CheckoutSessionData]:
        url_hash = self._get_url_hash(checkout_url)
        
        session_id = self.url_to_session.get(url_hash)
        if session_id:
            return self.get_session(session_id)
        
        return None
    
    def save_session(self, session: CheckoutSessionData):
        session.updated_at = time.time()
        
        self.active_sessions[session.session_id] = session
        
        file_path = self._get_session_file_path(session.session_id)
        session_data = session.to_dict()
        
        with gzip.open(file_path, 'wt', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2)
    
    def _load_session_from_file(self, session_id: str) -> Optional[CheckoutSessionData]:
        file_path = self._get_session_file_path(session_id)
        
        if not file_path.exists():
            return None
        
        try:
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                data = json.load(f)
                return CheckoutSessionData.from_dict(data)
        except (json.JSONDecodeError, IOError, gzip.BadGzipFile):
            return None
    
    def update_session_status(self, session_id: str, status: str):
        session = self.get_session(session_id)
        if session:
            session.status = status
            session.updated_at = time.time()
            self.save_session(session)
    
    def extend_session(self, session_id: str, additional_time: int = None):
        session = self.get_session(session_id)
        if session:
            extend_by = additional_time or self.session_ttl
            session.expires_at = time.time() + extend_by
            session.updated_at = time.time()
            self.save_session(session)
    
    def end_session(self, session_id: str, final_status: str = "completed"):
        session = self.get_session(session_id)
        if session:
            session.status = final_status
            session.updated_at = time.time()
            self.save_session(session)
            
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
    
    def cleanup_expired_sessions(self):
        expired_sessions = []
        
        for session_id, session in list(self.active_sessions.items()):
            if session.is_expired():
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.end_session(session_id, "expired")
        
        for url_hash, session_id in list(self.url_to_session.items()):
            session = self.get_session(session_id)
            if not session or not session.is_active():
                del self.url_to_session[url_hash]
        
        self._save_index()
        
        return len(expired_sessions)
    
    def get_active_session_count(self) -> int:
        count = 0
        for session in self.active_sessions.values():
            if session.is_active():
                count += 1
        return count
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        session = self.get_session(session_id)
        if not session:
            return {}
        
        return {
            "session_id": session.session_id,
            "checkout_url": session.checkout_url,
            "domain": session.domain,
            "platform": session.platform,
            "gateway": session.gateway,
            "status": session.status,
            "created_at": datetime.fromtimestamp(session.created_at).isoformat(),
            "updated_at": datetime.fromtimestamp(session.updated_at).isoformat(),
            "expires_at": datetime.fromtimestamp(session.expires_at).isoformat(),
            "time_remaining": max(0, session.expires_at - time.time()),
            "request_count": session.request_count,
            "cookie_count": len(session.cookies),
            "header_count": len(session.headers),
            "error_count": len(session.error_log),
            "has_fingerprint": session.fingerprint is not None,
            "has_proxy": session.proxy is not None,
            "has_cart": session.cart_id is not None,
            "has_checkout_token": session.checkout_token is not None
        }
    
    def export_session(self, session_id: str, export_path: str = None) -> str:
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        if export_path is None:
            export_path = f"{session_id}_export.json"
        
        with open(export_path, 'w') as f:
            json.dump(session.to_dict(), f, indent=2)
        
        return export_path
    
    def import_session(self, import_path: str) -> CheckoutSessionData:
        with open(import_path, 'r') as f:
            data = json.load(f)
        
        session = CheckoutSessionData.from_dict(data)
        
        self.active_sessions[session.session_id] = session
        self.url_to_session[session.checkout_url_hash] = session.session_id
        
        self.save_session(session)
        self._save_index()
        
        return session
