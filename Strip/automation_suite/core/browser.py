import hashlib
import random
import string
import base64
import time
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class BrowserProfile:
    platform: str
    browser: str
    version: str
    user_agent: str
    viewport: tuple
    webgl_vendor: str
    webgl_renderer: str
    canvas_hash: str
    audio_context: float
    timezone: str
    language: str
    languages: List[str]
    screen_resolution: tuple
    color_depth: int
    device_memory: int
    hardware_concurrency: int
    plugins: List[Dict]
    fonts: List[str]


class BrowserFingerprintGenerator:
    def __init__(self):
        self.fingerprint_cache = {}
        self.session_data = {}
        self.real_fingerprints = self._init_real_fingerprints()
        
    def _init_real_fingerprints(self) -> List[Dict]:
        return [
            {
                "platform": "Windows",
                "browser": "Chrome",
                "version": "120.0.0.0",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "viewport": (1920, 1080),
                "webgl_vendor": "Google Inc. (ANGLE)",
                "webgl_renderer": "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)",
                "timezone": "America/New_York",
                "language": "en-US",
                "languages": ["en-US", "en"],
                "screen_resolution": (1920, 1080),
                "color_depth": 24,
                "device_memory": 8,
                "hardware_concurrency": 8,
                "fonts": ["Arial", "Verdana", "Times New Roman", "Courier New", "Georgia", "Palatino", "Garamond", "Trebuchet MS", "Impact", "Lucida Console", "Tahoma", "Segoe UI"]
            },
            {
                "platform": "macOS",
                "browser": "Chrome",
                "version": "120.0.0.0",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "viewport": (1440, 900),
                "webgl_vendor": "Google Inc. (Apple)",
                "webgl_renderer": "ANGLE (Apple, Apple M1, OpenGL 4.1)",
                "timezone": "America/Los_Angeles",
                "language": "en-US",
                "languages": ["en-US", "en"],
                "screen_resolution": (2560, 1600),
                "color_depth": 30,
                "device_memory": 16,
                "hardware_concurrency": 8,
                "fonts": ["Arial", "Helvetica", "Times New Roman", "Courier New", "Georgia", "Palatino", "Trebuchet MS", "Lucida Grande", "Monaco", "Menlo"]
            },
            {
                "platform": "Windows",
                "browser": "Firefox",
                "version": "121.0",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
                "viewport": (1920, 1080),
                "webgl_vendor": "Intel Inc.",
                "webgl_renderer": "Intel(R) UHD Graphics 620",
                "timezone": "Europe/London",
                "language": "en-GB",
                "languages": ["en-GB", "en"],
                "screen_resolution": (1920, 1080),
                "color_depth": 24,
                "device_memory": 8,
                "hardware_concurrency": 4,
                "fonts": ["Arial", "Verdana", "Times New Roman", "Courier New", "Georgia", "Trebuchet MS", "Impact", "Lucida Console", "Tahoma"]
            },
            {
                "platform": "Windows",
                "browser": "Edge",
                "version": "120.0.0.0",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
                "viewport": (1920, 1080),
                "webgl_vendor": "Google Inc. (ANGLE)",
                "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 Direct3D11 vs_5_0 ps_5_0, D3D11)",
                "timezone": "America/Chicago",
                "language": "en-US",
                "languages": ["en-US", "en"],
                "screen_resolution": (2560, 1440),
                "color_depth": 24,
                "device_memory": 16,
                "hardware_concurrency": 12,
                "fonts": ["Arial", "Verdana", "Times New Roman", "Courier New", "Georgia", "Palatino", "Trebuchet MS", "Impact", "Lucida Console", "Tahoma", "Segoe UI", "Calibri"]
            },
            {
                "platform": "macOS",
                "browser": "Safari",
                "version": "17.0",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                "viewport": (1440, 900),
                "webgl_vendor": "Apple Inc.",
                "webgl_renderer": "Apple M1 Pro",
                "timezone": "America/Los_Angeles",
                "language": "en-US",
                "languages": ["en-US", "en"],
                "screen_resolution": (3024, 1964),
                "color_depth": 30,
                "device_memory": 32,
                "hardware_concurrency": 10,
                "fonts": ["Arial", "Helvetica", "Times New Roman", "Courier New", "Georgia", "Palatino", "Trebuchet MS", "Lucida Grande", "Monaco", "Menlo", "SF Pro"]
            }
        ]
    
    def _generate_canvas_hash(self, browser: str) -> str:
        seed = f"{browser}_{random.random()}"
        return hashlib.sha256(seed.encode()).hexdigest()[:32]
    
    def _generate_audio_context(self) -> float:
        return random.uniform(124.0, 124.1)
    
    def _generate_plugins(self, browser: str) -> List[Dict]:
        chrome_plugins = [
            {"name": "Chrome PDF Plugin", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
            {"name": "Chrome PDF Viewer", "filename": "mhjfbmdgcfjbbpaeojofohoefgiehjai", "description": ""},
            {"name": "Native Client", "filename": "internal-nacl-plugin", "description": ""}
        ]
        firefox_plugins = []
        safari_plugins = []
        
        if browser in ["Chrome", "Edge"]:
            return chrome_plugins
        elif browser == "Firefox":
            return firefox_plugins
        else:
            return safari_plugins
    
    def generate_fingerprint(self, session_id: Optional[str] = None) -> BrowserProfile:
        if session_id and session_id in self.fingerprint_cache:
            return self.fingerprint_cache[session_id]
        
        base = random.choice(self.real_fingerprints)
        
        profile = BrowserProfile(
            platform=base["platform"],
            browser=base["browser"],
            version=base["version"],
            user_agent=base["user_agent"],
            viewport=base["viewport"],
            webgl_vendor=base["webgl_vendor"],
            webgl_renderer=base["webgl_renderer"],
            canvas_hash=self._generate_canvas_hash(base["browser"]),
            audio_context=self._generate_audio_context(),
            timezone=base["timezone"],
            language=base["language"],
            languages=base["languages"],
            screen_resolution=base["screen_resolution"],
            color_depth=base["color_depth"],
            device_memory=base["device_memory"],
            hardware_concurrency=base["hardware_concurrency"],
            plugins=self._generate_plugins(base["browser"]),
            fonts=base["fonts"]
        )
        
        if session_id:
            self.fingerprint_cache[session_id] = profile
        
        return profile


class CookieGenerator:
    def __init__(self):
        self.cookie_templates = {}
        
    def _random_string(self, length: int, chars: str = None) -> str:
        if chars is None:
            chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    def _random_hex(self, length: int) -> str:
        return ''.join(random.choice('0123456789abcdef') for _ in range(length))
    
    def _random_base64(self, length: int) -> str:
        raw = bytes([random.randint(0, 255) for _ in range(length)])
        return base64.b64encode(raw).decode().replace('=', '')[:length]
    
    def _generate_ga_client_id(self) -> str:
        return f"{random.randint(100000000, 2000000000)}.{random.randint(100000000, 2000000000)}"
    
    def generate_cloudflare_cookies(self, hostname: str, session_id: str) -> Dict[str, str]:
        timestamp = int(time.time())
        
        cf_clearance_challenge = self._random_base64(43)
        cf_clearance_hmac = hashlib.sha256(f"{hostname}:{session_id}:{cf_clearance_challenge}:{timestamp}".encode()).hexdigest()[:8]
        
        return {
            "cf_clearance": f"{cf_clearance_challenge}.{session_id[:8]}-{timestamp}-{cf_clearance_hmac}",
            "__cf_bm": self._random_base64(43) + "=",
            "_cfuvid": f"{self._random_hex(32)}.{timestamp}"
        }
    
    def generate_akamai_cookies(self) -> Dict[str, str]:
        timestamp = int(time.time() * 1000)
        
        return {
            "ak_bmsc": self._random_base64(88),
            "_abck": f"{self._random_base64(144)}~0~{self._random_base64(64)}~0~-1",
            "bm_mi": f"{self._random_hex(32)}~{self._random_hex(16)}",
            "bm_sv": f"{self._random_base64(200)}~{self._random_hex(8)}~{timestamp}"
        }
    
    def generate_analytics_cookies(self) -> Dict[str, str]:
        timestamp = int(time.time() * 1000)
        base_time = timestamp - random.randint(0, 2592000000)
        ga_suffix = self._random_string(10, string.ascii_uppercase + string.digits)
        
        return {
            "_ga": f"GA1.1.{self._generate_ga_client_id()}.{int(base_time/1000)}",
            f"_ga_{ga_suffix}": f"GS1.1.{timestamp}.1.1.{timestamp + random.randint(0, 3600000)}.0",
            "_gid": f"GA1.2.{self._generate_ga_client_id()}.{int(timestamp/86400000)}",
            "_fbp": f"fb.1.{timestamp}.{random.randint(100000000, 2000000000)}",
            "_fbc": f"fb.1.{timestamp}.{self._random_string(16)}"
        }
    
    def generate_consent_cookies(self) -> Dict[str, str]:
        purposes = ''.join(['1' if random.random() > 0.3 else '0' for _ in range(24)])
        consent_string = base64.b64encode(purposes.encode()).decode().replace('=', '')
        eu_consent = f"CP{self._random_string(20, string.ascii_letters + string.digits + '-_')}."
        
        return {
            "gdpr_consent": f"1~{consent_string}",
            "euconsent": eu_consent,
            "cookieconsent_status": "allow"
        }
    
    def generate_session_cookies(self) -> Dict[str, str]:
        return {
            "sessionid": self._random_hex(32),
            "csrftoken": self._random_base64(64),
            "cart_token": self._random_hex(32),
            "checkout_token": self._random_hex(32)
        }
    
    def generate_all_cookies(self, hostname: str, session_id: str) -> str:
        all_cookies = {}
        all_cookies.update(self.generate_cloudflare_cookies(hostname, session_id))
        all_cookies.update(self.generate_akamai_cookies())
        all_cookies.update(self.generate_analytics_cookies())
        all_cookies.update(self.generate_consent_cookies())
        all_cookies.update(self.generate_session_cookies())
        
        return "; ".join([f"{k}={v}" for k, v in all_cookies.items()])


class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.fingerprint_generator = BrowserFingerprintGenerator()
        self.cookie_generator = CookieGenerator()
        
    def create_session(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        if session_id is None:
            session_id = self._generate_session_id()
        
        fingerprint = self.fingerprint_generator.generate_fingerprint(session_id)
        
        session = {
            "id": session_id,
            "fingerprint": fingerprint,
            "created_at": time.time(),
            "last_activity": time.time(),
            "request_count": 0,
            "cookies": {},
            "history": []
        }
        
        self.sessions[session_id] = session
        return session
    
    def _generate_session_id(self) -> str:
        return hashlib.sha256(f"{time.time()}_{random.random()}".encode()).hexdigest()[:16]
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.sessions.get(session_id)
    
    def update_session_activity(self, session_id: str, url: str = None):
        if session_id in self.sessions:
            self.sessions[session_id]["last_activity"] = time.time()
            self.sessions[session_id]["request_count"] += 1
            if url:
                self.sessions[session_id]["history"].append({
                    "url": url,
                    "timestamp": time.time()
                })
    
    def get_session_headers(self, session_id: str, hostname: str) -> Dict[str, str]:
        session = self.get_session(session_id)
        if not session:
            return {}
        
        fp = session["fingerprint"]
        
        headers = {
            "User-Agent": fp.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": ",".join(fp.languages) + ";q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        }
        
        if fp.browser == "Chrome" or fp.browser == "Edge":
            headers["sec-ch-ua"] = f'"Not_A Brand";v="8", "Chromium";v="{fp.version.split(".")[0]}", "Google Chrome";v="{fp.version.split(".")[0]}"'
            headers["sec-ch-ua-mobile"] = "?0"
            headers["sec-ch-ua-platform"] = f'"{fp.platform}"'
        
        cookies = self.cookie_generator.generate_all_cookies(hostname, session_id)
        if cookies:
            headers["Cookie"] = cookies
        
        return headers
    
    def destroy_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]


class WebGLFingerprint:
    def __init__(self, profile: BrowserProfile):
        self.profile = profile
        
    def generate(self) -> Dict[str, Any]:
        return {
            "vendor": self.profile.webgl_vendor,
            "renderer": self.profile.webgl_renderer,
            "version": "WebGL 2.0 (OpenGL ES 3.0 Chromium)",
            "shading_language_version": "WebGL GLSL ES 3.00 (OpenGL ES GLSL ES 3.0 Chromium)",
            "extensions": self._get_extensions(),
            "parameters": self._get_parameters()
        }
    
    def _get_extensions(self) -> List[str]:
        return [
            "ANGLE_instanced_arrays",
            "EXT_blend_minmax",
            "EXT_color_buffer_half_float",
            "EXT_disjoint_timer_query",
            "EXT_float_blend",
            "EXT_frag_depth",
            "EXT_shader_texture_lod",
            "EXT_sRGB",
            "EXT_texture_compression_bptc",
            "EXT_texture_compression_rgtc",
            "EXT_texture_filter_anisotropic",
            "WEBGL_color_buffer_float",
            "WEBGL_compressed_texture_s3tc",
            "WEBGL_debug_renderer_info",
            "WEBGL_debug_shaders",
            "WEBGL_depth_texture",
            "WEBGL_draw_buffers",
            "WEBGL_lose_context",
            "OES_element_index_uint",
            "OES_standard_derivatives",
            "OES_texture_float",
            "OES_texture_float_linear",
            "OES_texture_half_float",
            "OES_texture_half_float_linear",
            "OES_vertex_array_object"
        ]
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "MAX_TEXTURE_SIZE": 16384,
            "MAX_CUBE_MAP_TEXTURE_SIZE": 16384,
            "MAX_RENDERBUFFER_SIZE": 16384,
            "MAX_VIEWPORT_DIMS": [32767, 32767],
            "ALIASED_LINE_WIDTH_RANGE": [1, 1],
            "ALIASED_POINT_SIZE_RANGE": [1, 1024],
            "MAX_VERTEX_ATTRIBS": 16,
            "MAX_VERTEX_UNIFORM_VECTORS": 4096,
            "MAX_VARYING_VECTORS": 30,
            "MAX_FRAGMENT_UNIFORM_VECTORS": 1024,
            "MAX_TEXTURE_IMAGE_UNITS": 16,
            "MAX_VERTEX_TEXTURE_IMAGE_UNITS": 16,
            "MAX_COMBINED_TEXTURE_IMAGE_UNITS": 32
        }


class CanvasFingerprint:
    def __init__(self, profile: BrowserProfile):
        self.profile = profile
        
    def generate(self) -> Dict[str, Any]:
        return {
            "hash": self.profile.canvas_hash,
            "text": "Browser Canvas Fingerprint Test",
            "font": "20px Arial",
            "fill_style": "#FF0000",
            "global_alpha": 1.0,
            "global_composite_operation": "source-over",
            "line_cap": "butt",
            "line_join": "miter",
            "line_width": 1,
            "miter_limit": 10,
            "shadow_blur": 0,
            "shadow_color": "rgba(0, 0, 0, 0)",
            "shadow_offset_x": 0,
            "shadow_offset_y": 0,
            "stroke_style": "#000000",
            "text_align": "start",
            "text_baseline": "alphabetic"
        }


class AudioContextFingerprint:
    def __init__(self, profile: BrowserProfile):
        self.profile = profile
        
    def generate(self) -> Dict[str, Any]:
        return {
            "sample_rate": 48000,
            "channel_count": 2,
            "max_channel_count": 32,
            "state": "running",
            "base_latency": 0.005333333333333333,
            "output_latency": 0.01,
            "fingerprint_value": self.profile.audio_context
        }
