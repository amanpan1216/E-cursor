import subprocess
import json
import os
import tempfile
import time
import random
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .browser import SessionManager, BrowserProfile, BrowserFingerprintGenerator
from .session_persistence import (
    SessionPersistenceManager,
    CheckoutSessionData,
    StoredCookie,
    StoredHeader,
    StoredFingerprint,
    StoredProxy,
    StoredTLSFingerprint,
    StoredHTTP2Settings
)


@dataclass
class HTTPResponse:
    status_code: int
    headers: Dict[str, str]
    body: str
    cookies: Dict[str, str]
    url: str
    elapsed: float
    redirects: List[str]


class TLSFingerprint:
    def __init__(self, browser: str = "chrome"):
        self.browser = browser
        self.cipher_suites = self._get_cipher_suites()
        self.extensions = self._get_extensions()
        self.elliptic_curves = self._get_elliptic_curves()
        self.ec_point_formats = self._get_ec_point_formats()
        
    def _get_cipher_suites(self) -> List[str]:
        chrome_ciphers = [
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
            "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
            "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
            "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
            "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
            "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
            "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA",
            "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA",
            "TLS_RSA_WITH_AES_128_GCM_SHA256",
            "TLS_RSA_WITH_AES_256_GCM_SHA384",
            "TLS_RSA_WITH_AES_128_CBC_SHA",
            "TLS_RSA_WITH_AES_256_CBC_SHA"
        ]
        
        firefox_ciphers = [
            "TLS_AES_128_GCM_SHA256",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
            "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
            "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
            "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
            "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
            "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
            "TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA",
            "TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA",
            "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA",
            "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA",
            "TLS_RSA_WITH_AES_128_GCM_SHA256",
            "TLS_RSA_WITH_AES_256_GCM_SHA384"
        ]
        
        safari_ciphers = [
            "TLS_AES_128_GCM_SHA256",
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
            "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
            "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
            "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
            "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
            "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256"
        ]
        
        edge_ciphers = [
            "TLS_AES_256_GCM_SHA384",
            "TLS_AES_128_GCM_SHA256",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
            "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
            "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
            "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
            "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
            "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256"
        ]
        
        if self.browser == "firefox":
            return firefox_ciphers
        elif self.browser == "safari":
            return safari_ciphers
        elif self.browser == "edge":
            return edge_ciphers
        return chrome_ciphers
    
    def _get_extensions(self) -> List[str]:
        chrome_extensions = [
            "server_name",
            "extended_master_secret",
            "renegotiation_info",
            "supported_groups",
            "ec_point_formats",
            "session_ticket",
            "application_layer_protocol_negotiation",
            "status_request",
            "signature_algorithms",
            "signed_certificate_timestamp",
            "key_share",
            "psk_key_exchange_modes",
            "supported_versions",
            "compress_certificate",
            "application_settings"
        ]
        
        firefox_extensions = [
            "server_name",
            "extended_master_secret",
            "renegotiation_info",
            "supported_groups",
            "ec_point_formats",
            "session_ticket",
            "application_layer_protocol_negotiation",
            "status_request",
            "delegated_credentials",
            "key_share",
            "supported_versions",
            "signature_algorithms",
            "psk_key_exchange_modes",
            "record_size_limit"
        ]
        
        if self.browser == "firefox":
            return firefox_extensions
        return chrome_extensions
    
    def _get_elliptic_curves(self) -> List[str]:
        return [
            "X25519",
            "secp256r1",
            "secp384r1"
        ]
    
    def _get_ec_point_formats(self) -> List[str]:
        return ["uncompressed"]
    
    def get_ja3_hash(self) -> str:
        ja3_string = f"{','.join(self.cipher_suites)}|{','.join(self.extensions)}|{','.join(self.elliptic_curves)}"
        return hashlib.md5(ja3_string.encode()).hexdigest()
    
    def to_stored(self) -> StoredTLSFingerprint:
        return StoredTLSFingerprint(
            ja3_hash=self.get_ja3_hash(),
            cipher_suites=self.cipher_suites,
            extensions=self.extensions,
            elliptic_curves=self.elliptic_curves,
            ec_point_formats=self.ec_point_formats
        )


class HTTP2Fingerprint:
    def __init__(self, browser: str = "chrome"):
        self.browser = browser
        self.settings = self._get_settings()
        self.window_update = self._get_window_update()
        self.priority = self._get_priority()
        
    def _get_settings(self) -> Dict[str, int]:
        chrome_settings = {
            "HEADER_TABLE_SIZE": 65536,
            "ENABLE_PUSH": 0,
            "MAX_CONCURRENT_STREAMS": 1000,
            "INITIAL_WINDOW_SIZE": 6291456,
            "MAX_FRAME_SIZE": 16384,
            "MAX_HEADER_LIST_SIZE": 262144
        }
        
        firefox_settings = {
            "HEADER_TABLE_SIZE": 65536,
            "ENABLE_PUSH": 0,
            "MAX_CONCURRENT_STREAMS": 100,
            "INITIAL_WINDOW_SIZE": 131072,
            "MAX_FRAME_SIZE": 16384
        }
        
        safari_settings = {
            "HEADER_TABLE_SIZE": 4096,
            "ENABLE_PUSH": 0,
            "MAX_CONCURRENT_STREAMS": 100,
            "INITIAL_WINDOW_SIZE": 2097152,
            "MAX_FRAME_SIZE": 16384,
            "MAX_HEADER_LIST_SIZE": 32768
        }
        
        if self.browser == "firefox":
            return firefox_settings
        elif self.browser == "safari":
            return safari_settings
        return chrome_settings
    
    def _get_window_update(self) -> int:
        if self.browser == "firefox":
            return 12517377
        elif self.browser == "safari":
            return 10485760
        return 15663105
    
    def _get_priority(self) -> Dict[str, Any]:
        return {
            "exclusive": True,
            "stream_dep": 0,
            "weight": 256
        }
    
    def to_stored(self) -> StoredHTTP2Settings:
        return StoredHTTP2Settings(
            header_table_size=self.settings.get("HEADER_TABLE_SIZE", 65536),
            enable_push=self.settings.get("ENABLE_PUSH", 0) == 1,
            max_concurrent_streams=self.settings.get("MAX_CONCURRENT_STREAMS", 1000),
            initial_window_size=self.settings.get("INITIAL_WINDOW_SIZE", 6291456),
            max_frame_size=self.settings.get("MAX_FRAME_SIZE", 16384),
            max_header_list_size=self.settings.get("MAX_HEADER_LIST_SIZE", 262144)
        )


class HeaderOrderManager:
    def __init__(self, browser: str = "chrome"):
        self.browser = browser
        
    def get_header_order(self) -> List[str]:
        chrome_order = [
            ":method",
            ":authority",
            ":scheme",
            ":path",
            "cache-control",
            "sec-ch-ua",
            "sec-ch-ua-mobile",
            "sec-ch-ua-platform",
            "upgrade-insecure-requests",
            "user-agent",
            "accept",
            "sec-fetch-site",
            "sec-fetch-mode",
            "sec-fetch-user",
            "sec-fetch-dest",
            "accept-encoding",
            "accept-language",
            "cookie"
        ]
        
        firefox_order = [
            ":method",
            ":path",
            ":authority",
            ":scheme",
            "user-agent",
            "accept",
            "accept-language",
            "accept-encoding",
            "connection",
            "cookie",
            "upgrade-insecure-requests",
            "sec-fetch-dest",
            "sec-fetch-mode",
            "sec-fetch-site",
            "sec-fetch-user"
        ]
        
        safari_order = [
            ":method",
            ":scheme",
            ":path",
            ":authority",
            "accept",
            "sec-fetch-site",
            "cookie",
            "sec-fetch-dest",
            "sec-fetch-mode",
            "user-agent",
            "accept-language",
            "accept-encoding"
        ]
        
        if self.browser == "firefox":
            return firefox_order
        elif self.browser == "safari":
            return safari_order
        return chrome_order
    
    def order_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        order = self.get_header_order()
        ordered = {}
        
        for key in order:
            header_key = key.lstrip(':')
            for h_key, h_value in headers.items():
                if h_key.lower() == header_key.lower():
                    ordered[h_key] = h_value
                    break
        
        for key, value in headers.items():
            if key not in ordered:
                ordered[key] = value
        
        return ordered


class BypassJSWrapper:
    def __init__(self, bypass_js_path: str = None):
        self.bypass_js_path = bypass_js_path
        self.node_available = self._check_node()
        
    def _check_node(self) -> bool:
        try:
            result = subprocess.run(["node", "--version"], capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def make_request(self, url: str, method: str = "GET", headers: Dict[str, str] = None, 
                     body: str = None, proxy: str = None) -> Optional[HTTPResponse]:
        if not self.node_available or not self.bypass_js_path:
            return None
        
        request_data = {
            "url": url,
            "method": method,
            "headers": headers or {},
            "body": body,
            "proxy": proxy
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(request_data, f)
            request_file = f.name
        
        try:
            result = subprocess.run(
                ["node", self.bypass_js_path, request_file],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                response_data = json.loads(result.stdout)
                return HTTPResponse(
                    status_code=response_data.get("status", 0),
                    headers=response_data.get("headers", {}),
                    body=response_data.get("body", ""),
                    cookies=response_data.get("cookies", {}),
                    url=response_data.get("url", url),
                    elapsed=response_data.get("elapsed", 0),
                    redirects=response_data.get("redirects", [])
                )
        except Exception:
            pass
        finally:
            os.unlink(request_file)
        
        return None


class PersistentHTTPClient:
    def __init__(self, session_storage_dir: str = "sessions", session_ttl: int = 3600,
                 use_bypass: bool = False, bypass_js_path: str = None):
        self.persistence_manager = SessionPersistenceManager(session_storage_dir, session_ttl)
        self.fingerprint_generator = BrowserFingerprintGenerator()
        self.use_bypass = use_bypass
        self.bypass_wrapper = BypassJSWrapper(bypass_js_path) if use_bypass else None
        
        self.current_checkout_session: Optional[CheckoutSessionData] = None
        self.current_proxy: Optional[str] = None
        self.requests_session: Optional[requests.Session] = None
        
    def _create_requests_session(self) -> requests.Session:
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def start_checkout_session(self, checkout_url: str, platform: str = "unknown",
                                gateway: str = "unknown", proxy: str = None) -> CheckoutSessionData:
        existing_session = self.persistence_manager.get_session_by_url(checkout_url)
        
        if existing_session and existing_session.is_active():
            self.current_checkout_session = existing_session
            self.current_proxy = existing_session.proxy.get_url() if existing_session.proxy else proxy
            self._restore_requests_session()
            return existing_session
        
        session = self.persistence_manager.create_session(checkout_url, platform, gateway)
        
        browser = random.choice(["chrome", "firefox", "safari", "edge"])
        fingerprint = self.fingerprint_generator.generate_fingerprint(browser)
        
        stored_fingerprint = StoredFingerprint(
            user_agent=fingerprint.user_agent,
            accept_language=fingerprint.accept_language,
            accept_encoding=fingerprint.accept_encoding,
            platform=fingerprint.platform,
            vendor=fingerprint.vendor,
            screen_width=fingerprint.screen_width,
            screen_height=fingerprint.screen_height,
            color_depth=fingerprint.color_depth,
            pixel_ratio=fingerprint.pixel_ratio,
            timezone=fingerprint.timezone,
            timezone_offset=fingerprint.timezone_offset,
            languages=fingerprint.languages,
            hardware_concurrency=fingerprint.hardware_concurrency,
            device_memory=fingerprint.device_memory,
            webgl_vendor=fingerprint.webgl_vendor,
            webgl_renderer=fingerprint.webgl_renderer,
            canvas_hash=fingerprint.canvas_hash,
            audio_hash=fingerprint.audio_hash,
            fonts_hash=fingerprint.fonts_hash,
            plugins_hash=fingerprint.plugins_hash,
            do_not_track=fingerprint.do_not_track,
            touch_support=fingerprint.touch_support
        )
        session.fingerprint = stored_fingerprint
        
        tls_fp = TLSFingerprint(browser)
        session.tls_fingerprint = tls_fp.to_stored()
        
        http2_fp = HTTP2Fingerprint(browser)
        session.http2_settings = http2_fp.to_stored()
        
        if proxy:
            parsed_proxy = self._parse_proxy(proxy)
            if parsed_proxy:
                session.proxy = parsed_proxy
                self.current_proxy = proxy
        
        self._generate_initial_headers(session, browser)
        
        self.persistence_manager.save_session(session)
        
        self.current_checkout_session = session
        self.requests_session = self._create_requests_session()
        
        return session
    
    def _parse_proxy(self, proxy: str) -> Optional[StoredProxy]:
        try:
            if "://" in proxy:
                protocol, rest = proxy.split("://", 1)
            else:
                protocol = "http"
                rest = proxy
            
            username = None
            password = None
            
            if "@" in rest:
                auth, host_port = rest.rsplit("@", 1)
                if ":" in auth:
                    username, password = auth.split(":", 1)
            else:
                host_port = rest
            
            if ":" in host_port:
                host, port = host_port.rsplit(":", 1)
                port = int(port)
            else:
                host = host_port
                port = 80 if protocol == "http" else 443
            
            return StoredProxy(
                protocol=protocol,
                host=host,
                port=port,
                username=username,
                password=password
            )
        except Exception:
            return None
    
    def _generate_initial_headers(self, session: CheckoutSessionData, browser: str):
        fp = session.fingerprint
        
        base_headers = [
            ("Host", session.domain),
            ("Connection", "keep-alive"),
            ("Cache-Control", "max-age=0"),
            ("Upgrade-Insecure-Requests", "1"),
            ("User-Agent", fp.user_agent),
            ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"),
            ("Accept-Language", fp.accept_language),
            ("Accept-Encoding", fp.accept_encoding)
        ]
        
        if browser == "chrome":
            chrome_version = "120"
            base_headers.extend([
                ("sec-ch-ua", f'"Not_A Brand";v="8", "Chromium";v="{chrome_version}", "Google Chrome";v="{chrome_version}"'),
                ("sec-ch-ua-mobile", "?0"),
                ("sec-ch-ua-platform", f'"{fp.platform}"'),
                ("Sec-Fetch-Site", "none"),
                ("Sec-Fetch-Mode", "navigate"),
                ("Sec-Fetch-User", "?1"),
                ("Sec-Fetch-Dest", "document")
            ])
        elif browser == "firefox":
            base_headers.extend([
                ("Sec-Fetch-Dest", "document"),
                ("Sec-Fetch-Mode", "navigate"),
                ("Sec-Fetch-Site", "none"),
                ("Sec-Fetch-User", "?1")
            ])
        elif browser == "safari":
            base_headers.extend([
                ("Sec-Fetch-Site", "none"),
                ("Sec-Fetch-Mode", "navigate"),
                ("Sec-Fetch-Dest", "document")
            ])
        
        for i, (name, value) in enumerate(base_headers):
            session.add_header(name, value, i)
    
    def _restore_requests_session(self):
        self.requests_session = self._create_requests_session()
        
        if self.current_checkout_session:
            for cookie in self.current_checkout_session.cookies:
                if not cookie.is_expired():
                    self.requests_session.cookies.set(
                        cookie.name,
                        cookie.value,
                        domain=cookie.domain,
                        path=cookie.path
                    )
    
    def get_current_session(self) -> Optional[CheckoutSessionData]:
        return self.current_checkout_session
    
    def get_session_headers(self, url: str = None) -> Dict[str, str]:
        if not self.current_checkout_session:
            return {}
        
        headers = self.current_checkout_session.get_all_headers()
        
        if url:
            parsed = urlparse(url)
            headers["Host"] = parsed.netloc
            
            cookie_header = self.current_checkout_session.get_cookie_header(parsed.netloc)
            if cookie_header:
                headers["Cookie"] = cookie_header
        
        return headers
    
    def update_headers_for_request(self, url: str, request_type: str = "navigate") -> Dict[str, str]:
        headers = self.get_session_headers(url)
        
        parsed = urlparse(url)
        referer = self.current_checkout_session.custom_data.get("last_url") if self.current_checkout_session else None
        
        if referer:
            headers["Referer"] = referer
            
            referer_parsed = urlparse(referer)
            if referer_parsed.netloc == parsed.netloc:
                headers["Sec-Fetch-Site"] = "same-origin"
            elif referer_parsed.netloc.endswith(parsed.netloc.split('.')[-2] + '.' + parsed.netloc.split('.')[-1]):
                headers["Sec-Fetch-Site"] = "same-site"
            else:
                headers["Sec-Fetch-Site"] = "cross-site"
        else:
            headers["Sec-Fetch-Site"] = "none"
        
        if request_type == "navigate":
            headers["Sec-Fetch-Mode"] = "navigate"
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-User"] = "?1"
        elif request_type == "xhr":
            headers["Sec-Fetch-Mode"] = "cors"
            headers["Sec-Fetch-Dest"] = "empty"
            headers["X-Requested-With"] = "XMLHttpRequest"
        elif request_type == "form":
            headers["Sec-Fetch-Mode"] = "navigate"
            headers["Sec-Fetch-Dest"] = "document"
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif request_type == "json":
            headers["Sec-Fetch-Mode"] = "cors"
            headers["Sec-Fetch-Dest"] = "empty"
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json, text/plain, */*"
        
        return headers
    
    def get(self, url: str, headers: Dict[str, str] = None,
            allow_redirects: bool = True, timeout: int = 30,
            request_type: str = "navigate") -> HTTPResponse:
        return self._make_request("GET", url, headers=headers,
                                  allow_redirects=allow_redirects, timeout=timeout,
                                  request_type=request_type)
    
    def post(self, url: str, data: Any = None, json_data: Dict = None,
             headers: Dict[str, str] = None, allow_redirects: bool = True,
             timeout: int = 30, request_type: str = "form") -> HTTPResponse:
        return self._make_request("POST", url, data=data, json_data=json_data,
                                  headers=headers, allow_redirects=allow_redirects,
                                  timeout=timeout, request_type=request_type)
    
    def _make_request(self, method: str, url: str, data: Any = None,
                      json_data: Dict = None, headers: Dict[str, str] = None,
                      allow_redirects: bool = True, timeout: int = 30,
                      request_type: str = "navigate") -> HTTPResponse:
        
        if not self.current_checkout_session:
            self.start_checkout_session(url)
        
        session_headers = self.update_headers_for_request(url, request_type)
        merged_headers = {**session_headers, **(headers or {})}
        
        fp = self.current_checkout_session.fingerprint
        if fp:
            browser = "chrome"
            if "Firefox" in fp.user_agent:
                browser = "firefox"
            elif "Safari" in fp.user_agent and "Chrome" not in fp.user_agent:
                browser = "safari"
            elif "Edg" in fp.user_agent:
                browser = "edge"
            
            header_manager = HeaderOrderManager(browser)
            merged_headers = header_manager.order_headers(merged_headers)
        
        proxy_dict = None
        if self.current_proxy:
            proxy_dict = {
                "http": self.current_proxy,
                "https": self.current_proxy
            }
        
        if self.use_bypass and self.bypass_wrapper:
            body = None
            if data:
                body = data if isinstance(data, str) else json.dumps(data)
            elif json_data:
                body = json.dumps(json_data)
                merged_headers["Content-Type"] = "application/json"
            
            response = self.bypass_wrapper.make_request(
                url, method, merged_headers, body, self.current_proxy
            )
            if response:
                self._process_response(method, url, response)
                return response
        
        start_time = time.time()
        
        try:
            if method == "GET":
                resp = self.requests_session.get(
                    url, headers=merged_headers,
                    allow_redirects=allow_redirects, timeout=timeout,
                    proxies=proxy_dict
                )
            elif method == "POST":
                resp = self.requests_session.post(
                    url, data=data, json=json_data, headers=merged_headers,
                    allow_redirects=allow_redirects, timeout=timeout,
                    proxies=proxy_dict
                )
            else:
                resp = self.requests_session.request(
                    method, url, data=data, json=json_data, headers=merged_headers,
                    allow_redirects=allow_redirects, timeout=timeout,
                    proxies=proxy_dict
                )
            
            elapsed = time.time() - start_time
            
            redirects = []
            if resp.history:
                redirects = [r.url for r in resp.history]
            
            response = HTTPResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=resp.text,
                cookies=dict(resp.cookies),
                url=resp.url,
                elapsed=elapsed,
                redirects=redirects
            )
            
            self._process_response(method, url, response)
            
            return response
            
        except requests.exceptions.RequestException as e:
            elapsed = time.time() - start_time
            
            if self.current_checkout_session:
                self.current_checkout_session.log_request(method, url, 0, elapsed, str(e))
                self.persistence_manager.save_session(self.current_checkout_session)
            
            return HTTPResponse(
                status_code=0,
                headers={},
                body=str(e),
                cookies={},
                url=url,
                elapsed=elapsed,
                redirects=[]
            )
    
    def _process_response(self, method: str, url: str, response: HTTPResponse):
        if not self.current_checkout_session:
            return
        
        self.current_checkout_session.log_request(
            method, url, response.status_code, response.elapsed
        )
        
        self.current_checkout_session.custom_data["last_url"] = response.url
        
        parsed = urlparse(url)
        for name, value in response.cookies.items():
            cookie = StoredCookie(
                name=name,
                value=value,
                domain=parsed.netloc,
                path="/"
            )
            self.current_checkout_session.add_cookie(cookie)
        
        set_cookie_headers = []
        for header_name, header_value in response.headers.items():
            if header_name.lower() == "set-cookie":
                set_cookie_headers.append(header_value)
        
        for set_cookie in set_cookie_headers:
            cookie = self._parse_set_cookie(set_cookie, parsed.netloc)
            if cookie:
                self.current_checkout_session.add_cookie(cookie)
        
        self.persistence_manager.save_session(self.current_checkout_session)
    
    def _parse_set_cookie(self, set_cookie: str, default_domain: str) -> Optional[StoredCookie]:
        try:
            parts = set_cookie.split(";")
            name_value = parts[0].strip()
            
            if "=" not in name_value:
                return None
            
            name, value = name_value.split("=", 1)
            
            cookie = StoredCookie(
                name=name.strip(),
                value=value.strip(),
                domain=default_domain,
                path="/"
            )
            
            for part in parts[1:]:
                part = part.strip()
                if "=" in part:
                    attr_name, attr_value = part.split("=", 1)
                    attr_name = attr_name.strip().lower()
                    attr_value = attr_value.strip()
                    
                    if attr_name == "domain":
                        cookie.domain = attr_value.lstrip(".")
                    elif attr_name == "path":
                        cookie.path = attr_value
                    elif attr_name == "expires":
                        pass
                    elif attr_name == "max-age":
                        try:
                            max_age = int(attr_value)
                            cookie.expires = time.time() + max_age
                        except ValueError:
                            pass
                    elif attr_name == "samesite":
                        cookie.same_site = attr_value
                else:
                    attr_name = part.lower()
                    if attr_name == "secure":
                        cookie.secure = True
                    elif attr_name == "httponly":
                        cookie.http_only = True
            
            return cookie
        except Exception:
            return None
    
    def set_nonce(self, key: str, value: str):
        if self.current_checkout_session:
            self.current_checkout_session.set_nonce(key, value)
            self.persistence_manager.save_session(self.current_checkout_session)
    
    def get_nonce(self, key: str) -> Optional[str]:
        if self.current_checkout_session:
            return self.current_checkout_session.get_nonce(key)
        return None
    
    def set_csrf_token(self, key: str, value: str):
        if self.current_checkout_session:
            self.current_checkout_session.set_csrf_token(key, value)
            self.persistence_manager.save_session(self.current_checkout_session)
    
    def get_csrf_token(self, key: str) -> Optional[str]:
        if self.current_checkout_session:
            return self.current_checkout_session.get_csrf_token(key)
        return None
    
    def set_cart_data(self, cart_id: str = None, cart_token: str = None):
        if self.current_checkout_session:
            if cart_id:
                self.current_checkout_session.cart_id = cart_id
            if cart_token:
                self.current_checkout_session.cart_token = cart_token
            self.persistence_manager.save_session(self.current_checkout_session)
    
    def set_checkout_token(self, token: str):
        if self.current_checkout_session:
            self.current_checkout_session.checkout_token = token
            self.persistence_manager.save_session(self.current_checkout_session)
    
    def set_payment_data(self, data: Dict[str, Any]):
        if self.current_checkout_session:
            self.current_checkout_session.payment_data.update(data)
            self.persistence_manager.save_session(self.current_checkout_session)
    
    def set_billing_data(self, data: Dict[str, Any]):
        if self.current_checkout_session:
            self.current_checkout_session.billing_data.update(data)
            self.persistence_manager.save_session(self.current_checkout_session)
    
    def set_shipping_data(self, data: Dict[str, Any]):
        if self.current_checkout_session:
            self.current_checkout_session.shipping_data.update(data)
            self.persistence_manager.save_session(self.current_checkout_session)
    
    def set_order_data(self, data: Dict[str, Any]):
        if self.current_checkout_session:
            self.current_checkout_session.order_data.update(data)
            self.persistence_manager.save_session(self.current_checkout_session)
    
    def end_checkout_session(self, status: str = "completed"):
        if self.current_checkout_session:
            self.persistence_manager.end_session(self.current_checkout_session.session_id, status)
            self.current_checkout_session = None
            self.current_proxy = None
            self.requests_session = None
    
    def get_session_stats(self) -> Dict[str, Any]:
        if self.current_checkout_session:
            return self.persistence_manager.get_session_stats(
                self.current_checkout_session.session_id
            )
        return {}
    
    def export_session(self, export_path: str = None) -> str:
        if self.current_checkout_session:
            return self.persistence_manager.export_session(
                self.current_checkout_session.session_id,
                export_path
            )
        raise ValueError("No active session to export")


class AdvancedHTTPClient:
    def __init__(self, session_manager: SessionManager = None, use_bypass: bool = False, 
                 bypass_js_path: str = None):
        self.session_manager = session_manager or SessionManager()
        self.use_bypass = use_bypass
        self.bypass_wrapper = BypassJSWrapper(bypass_js_path) if use_bypass else None
        self.request_history = []
        self.current_session_id = None
        
        self.requests_session = self._create_requests_session()
        
    def _create_requests_session(self) -> requests.Session:
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def create_session(self) -> str:
        session = self.session_manager.create_session()
        self.current_session_id = session["id"]
        return self.current_session_id
    
    def get(self, url: str, headers: Dict[str, str] = None, 
            allow_redirects: bool = True, timeout: int = 30) -> HTTPResponse:
        return self._make_request("GET", url, headers=headers, 
                                  allow_redirects=allow_redirects, timeout=timeout)
    
    def post(self, url: str, data: Any = None, json_data: Dict = None,
             headers: Dict[str, str] = None, allow_redirects: bool = True,
             timeout: int = 30) -> HTTPResponse:
        return self._make_request("POST", url, data=data, json_data=json_data,
                                  headers=headers, allow_redirects=allow_redirects,
                                  timeout=timeout)
    
    def _make_request(self, method: str, url: str, data: Any = None,
                      json_data: Dict = None, headers: Dict[str, str] = None,
                      allow_redirects: bool = True, timeout: int = 30) -> HTTPResponse:
        
        if not self.current_session_id:
            self.create_session()
        
        parsed_url = urlparse(url)
        hostname = parsed_url.netloc
        
        session_headers = self.session_manager.get_session_headers(
            self.current_session_id, hostname
        )
        
        merged_headers = {**session_headers, **(headers or {})}
        
        session = self.session_manager.get_session(self.current_session_id)
        if session:
            fp = session["fingerprint"]
            header_manager = HeaderOrderManager(fp.browser)
            merged_headers = header_manager.order_headers(merged_headers)
        
        if self.use_bypass and self.bypass_wrapper:
            body = None
            if data:
                body = data if isinstance(data, str) else json.dumps(data)
            elif json_data:
                body = json.dumps(json_data)
                merged_headers["Content-Type"] = "application/json"
            
            response = self.bypass_wrapper.make_request(
                url, method, merged_headers, body
            )
            if response:
                self._record_request(method, url, response)
                return response
        
        start_time = time.time()
        
        try:
            if method == "GET":
                resp = self.requests_session.get(
                    url, headers=merged_headers, 
                    allow_redirects=allow_redirects, timeout=timeout
                )
            elif method == "POST":
                resp = self.requests_session.post(
                    url, data=data, json=json_data, headers=merged_headers,
                    allow_redirects=allow_redirects, timeout=timeout
                )
            else:
                resp = self.requests_session.request(
                    method, url, data=data, json=json_data, headers=merged_headers,
                    allow_redirects=allow_redirects, timeout=timeout
                )
            
            elapsed = time.time() - start_time
            
            redirects = []
            if resp.history:
                redirects = [r.url for r in resp.history]
            
            response = HTTPResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=resp.text,
                cookies=dict(resp.cookies),
                url=resp.url,
                elapsed=elapsed,
                redirects=redirects
            )
            
            self._record_request(method, url, response)
            self.session_manager.update_session_activity(self.current_session_id, url)
            
            return response
            
        except requests.exceptions.RequestException as e:
            return HTTPResponse(
                status_code=0,
                headers={},
                body=str(e),
                cookies={},
                url=url,
                elapsed=time.time() - start_time,
                redirects=[]
            )
    
    def _record_request(self, method: str, url: str, response: HTTPResponse):
        self.request_history.append({
            "method": method,
            "url": url,
            "status_code": response.status_code,
            "elapsed": response.elapsed,
            "timestamp": time.time()
        })


class RedirectHandler:
    def __init__(self, max_redirects: int = 10):
        self.max_redirects = max_redirects
        self.redirect_history = []
        
    def handle_redirect(self, response: HTTPResponse, current_url: str) -> Optional[str]:
        if response.status_code not in [301, 302, 303, 307, 308]:
            return None
        
        location = response.headers.get("Location") or response.headers.get("location")
        if not location:
            return None
        
        if len(self.redirect_history) >= self.max_redirects:
            return None
        
        redirect_url = urljoin(current_url, location)
        self.redirect_history.append({
            "from": current_url,
            "to": redirect_url,
            "status": response.status_code
        })
        
        return redirect_url
    
    def is_protection_redirect(self, url: str) -> bool:
        protection_patterns = [
            "challenge",
            "captcha",
            "verify",
            "cloudflare",
            "akamai",
            "ddos",
            "bot",
            "security"
        ]
        
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in protection_patterns)


class ProxyManager:
    def __init__(self, proxies: List[str] = None):
        self.proxies = proxies or []
        self.proxy_stats = {}
        self.current_index = 0
        self.session_proxy_map: Dict[str, str] = {}
        
    def add_proxy(self, proxy: str):
        self.proxies.append(proxy)
        self.proxy_stats[proxy] = {"success": 0, "failure": 0, "last_used": 0}
    
    def get_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        
        proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        self.proxy_stats[proxy]["last_used"] = time.time()
        
        return proxy
    
    def get_proxy_for_session(self, session_id: str) -> Optional[str]:
        if session_id in self.session_proxy_map:
            return self.session_proxy_map[session_id]
        
        proxy = self.get_best_proxy()
        if proxy:
            self.session_proxy_map[session_id] = proxy
        
        return proxy
    
    def get_best_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        
        best_proxy = None
        best_score = -1
        
        for proxy in self.proxies:
            stats = self.proxy_stats.get(proxy, {"success": 0, "failure": 0})
            total = stats["success"] + stats["failure"]
            
            if total == 0:
                return proxy
            
            score = stats["success"] / total
            if score > best_score:
                best_score = score
                best_proxy = proxy
        
        return best_proxy
    
    def report_success(self, proxy: str):
        if proxy in self.proxy_stats:
            self.proxy_stats[proxy]["success"] += 1
    
    def report_failure(self, proxy: str):
        if proxy in self.proxy_stats:
            self.proxy_stats[proxy]["failure"] += 1
    
    def release_session_proxy(self, session_id: str):
        if session_id in self.session_proxy_map:
            del self.session_proxy_map[session_id]
