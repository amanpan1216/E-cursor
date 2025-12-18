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

from .browser import SessionManager, BrowserProfile


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
        
        if self.browser == "firefox":
            return firefox_ciphers
        return chrome_ciphers
    
    def _get_extensions(self) -> List[str]:
        return [
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
        
        if self.browser == "firefox":
            return firefox_settings
        return chrome_settings
    
    def _get_window_update(self) -> int:
        if self.browser == "firefox":
            return 12517377
        return 15663105
    
    def _get_priority(self) -> Dict[str, Any]:
        return {
            "exclusive": True,
            "stream_dep": 0,
            "weight": 256
        }


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
        
        if self.browser == "firefox":
            return firefox_order
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
