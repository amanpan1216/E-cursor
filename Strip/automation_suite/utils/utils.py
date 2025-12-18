import re
import json
import time
import random
import hashlib
import string
import os
from typing import Dict, List, Optional, Any, Tuple, Union
from urllib.parse import urlparse, urljoin, parse_qs, urlencode
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class CardInfo:
    number: str
    exp_month: str
    exp_year: str
    cvv: str
    brand: str
    bin: str
    last4: str
    is_valid: bool


@dataclass
class BillingInfo:
    first_name: str
    last_name: str
    email: str
    phone: str
    address_1: str
    address_2: str
    city: str
    state: str
    postcode: str
    country: str


@dataclass
class ShippingInfo:
    first_name: str
    last_name: str
    address_1: str
    address_2: str
    city: str
    state: str
    postcode: str
    country: str
    phone: str


class CardValidator:
    def __init__(self):
        self.brand_patterns = {
            "visa": r"^4[0-9]{12}(?:[0-9]{3})?$",
            "mastercard": r"^(?:5[1-5][0-9]{2}|222[1-9]|22[3-9][0-9]|2[3-6][0-9]{2}|27[01][0-9]|2720)[0-9]{12}$",
            "amex": r"^3[47][0-9]{13}$",
            "discover": r"^6(?:011|5[0-9]{2})[0-9]{12}$",
            "diners": r"^3(?:0[0-5]|[68][0-9])[0-9]{11}$",
            "jcb": r"^(?:2131|1800|35\d{3})\d{11}$",
            "unionpay": r"^(62|88)\d{14,17}$"
        }
        
    def validate(self, card_number: str) -> CardInfo:
        cleaned_number = re.sub(r'\D', '', card_number)
        
        is_valid = self._luhn_check(cleaned_number)
        brand = self._detect_brand(cleaned_number)
        
        return CardInfo(
            number=cleaned_number,
            exp_month="",
            exp_year="",
            cvv="",
            brand=brand,
            bin=cleaned_number[:6] if len(cleaned_number) >= 6 else "",
            last4=cleaned_number[-4:] if len(cleaned_number) >= 4 else "",
            is_valid=is_valid
        )
    
    def _luhn_check(self, card_number: str) -> bool:
        if not card_number.isdigit():
            return False
        
        digits = [int(d) for d in card_number]
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        
        checksum = sum(odd_digits)
        
        for d in even_digits:
            checksum += sum(divmod(d * 2, 10))
        
        return checksum % 10 == 0
    
    def _detect_brand(self, card_number: str) -> str:
        for brand, pattern in self.brand_patterns.items():
            if re.match(pattern, card_number):
                return brand
        return "unknown"
    
    def validate_expiry(self, exp_month: str, exp_year: str) -> bool:
        try:
            month = int(exp_month)
            year = int(exp_year)
            
            if year < 100:
                year += 2000
            
            if not (1 <= month <= 12):
                return False
            
            now = datetime.now()
            expiry = datetime(year, month, 1) + timedelta(days=31)
            
            return expiry > now
        except ValueError:
            return False
    
    def validate_cvv(self, cvv: str, brand: str = None) -> bool:
        if not cvv.isdigit():
            return False
        
        if brand == "amex":
            return len(cvv) == 4
        
        return len(cvv) in [3, 4]


class CardParser:
    def __init__(self):
        self.validator = CardValidator()
        
    def parse_line(self, line: str) -> Optional[CardInfo]:
        patterns = [
            r"(\d{13,19})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})",
            r"(\d{13,19}):(\d{1,2}):(\d{2,4}):(\d{3,4})",
            r"(\d{13,19})\s+(\d{1,2})\s+(\d{2,4})\s+(\d{3,4})",
            r"(\d{13,19})/(\d{1,2})/(\d{2,4})/(\d{3,4})",
            r"(\d{13,19}),(\d{1,2}),(\d{2,4}),(\d{3,4})"
        ]
        
        for pattern in patterns:
            match = re.match(pattern, line.strip())
            if match:
                number, exp_month, exp_year, cvv = match.groups()
                
                card_info = self.validator.validate(number)
                card_info.exp_month = exp_month.zfill(2)
                card_info.exp_year = exp_year if len(exp_year) == 4 else f"20{exp_year}"
                card_info.cvv = cvv
                
                return card_info
        
        return None
    
    def parse_file(self, file_path: str) -> List[CardInfo]:
        cards = []
        
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    card = self.parse_line(line)
                    if card:
                        cards.append(card)
        except FileNotFoundError:
            pass
        
        return cards
    
    def parse_text(self, text: str) -> List[CardInfo]:
        cards = []
        
        for line in text.strip().split('\n'):
            card = self.parse_line(line)
            if card:
                cards.append(card)
        
        return cards


class AddressGenerator:
    def __init__(self):
        self.us_states = {
            "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
            "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
            "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
            "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
            "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
            "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
            "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
            "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
            "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
            "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
            "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
            "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
            "WI": "Wisconsin", "WY": "Wyoming"
        }
        
        self.first_names = [
            "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
            "Thomas", "Charles", "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth",
            "Barbara", "Susan", "Jessica", "Sarah", "Karen", "Daniel", "Matthew", "Anthony",
            "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua", "Kenneth"
        ]
        
        self.last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
            "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
            "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
            "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson"
        ]
        
        self.street_names = [
            "Main", "Oak", "Maple", "Cedar", "Pine", "Elm", "Washington", "Lake",
            "Hill", "Park", "Walnut", "Sunset", "Cherry", "Willow", "Forest",
            "River", "Spring", "Valley", "Highland", "Meadow"
        ]
        
        self.street_types = [
            "Street", "Avenue", "Road", "Drive", "Lane", "Boulevard", "Court",
            "Place", "Way", "Circle", "Trail", "Parkway"
        ]
        
        self.cities = [
            ("New York", "NY", "10001"), ("Los Angeles", "CA", "90001"),
            ("Chicago", "IL", "60601"), ("Houston", "TX", "77001"),
            ("Phoenix", "AZ", "85001"), ("Philadelphia", "PA", "19101"),
            ("San Antonio", "TX", "78201"), ("San Diego", "CA", "92101"),
            ("Dallas", "TX", "75201"), ("San Jose", "CA", "95101"),
            ("Austin", "TX", "78701"), ("Jacksonville", "FL", "32099"),
            ("Fort Worth", "TX", "76101"), ("Columbus", "OH", "43085"),
            ("Charlotte", "NC", "28201"), ("San Francisco", "CA", "94102"),
            ("Indianapolis", "IN", "46201"), ("Seattle", "WA", "98101"),
            ("Denver", "CO", "80201"), ("Boston", "MA", "02101")
        ]
        
    def generate_billing(self, country: str = "US") -> BillingInfo:
        first_name = random.choice(self.first_names)
        last_name = random.choice(self.last_names)
        city, state, postcode = random.choice(self.cities)
        
        street_number = random.randint(100, 9999)
        street_name = random.choice(self.street_names)
        street_type = random.choice(self.street_types)
        address_1 = f"{street_number} {street_name} {street_type}"
        
        apt_number = random.randint(1, 999) if random.random() > 0.7 else None
        address_2 = f"Apt {apt_number}" if apt_number else ""
        
        email_domain = random.choice(["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"])
        email = f"{first_name.lower()}.{last_name.lower()}{random.randint(1, 999)}@{email_domain}"
        
        phone = f"+1{random.randint(200, 999)}{random.randint(200, 999)}{random.randint(1000, 9999)}"
        
        return BillingInfo(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            address_1=address_1,
            address_2=address_2,
            city=city,
            state=state,
            postcode=postcode,
            country=country
        )
    
    def generate_shipping(self, country: str = "US") -> ShippingInfo:
        billing = self.generate_billing(country)
        
        return ShippingInfo(
            first_name=billing.first_name,
            last_name=billing.last_name,
            address_1=billing.address_1,
            address_2=billing.address_2,
            city=billing.city,
            state=billing.state,
            postcode=billing.postcode,
            country=billing.country,
            phone=billing.phone
        )
    
    def billing_to_dict(self, billing: BillingInfo) -> Dict[str, str]:
        return {
            "first_name": billing.first_name,
            "last_name": billing.last_name,
            "email": billing.email,
            "phone": billing.phone,
            "address_1": billing.address_1,
            "address_2": billing.address_2,
            "city": billing.city,
            "state": billing.state,
            "postcode": billing.postcode,
            "country": billing.country
        }
    
    def shipping_to_dict(self, shipping: ShippingInfo) -> Dict[str, str]:
        return {
            "first_name": shipping.first_name,
            "last_name": shipping.last_name,
            "address_1": shipping.address_1,
            "address_2": shipping.address_2,
            "city": shipping.city,
            "state": shipping.state,
            "postcode": shipping.postcode,
            "country": shipping.country,
            "phone": shipping.phone
        }


class URLUtils:
    @staticmethod
    def extract_domain(url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc
    
    @staticmethod
    def extract_base_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    
    @staticmethod
    def join_url(base: str, path: str) -> str:
        return urljoin(base, path)
    
    @staticmethod
    def parse_query_string(url: str) -> Dict[str, List[str]]:
        parsed = urlparse(url)
        return parse_qs(parsed.query)
    
    @staticmethod
    def build_query_string(params: Dict[str, str]) -> str:
        return urlencode(params)
    
    @staticmethod
    def add_query_params(url: str, params: Dict[str, str]) -> str:
        parsed = urlparse(url)
        existing_params = parse_qs(parsed.query)
        
        for key, value in params.items():
            existing_params[key] = [value]
        
        query_string = urlencode({k: v[0] for k, v in existing_params.items()})
        
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{query_string}"


class HashUtils:
    @staticmethod
    def md5(text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()
    
    @staticmethod
    def sha1(text: str) -> str:
        return hashlib.sha1(text.encode()).hexdigest()
    
    @staticmethod
    def sha256(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()
    
    @staticmethod
    def sha512(text: str) -> str:
        return hashlib.sha512(text.encode()).hexdigest()
    
    @staticmethod
    def random_hex(length: int) -> str:
        return ''.join(random.choice('0123456789abcdef') for _ in range(length))
    
    @staticmethod
    def random_string(length: int, include_digits: bool = True) -> str:
        chars = string.ascii_letters
        if include_digits:
            chars += string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    @staticmethod
    def uuid4() -> str:
        return f"{HashUtils.random_hex(8)}-{HashUtils.random_hex(4)}-4{HashUtils.random_hex(3)}-{random.choice('89ab')}{HashUtils.random_hex(3)}-{HashUtils.random_hex(12)}"


class TimeUtils:
    @staticmethod
    def timestamp() -> int:
        return int(time.time())
    
    @staticmethod
    def timestamp_ms() -> int:
        return int(time.time() * 1000)
    
    @staticmethod
    def iso_format() -> str:
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    
    @staticmethod
    def random_delay(min_seconds: float, max_seconds: float) -> float:
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
        return delay
    
    @staticmethod
    def human_delay() -> float:
        delay = random.gauss(1.5, 0.5)
        delay = max(0.5, min(delay, 3.0))
        time.sleep(delay)
        return delay


class JSONUtils:
    @staticmethod
    def safe_parse(text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    
    @staticmethod
    def extract_json_from_html(html: str) -> List[Dict[str, Any]]:
        results = []
        
        pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(pattern, html)
        
        for match in matches:
            parsed = JSONUtils.safe_parse(match)
            if parsed:
                results.append(parsed)
        
        return results
    
    @staticmethod
    def find_key(data: Union[Dict, List], key: str) -> List[Any]:
        results = []
        
        if isinstance(data, dict):
            if key in data:
                results.append(data[key])
            for value in data.values():
                results.extend(JSONUtils.find_key(value, key))
        elif isinstance(data, list):
            for item in data:
                results.extend(JSONUtils.find_key(item, key))
        
        return results


class FileUtils:
    @staticmethod
    def read_lines(file_path: str) -> List[str]:
        try:
            with open(file_path, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            return []
    
    @staticmethod
    def write_lines(file_path: str, lines: List[str]):
        with open(file_path, 'w') as f:
            for line in lines:
                f.write(f"{line}\n")
    
    @staticmethod
    def append_line(file_path: str, line: str):
        with open(file_path, 'a') as f:
            f.write(f"{line}\n")
    
    @staticmethod
    def read_json(file_path: str) -> Optional[Dict[str, Any]]:
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
    
    @staticmethod
    def write_json(file_path: str, data: Dict[str, Any], indent: int = 2):
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=indent)
    
    @staticmethod
    def ensure_directory(dir_path: str):
        os.makedirs(dir_path, exist_ok=True)


class ResultLogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        FileUtils.ensure_directory(log_dir)
        
        self.success_file = os.path.join(log_dir, "success.txt")
        self.failure_file = os.path.join(log_dir, "failure.txt")
        self.error_file = os.path.join(log_dir, "errors.txt")
        
    def log_success(self, card: str, site: str, message: str = ""):
        timestamp = TimeUtils.iso_format()
        line = f"[{timestamp}] {card} | {site} | {message}"
        FileUtils.append_line(self.success_file, line)
    
    def log_failure(self, card: str, site: str, reason: str = ""):
        timestamp = TimeUtils.iso_format()
        line = f"[{timestamp}] {card} | {site} | {reason}"
        FileUtils.append_line(self.failure_file, line)
    
    def log_error(self, card: str, site: str, error: str):
        timestamp = TimeUtils.iso_format()
        line = f"[{timestamp}] {card} | {site} | ERROR: {error}"
        FileUtils.append_line(self.error_file, line)
    
    def get_stats(self) -> Dict[str, int]:
        success_count = len(FileUtils.read_lines(self.success_file))
        failure_count = len(FileUtils.read_lines(self.failure_file))
        error_count = len(FileUtils.read_lines(self.error_file))
        
        return {
            "success": success_count,
            "failure": failure_count,
            "errors": error_count,
            "total": success_count + failure_count + error_count
        }
