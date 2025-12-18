import re
import json
import time
import random
import hashlib
import base64
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, urljoin, parse_qs, urlencode
from dataclasses import dataclass
from bs4 import BeautifulSoup

from ..core.http_client import AdvancedHTTPClient, HTTPResponse
from ..core.behavior import HumanBehaviorSimulator


@dataclass
class ThreeDSChallenge:
    version: str
    acs_url: str
    creq: Optional[str] = None
    pareq: Optional[str] = None
    md: Optional[str] = None
    term_url: Optional[str] = None
    transaction_id: Optional[str] = None
    method_url: Optional[str] = None
    method_data: Optional[str] = None


@dataclass
class ThreeDSResult:
    success: bool
    version: str
    cres: Optional[str] = None
    pares: Optional[str] = None
    trans_status: Optional[str] = None
    eci: Optional[str] = None
    cavv: Optional[str] = None
    error: Optional[str] = None


class ThreeDSDetector:
    def __init__(self):
        pass
        
    def detect(self, response_data: Dict[str, Any]) -> Optional[ThreeDSChallenge]:
        if "next_action" in response_data:
            next_action = response_data["next_action"]
            
            if next_action.get("type") == "redirect_to_url":
                redirect_url = next_action.get("redirect_to_url", {}).get("url", "")
                return ThreeDSChallenge(
                    version="redirect",
                    acs_url=redirect_url
                )
            
            elif next_action.get("type") == "use_stripe_sdk":
                sdk_data = next_action.get("use_stripe_sdk", {})
                
                if "three_d_secure_2_source" in sdk_data:
                    return ThreeDSChallenge(
                        version="2.0",
                        acs_url=sdk_data.get("three_d_secure_2_source", ""),
                        transaction_id=sdk_data.get("three_ds_server_trans_id", "")
                    )
        
        if "acsUrl" in response_data or "acs_url" in response_data:
            acs_url = response_data.get("acsUrl") or response_data.get("acs_url", "")
            
            if "creq" in response_data or "CReq" in response_data:
                return ThreeDSChallenge(
                    version="2.0",
                    acs_url=acs_url,
                    creq=response_data.get("creq") or response_data.get("CReq"),
                    transaction_id=response_data.get("threeDSServerTransID")
                )
            
            elif "pareq" in response_data or "PaReq" in response_data:
                return ThreeDSChallenge(
                    version="1.0",
                    acs_url=acs_url,
                    pareq=response_data.get("pareq") or response_data.get("PaReq"),
                    md=response_data.get("md") or response_data.get("MD"),
                    term_url=response_data.get("termUrl") or response_data.get("TermUrl")
                )
        
        if "threeDSecureLookupData" in response_data:
            lookup_data = response_data["threeDSecureLookupData"]
            
            if lookup_data.get("acsUrl"):
                return ThreeDSChallenge(
                    version="1.0" if lookup_data.get("paReq") else "2.0",
                    acs_url=lookup_data["acsUrl"],
                    pareq=lookup_data.get("paReq"),
                    md=lookup_data.get("md"),
                    term_url=lookup_data.get("termUrl"),
                    creq=lookup_data.get("creq")
                )
        
        return None
    
    def detect_from_html(self, html: str) -> Optional[ThreeDSChallenge]:
        soup = BeautifulSoup(html, 'html.parser')
        
        form = soup.find('form', {'name': re.compile(r'3ds|threeds|acs', re.IGNORECASE)})
        if not form:
            form = soup.find('form', action=re.compile(r'acs|3ds|authenticate', re.IGNORECASE))
        
        if form:
            action = form.get('action', '')
            
            creq_input = form.find('input', {'name': re.compile(r'creq', re.IGNORECASE)})
            if creq_input:
                return ThreeDSChallenge(
                    version="2.0",
                    acs_url=action,
                    creq=creq_input.get('value', ''),
                    transaction_id=self._extract_input_value(form, r'threeDSSessionData|transId')
                )
            
            pareq_input = form.find('input', {'name': re.compile(r'pareq', re.IGNORECASE)})
            if pareq_input:
                return ThreeDSChallenge(
                    version="1.0",
                    acs_url=action,
                    pareq=pareq_input.get('value', ''),
                    md=self._extract_input_value(form, r'md'),
                    term_url=self._extract_input_value(form, r'termurl')
                )
        
        return None
    
    def _extract_input_value(self, form, pattern: str) -> Optional[str]:
        inp = form.find('input', {'name': re.compile(pattern, re.IGNORECASE)})
        return inp.get('value', '') if inp else None


class ThreeDSv1Handler:
    def __init__(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        self.behavior = HumanBehaviorSimulator()
        
    def handle_challenge(self, challenge: ThreeDSChallenge) -> ThreeDSResult:
        result = ThreeDSResult(
            success=False,
            version="1.0"
        )
        
        if not challenge.acs_url or not challenge.pareq:
            result.error = "Missing ACS URL or PAReq"
            return result
        
        self.behavior.human_delay(action_type="page_load")
        
        data = {
            "PaReq": challenge.pareq,
            "TermUrl": challenge.term_url or "",
            "MD": challenge.md or ""
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        
        response = self.http_client.post(challenge.acs_url, data=data, headers=headers)
        
        if response.status_code != 200:
            result.error = f"ACS request failed: HTTP {response.status_code}"
            return result
        
        pares = self._extract_pares(response.body)
        
        if pares:
            result.success = True
            result.pares = pares
            result.trans_status = "Y"
        else:
            if self._is_challenge_page(response.body):
                result.error = "Manual challenge required"
            else:
                result.error = "Could not extract PARes"
        
        return result
    
    def _extract_pares(self, html: str) -> Optional[str]:
        patterns = [
            r'name=["\']PaRes["\']\s+value=["\']([^"\']+)["\']',
            r'name=["\']pares["\']\s+value=["\']([^"\']+)["\']',
            r'value=["\']([^"\']+)["\']\s+name=["\']PaRes["\']',
            r'"pares"\s*:\s*"([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)
        
        soup = BeautifulSoup(html, 'html.parser')
        pares_input = soup.find('input', {'name': re.compile(r'pares', re.IGNORECASE)})
        if pares_input:
            return pares_input.get('value', '')
        
        return None
    
    def _is_challenge_page(self, html: str) -> bool:
        challenge_indicators = [
            'password',
            'otp',
            'verification',
            'authenticate',
            'confirm',
            'enter code',
            'security code'
        ]
        
        html_lower = html.lower()
        return any(indicator in html_lower for indicator in challenge_indicators)


class ThreeDSv2Handler:
    def __init__(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        self.behavior = HumanBehaviorSimulator()
        
    def handle_challenge(self, challenge: ThreeDSChallenge) -> ThreeDSResult:
        result = ThreeDSResult(
            success=False,
            version="2.0"
        )
        
        if not challenge.acs_url:
            result.error = "Missing ACS URL"
            return result
        
        self.behavior.human_delay(action_type="page_load")
        
        if challenge.creq:
            return self._handle_creq_challenge(challenge)
        elif challenge.method_url:
            return self._handle_method_challenge(challenge)
        else:
            result.error = "Unknown 3DS2 challenge type"
            return result
    
    def _handle_creq_challenge(self, challenge: ThreeDSChallenge) -> ThreeDSResult:
        result = ThreeDSResult(
            success=False,
            version="2.0"
        )
        
        data = {
            "creq": challenge.creq
        }
        
        if challenge.transaction_id:
            data["threeDSSessionData"] = challenge.transaction_id
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        
        response = self.http_client.post(challenge.acs_url, data=data, headers=headers)
        
        if response.status_code != 200:
            result.error = f"ACS request failed: HTTP {response.status_code}"
            return result
        
        cres = self._extract_cres(response.body)
        
        if cres:
            result.success = True
            result.cres = cres
            
            decoded_cres = self._decode_cres(cres)
            if decoded_cres:
                result.trans_status = decoded_cres.get("transStatus", "")
                result.eci = decoded_cres.get("eci", "")
        else:
            if self._is_challenge_page(response.body):
                result.error = "Manual challenge required"
            else:
                result.error = "Could not extract CRes"
        
        return result
    
    def _handle_method_challenge(self, challenge: ThreeDSChallenge) -> ThreeDSResult:
        result = ThreeDSResult(
            success=False,
            version="2.0"
        )
        
        data = {}
        if challenge.method_data:
            data["threeDSMethodData"] = challenge.method_data
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        response = self.http_client.post(challenge.method_url, data=data, headers=headers)
        
        if response.status_code in [200, 204]:
            result.success = True
            result.trans_status = "Y"
        else:
            result.error = f"Method request failed: HTTP {response.status_code}"
        
        return result
    
    def _extract_cres(self, html: str) -> Optional[str]:
        patterns = [
            r'name=["\']cres["\']\s+value=["\']([^"\']+)["\']',
            r'value=["\']([^"\']+)["\']\s+name=["\']cres["\']',
            r'"cres"\s*:\s*"([^"]+)"',
            r'CRes["\s:=]+([a-zA-Z0-9+/=]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)
        
        soup = BeautifulSoup(html, 'html.parser')
        cres_input = soup.find('input', {'name': re.compile(r'cres', re.IGNORECASE)})
        if cres_input:
            return cres_input.get('value', '')
        
        return None
    
    def _decode_cres(self, cres: str) -> Optional[Dict[str, Any]]:
        try:
            padding = 4 - len(cres) % 4
            if padding != 4:
                cres += "=" * padding
            
            decoded = base64.b64decode(cres).decode('utf-8')
            return json.loads(decoded)
        except Exception:
            return None
    
    def _is_challenge_page(self, html: str) -> bool:
        challenge_indicators = [
            'iframe',
            'challenge',
            'authentication',
            'verify',
            'otp',
            'password'
        ]
        
        html_lower = html.lower()
        return any(indicator in html_lower for indicator in challenge_indicators)


class ThreeDSManager:
    def __init__(self, http_client: AdvancedHTTPClient):
        self.http_client = http_client
        self.detector = ThreeDSDetector()
        self.v1_handler = ThreeDSv1Handler(http_client)
        self.v2_handler = ThreeDSv2Handler(http_client)
        self.behavior = HumanBehaviorSimulator()
        
    def detect_challenge(self, response_data: Dict[str, Any]) -> Optional[ThreeDSChallenge]:
        return self.detector.detect(response_data)
    
    def detect_challenge_from_html(self, html: str) -> Optional[ThreeDSChallenge]:
        return self.detector.detect_from_html(html)
    
    def handle_challenge(self, challenge: ThreeDSChallenge) -> ThreeDSResult:
        if challenge.version == "1.0":
            return self.v1_handler.handle_challenge(challenge)
        elif challenge.version == "2.0":
            return self.v2_handler.handle_challenge(challenge)
        elif challenge.version == "redirect":
            return self._handle_redirect(challenge)
        else:
            return ThreeDSResult(
                success=False,
                version=challenge.version,
                error=f"Unsupported 3DS version: {challenge.version}"
            )
    
    def _handle_redirect(self, challenge: ThreeDSChallenge) -> ThreeDSResult:
        result = ThreeDSResult(
            success=False,
            version="redirect"
        )
        
        self.behavior.human_delay(action_type="page_load")
        
        response = self.http_client.get(challenge.acs_url, allow_redirects=True)
        
        if response.status_code == 200:
            html_challenge = self.detector.detect_from_html(response.body)
            
            if html_challenge:
                return self.handle_challenge(html_challenge)
            
            if self._is_success_page(response.body, response.url):
                result.success = True
                result.trans_status = "Y"
            else:
                result.error = "Unknown redirect result"
        else:
            result.error = f"Redirect failed: HTTP {response.status_code}"
        
        return result
    
    def _is_success_page(self, html: str, url: str) -> bool:
        success_indicators = [
            'success',
            'complete',
            'confirmed',
            'thank you',
            'order-received',
            'order-confirmation'
        ]
        
        html_lower = html.lower()
        url_lower = url.lower()
        
        return any(indicator in html_lower or indicator in url_lower 
                   for indicator in success_indicators)
    
    def complete_stripe_3ds(self, client_secret: str, source_id: str, 
                            return_url: str = None) -> ThreeDSResult:
        result = ThreeDSResult(
            success=False,
            version="stripe"
        )
        
        authenticate_url = f"https://hooks.stripe.com/3d_secure_2/authenticate"
        
        data = {
            "source": source_id,
            "client_secret": client_secret
        }
        
        if return_url:
            data["return_url"] = return_url
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        self.behavior.human_delay(action_type="page_load")
        
        response = self.http_client.post(authenticate_url, data=data, headers=headers)
        
        if response.status_code == 200:
            try:
                response_data = json.loads(response.body)
                
                if response_data.get("state") == "succeeded":
                    result.success = True
                    result.trans_status = "Y"
                elif response_data.get("state") == "failed":
                    result.error = response_data.get("failure_message", "Authentication failed")
                else:
                    result.error = f"Unknown state: {response_data.get('state')}"
                    
            except json.JSONDecodeError:
                result.error = "Invalid response"
        else:
            result.error = f"HTTP {response.status_code}"
        
        return result
    
    def complete_braintree_3ds(self, nonce: str, lookup_data: Dict[str, Any]) -> ThreeDSResult:
        result = ThreeDSResult(
            success=False,
            version="braintree"
        )
        
        if lookup_data.get("acsUrl"):
            challenge = ThreeDSChallenge(
                version="1.0" if lookup_data.get("paReq") else "2.0",
                acs_url=lookup_data["acsUrl"],
                pareq=lookup_data.get("paReq"),
                md=lookup_data.get("md"),
                term_url=lookup_data.get("termUrl"),
                creq=lookup_data.get("creq")
            )
            
            return self.handle_challenge(challenge)
        
        result.success = True
        result.trans_status = "Y"
        
        return result
