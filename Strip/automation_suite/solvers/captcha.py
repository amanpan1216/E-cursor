import re
import json
import time
import random
import hashlib
import base64
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, urljoin, parse_qs
from dataclasses import dataclass

from ..core.http_client import AdvancedHTTPClient, HTTPResponse
from ..core.behavior import HumanBehaviorSimulator


@dataclass
class CaptchaChallenge:
    type: str
    site_key: str
    url: str
    data_s: Optional[str] = None
    enterprise: bool = False
    invisible: bool = False


@dataclass
class CaptchaSolution:
    token: str
    type: str
    solve_time: float
    method: str


class CaptchaDetector:
    def __init__(self):
        pass
        
    def detect(self, html: str, url: str) -> List[CaptchaChallenge]:
        challenges = []
        
        recaptcha = self._detect_recaptcha(html, url)
        if recaptcha:
            challenges.append(recaptcha)
        
        hcaptcha = self._detect_hcaptcha(html, url)
        if hcaptcha:
            challenges.append(hcaptcha)
        
        turnstile = self._detect_turnstile(html, url)
        if turnstile:
            challenges.append(turnstile)
        
        return challenges
    
    def _detect_recaptcha(self, html: str, url: str) -> Optional[CaptchaChallenge]:
        patterns = [
            r'data-sitekey=["\']([a-zA-Z0-9_-]{40})["\']',
            r'grecaptcha\.render\s*\([^,]+,\s*\{\s*["\']sitekey["\']\s*:\s*["\']([a-zA-Z0-9_-]{40})["\']',
            r'recaptcha/api\.js\?.*?render=([a-zA-Z0-9_-]{40})',
            r'"sitekey"\s*:\s*"([a-zA-Z0-9_-]{40})"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                site_key = match.group(1)
                
                enterprise = 'recaptcha/enterprise' in html or 'enterprise.js' in html
                invisible = 'invisible' in html.lower() or 'size="invisible"' in html
                
                data_s = None
                data_s_match = re.search(r'data-s=["\']([^"\']+)["\']', html)
                if data_s_match:
                    data_s = data_s_match.group(1)
                
                return CaptchaChallenge(
                    type="recaptcha_v2" if not enterprise else "recaptcha_enterprise",
                    site_key=site_key,
                    url=url,
                    data_s=data_s,
                    enterprise=enterprise,
                    invisible=invisible
                )
        
        v3_match = re.search(r'grecaptcha\.execute\s*\(\s*["\']([a-zA-Z0-9_-]{40})["\']', html)
        if v3_match:
            return CaptchaChallenge(
                type="recaptcha_v3",
                site_key=v3_match.group(1),
                url=url,
                invisible=True
            )
        
        return None
    
    def _detect_hcaptcha(self, html: str, url: str) -> Optional[CaptchaChallenge]:
        patterns = [
            r'data-sitekey=["\']([a-f0-9-]{36})["\']',
            r'hcaptcha\.render\s*\([^,]+,\s*\{\s*["\']sitekey["\']\s*:\s*["\']([a-f0-9-]{36})["\']',
            r'"sitekey"\s*:\s*"([a-f0-9-]{36})"'
        ]
        
        if 'hcaptcha' not in html.lower():
            return None
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                site_key = match.group(1)
                
                invisible = 'size="invisible"' in html or 'data-size="invisible"' in html
                
                return CaptchaChallenge(
                    type="hcaptcha",
                    site_key=site_key,
                    url=url,
                    invisible=invisible
                )
        
        return None
    
    def _detect_turnstile(self, html: str, url: str) -> Optional[CaptchaChallenge]:
        patterns = [
            r'data-sitekey=["\']([a-zA-Z0-9_-]+)["\']',
            r'turnstile\.render\s*\([^,]+,\s*\{\s*["\']sitekey["\']\s*:\s*["\']([a-zA-Z0-9_-]+)["\']'
        ]
        
        if 'turnstile' not in html.lower() and 'challenges.cloudflare.com' not in html:
            return None
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return CaptchaChallenge(
                    type="turnstile",
                    site_key=match.group(1),
                    url=url
                )
        
        return None


class CaptchaSolverBase:
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.behavior = HumanBehaviorSimulator()
        
    def solve(self, challenge: CaptchaChallenge) -> Optional[CaptchaSolution]:
        raise NotImplementedError


class TwoCaptchaSolver(CaptchaSolverBase):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.api_base = "https://2captcha.com"
        self.http_client = None
        
    def set_http_client(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        
    def solve(self, challenge: CaptchaChallenge) -> Optional[CaptchaSolution]:
        if not self.http_client or not self.api_key:
            return None
        
        start_time = time.time()
        
        task_id = self._create_task(challenge)
        if not task_id:
            return None
        
        token = self._get_result(task_id)
        if not token:
            return None
        
        solve_time = time.time() - start_time
        
        return CaptchaSolution(
            token=token,
            type=challenge.type,
            solve_time=solve_time,
            method="2captcha"
        )
    
    def _create_task(self, challenge: CaptchaChallenge) -> Optional[str]:
        params = {
            "key": self.api_key,
            "method": self._get_method(challenge.type),
            "pageurl": challenge.url,
            "json": "1"
        }
        
        if challenge.type in ["recaptcha_v2", "recaptcha_v3", "recaptcha_enterprise"]:
            params["googlekey"] = challenge.site_key
            if challenge.invisible:
                params["invisible"] = "1"
            if challenge.data_s:
                params["data-s"] = challenge.data_s
            if challenge.enterprise:
                params["enterprise"] = "1"
            if challenge.type == "recaptcha_v3":
                params["version"] = "v3"
                params["action"] = "verify"
                params["min_score"] = "0.3"
        
        elif challenge.type == "hcaptcha":
            params["sitekey"] = challenge.site_key
            if challenge.invisible:
                params["invisible"] = "1"
        
        elif challenge.type == "turnstile":
            params["sitekey"] = challenge.site_key
        
        url = f"{self.api_base}/in.php"
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        
        response = self.http_client.get(f"{url}?{query_string}")
        
        if response.status_code == 200:
            try:
                result = json.loads(response.body)
                if result.get("status") == 1:
                    return result.get("request")
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _get_result(self, task_id: str, max_attempts: int = 60) -> Optional[str]:
        params = {
            "key": self.api_key,
            "action": "get",
            "id": task_id,
            "json": "1"
        }
        
        url = f"{self.api_base}/res.php"
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        
        for _ in range(max_attempts):
            time.sleep(5)
            
            response = self.http_client.get(f"{url}?{query_string}")
            
            if response.status_code == 200:
                try:
                    result = json.loads(response.body)
                    if result.get("status") == 1:
                        return result.get("request")
                    elif result.get("request") != "CAPCHA_NOT_READY":
                        return None
                except json.JSONDecodeError:
                    pass
        
        return None
    
    def _get_method(self, captcha_type: str) -> str:
        methods = {
            "recaptcha_v2": "userrecaptcha",
            "recaptcha_v3": "userrecaptcha",
            "recaptcha_enterprise": "userrecaptcha",
            "hcaptcha": "hcaptcha",
            "turnstile": "turnstile"
        }
        return methods.get(captcha_type, "userrecaptcha")


class AntiCaptchaSolver(CaptchaSolverBase):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.api_base = "https://api.anti-captcha.com"
        self.http_client = None
        
    def set_http_client(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        
    def solve(self, challenge: CaptchaChallenge) -> Optional[CaptchaSolution]:
        if not self.http_client or not self.api_key:
            return None
        
        start_time = time.time()
        
        task_id = self._create_task(challenge)
        if not task_id:
            return None
        
        token = self._get_result(task_id)
        if not token:
            return None
        
        solve_time = time.time() - start_time
        
        return CaptchaSolution(
            token=token,
            type=challenge.type,
            solve_time=solve_time,
            method="anticaptcha"
        )
    
    def _create_task(self, challenge: CaptchaChallenge) -> Optional[int]:
        task = self._build_task(challenge)
        
        payload = {
            "clientKey": self.api_key,
            "task": task
        }
        
        headers = {"Content-Type": "application/json"}
        
        response = self.http_client.post(
            f"{self.api_base}/createTask",
            json_data=payload,
            headers=headers
        )
        
        if response.status_code == 200:
            try:
                result = json.loads(response.body)
                if result.get("errorId") == 0:
                    return result.get("taskId")
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _build_task(self, challenge: CaptchaChallenge) -> Dict[str, Any]:
        if challenge.type in ["recaptcha_v2", "recaptcha_enterprise"]:
            task = {
                "type": "RecaptchaV2TaskProxyless" if not challenge.enterprise else "RecaptchaV2EnterpriseTaskProxyless",
                "websiteURL": challenge.url,
                "websiteKey": challenge.site_key
            }
            if challenge.invisible:
                task["isInvisible"] = True
            if challenge.data_s:
                task["recaptchaDataSValue"] = challenge.data_s
            return task
        
        elif challenge.type == "recaptcha_v3":
            return {
                "type": "RecaptchaV3TaskProxyless",
                "websiteURL": challenge.url,
                "websiteKey": challenge.site_key,
                "minScore": 0.3,
                "pageAction": "verify"
            }
        
        elif challenge.type == "hcaptcha":
            task = {
                "type": "HCaptchaTaskProxyless",
                "websiteURL": challenge.url,
                "websiteKey": challenge.site_key
            }
            if challenge.invisible:
                task["isInvisible"] = True
            return task
        
        elif challenge.type == "turnstile":
            return {
                "type": "TurnstileTaskProxyless",
                "websiteURL": challenge.url,
                "websiteKey": challenge.site_key
            }
        
        return {}
    
    def _get_result(self, task_id: int, max_attempts: int = 60) -> Optional[str]:
        payload = {
            "clientKey": self.api_key,
            "taskId": task_id
        }
        
        headers = {"Content-Type": "application/json"}
        
        for _ in range(max_attempts):
            time.sleep(5)
            
            response = self.http_client.post(
                f"{self.api_base}/getTaskResult",
                json_data=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                try:
                    result = json.loads(response.body)
                    if result.get("errorId") == 0:
                        if result.get("status") == "ready":
                            solution = result.get("solution", {})
                            return solution.get("gRecaptchaResponse") or solution.get("token")
                except json.JSONDecodeError:
                    pass
        
        return None


class CapMonsterSolver(CaptchaSolverBase):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.api_base = "https://api.capmonster.cloud"
        self.http_client = None
        
    def set_http_client(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        
    def solve(self, challenge: CaptchaChallenge) -> Optional[CaptchaSolution]:
        if not self.http_client or not self.api_key:
            return None
        
        start_time = time.time()
        
        task_id = self._create_task(challenge)
        if not task_id:
            return None
        
        token = self._get_result(task_id)
        if not token:
            return None
        
        solve_time = time.time() - start_time
        
        return CaptchaSolution(
            token=token,
            type=challenge.type,
            solve_time=solve_time,
            method="capmonster"
        )
    
    def _create_task(self, challenge: CaptchaChallenge) -> Optional[int]:
        task = self._build_task(challenge)
        
        payload = {
            "clientKey": self.api_key,
            "task": task
        }
        
        headers = {"Content-Type": "application/json"}
        
        response = self.http_client.post(
            f"{self.api_base}/createTask",
            json_data=payload,
            headers=headers
        )
        
        if response.status_code == 200:
            try:
                result = json.loads(response.body)
                if result.get("errorId") == 0:
                    return result.get("taskId")
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _build_task(self, challenge: CaptchaChallenge) -> Dict[str, Any]:
        if challenge.type in ["recaptcha_v2", "recaptcha_enterprise"]:
            return {
                "type": "NoCaptchaTaskProxyless",
                "websiteURL": challenge.url,
                "websiteKey": challenge.site_key
            }
        
        elif challenge.type == "recaptcha_v3":
            return {
                "type": "RecaptchaV3TaskProxyless",
                "websiteURL": challenge.url,
                "websiteKey": challenge.site_key,
                "minScore": 0.3
            }
        
        elif challenge.type == "hcaptcha":
            return {
                "type": "HCaptchaTaskProxyless",
                "websiteURL": challenge.url,
                "websiteKey": challenge.site_key
            }
        
        elif challenge.type == "turnstile":
            return {
                "type": "TurnstileTaskProxyless",
                "websiteURL": challenge.url,
                "websiteKey": challenge.site_key
            }
        
        return {}
    
    def _get_result(self, task_id: int, max_attempts: int = 60) -> Optional[str]:
        payload = {
            "clientKey": self.api_key,
            "taskId": task_id
        }
        
        headers = {"Content-Type": "application/json"}
        
        for _ in range(max_attempts):
            time.sleep(3)
            
            response = self.http_client.post(
                f"{self.api_base}/getTaskResult",
                json_data=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                try:
                    result = json.loads(response.body)
                    if result.get("errorId") == 0:
                        if result.get("status") == "ready":
                            solution = result.get("solution", {})
                            return solution.get("gRecaptchaResponse") or solution.get("token")
                except json.JSONDecodeError:
                    pass
        
        return None


class CaptchaSolverManager:
    def __init__(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        self.detector = CaptchaDetector()
        self.solvers = {}
        self.preferred_solver = None
        
    def add_solver(self, name: str, solver: CaptchaSolverBase):
        solver.set_http_client(self.http_client)
        self.solvers[name] = solver
        if not self.preferred_solver:
            self.preferred_solver = name
    
    def set_preferred_solver(self, name: str):
        if name in self.solvers:
            self.preferred_solver = name
    
    def detect_captcha(self, html: str, url: str) -> List[CaptchaChallenge]:
        return self.detector.detect(html, url)
    
    def solve_captcha(self, challenge: CaptchaChallenge, solver_name: str = None) -> Optional[CaptchaSolution]:
        solver_name = solver_name or self.preferred_solver
        
        if not solver_name or solver_name not in self.solvers:
            return None
        
        solver = self.solvers[solver_name]
        return solver.solve(challenge)
    
    def solve_all(self, challenges: List[CaptchaChallenge]) -> Dict[str, CaptchaSolution]:
        solutions = {}
        
        for challenge in challenges:
            solution = self.solve_captcha(challenge)
            if solution:
                solutions[challenge.type] = solution
        
        return solutions
