import random
import time
import math
from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass


@dataclass
class Point:
    x: float
    y: float


class HumanBehaviorSimulator:
    def __init__(self, speed_factor: float = 1.0):
        self.speed_factor = speed_factor
        self.last_action_time = time.time()
        self.action_history = []
        
    def human_delay(self, min_delay: float = 0.5, max_delay: float = 2.0, action_type: str = "default") -> float:
        delay_multipliers = {
            "page_load": (2.0, 5.0),
            "form_field": (0.3, 0.8),
            "button_click": (0.2, 0.5),
            "reading": (3.0, 8.0),
            "thinking": (1.0, 3.0),
            "scroll": (0.5, 1.5),
            "default": (min_delay, max_delay)
        }
        
        min_d, max_d = delay_multipliers.get(action_type, (min_delay, max_delay))
        
        base_delay = random.uniform(min_d, max_d)
        
        variance = random.gauss(0, 0.1)
        delay = base_delay * (1 + variance) * self.speed_factor
        
        if random.random() < 0.1:
            delay += random.uniform(0.5, 2.0)
        
        delay = max(0.1, delay)
        
        self.action_history.append({
            "type": action_type,
            "delay": delay,
            "timestamp": time.time()
        })
        
        time.sleep(delay)
        self.last_action_time = time.time()
        
        return delay


class TypingSimulator:
    def __init__(self, wpm: int = 60):
        self.base_delay = 60.0 / (wpm * 5)
        self.error_rate = 0.02
        self.correction_delay = 0.15
        
    def type_like_human(self, text: str, callback: Optional[Callable[[str], None]] = None) -> List[dict]:
        events = []
        typed_text = ""
        
        for i, char in enumerate(text):
            if random.random() < self.error_rate and len(typed_text) > 0:
                wrong_char = self._get_nearby_key(char)
                delay = self._get_keystroke_delay(wrong_char, typed_text)
                time.sleep(delay)
                typed_text += wrong_char
                events.append({"type": "keydown", "char": wrong_char, "delay": delay, "error": True})
                
                if callback:
                    callback(typed_text)
                
                time.sleep(self.correction_delay + random.uniform(0.05, 0.15))
                typed_text = typed_text[:-1]
                events.append({"type": "backspace", "delay": self.correction_delay})
                
                if callback:
                    callback(typed_text)
            
            delay = self._get_keystroke_delay(char, typed_text)
            time.sleep(delay)
            typed_text += char
            events.append({"type": "keydown", "char": char, "delay": delay, "error": False})
            
            if callback:
                callback(typed_text)
            
            if char in ".!?" and i < len(text) - 1:
                pause = random.uniform(0.3, 0.8)
                time.sleep(pause)
                events.append({"type": "pause", "delay": pause, "reason": "sentence_end"})
            
            elif char == " " and random.random() < 0.05:
                pause = random.uniform(0.2, 0.5)
                time.sleep(pause)
                events.append({"type": "pause", "delay": pause, "reason": "word_pause"})
        
        return events
    
    def _get_keystroke_delay(self, char: str, context: str) -> float:
        base = self.base_delay
        
        if char.isupper():
            base *= 1.2
        
        if char in "!@#$%^&*()_+-=[]{}|;':\",./<>?":
            base *= 1.3
        
        if char.isdigit():
            base *= 1.1
        
        variance = random.gauss(0, 0.3)
        delay = base * (1 + variance)
        
        return max(0.03, delay)
    
    def _get_nearby_key(self, char: str) -> str:
        keyboard_layout = {
            'q': 'wa', 'w': 'qeas', 'e': 'wrds', 'r': 'etdf', 't': 'ryfg',
            'y': 'tugh', 'u': 'yihj', 'i': 'uojk', 'o': 'ipkl', 'p': 'ol',
            'a': 'qwsz', 's': 'awedxz', 'd': 'serfcx', 'f': 'drtgvc',
            'g': 'ftyhbv', 'h': 'gyujnb', 'j': 'huikmn', 'k': 'jiolm',
            'l': 'kop', 'z': 'asx', 'x': 'zsdc', 'c': 'xdfv', 'v': 'cfgb',
            'b': 'vghn', 'n': 'bhjm', 'm': 'njk',
            '1': '2q', '2': '13qw', '3': '24we', '4': '35er', '5': '46rt',
            '6': '57ty', '7': '68yu', '8': '79ui', '9': '80io', '0': '9p'
        }
        
        char_lower = char.lower()
        if char_lower in keyboard_layout:
            nearby = keyboard_layout[char_lower]
            wrong = random.choice(nearby)
            return wrong.upper() if char.isupper() else wrong
        
        return char


class MouseMovementSimulator:
    def __init__(self):
        self.current_position = Point(0, 0)
        self.movement_history = []
        
    def bezier_curve(self, start: Point, end: Point, control_points: int = 2) -> List[Point]:
        controls = [start]
        
        for _ in range(control_points):
            mid_x = (start.x + end.x) / 2 + random.uniform(-100, 100)
            mid_y = (start.y + end.y) / 2 + random.uniform(-100, 100)
            controls.append(Point(mid_x, mid_y))
        
        controls.append(end)
        
        points = []
        num_steps = int(math.sqrt((end.x - start.x)**2 + (end.y - start.y)**2) / 5)
        num_steps = max(10, min(100, num_steps))
        
        for i in range(num_steps + 1):
            t = i / num_steps
            point = self._calculate_bezier_point(t, controls)
            points.append(point)
        
        return points
    
    def _calculate_bezier_point(self, t: float, controls: List[Point]) -> Point:
        n = len(controls) - 1
        x = 0
        y = 0
        
        for i, control in enumerate(controls):
            coefficient = self._binomial_coefficient(n, i) * (1 - t)**(n - i) * t**i
            x += coefficient * control.x
            y += coefficient * control.y
        
        return Point(x, y)
    
    def _binomial_coefficient(self, n: int, k: int) -> int:
        if k < 0 or k > n:
            return 0
        if k == 0 or k == n:
            return 1
        
        result = 1
        for i in range(min(k, n - k)):
            result = result * (n - i) // (i + 1)
        return result
    
    def move_to(self, target: Point, callback: Optional[Callable[[Point], None]] = None) -> List[dict]:
        path = self.bezier_curve(self.current_position, target)
        events = []
        
        for i, point in enumerate(path):
            jitter_x = random.gauss(0, 1)
            jitter_y = random.gauss(0, 1)
            actual_point = Point(point.x + jitter_x, point.y + jitter_y)
            
            base_delay = 0.005
            if i > 0:
                distance = math.sqrt(
                    (actual_point.x - path[i-1].x)**2 + 
                    (actual_point.y - path[i-1].y)**2
                )
                base_delay = distance / 1000
            
            delay = base_delay * random.uniform(0.8, 1.2)
            time.sleep(delay)
            
            self.current_position = actual_point
            events.append({
                "type": "mousemove",
                "x": actual_point.x,
                "y": actual_point.y,
                "delay": delay
            })
            
            if callback:
                callback(actual_point)
        
        self.movement_history.extend(events)
        return events
    
    def click(self, position: Optional[Point] = None, button: str = "left") -> List[dict]:
        events = []
        
        if position and (position.x != self.current_position.x or position.y != self.current_position.y):
            move_events = self.move_to(position)
            events.extend(move_events)
        
        pre_click_delay = random.uniform(0.05, 0.15)
        time.sleep(pre_click_delay)
        events.append({"type": "pre_click_pause", "delay": pre_click_delay})
        
        click_duration = random.uniform(0.05, 0.12)
        events.append({
            "type": "mousedown",
            "button": button,
            "x": self.current_position.x,
            "y": self.current_position.y
        })
        
        time.sleep(click_duration)
        
        events.append({
            "type": "mouseup",
            "button": button,
            "x": self.current_position.x,
            "y": self.current_position.y,
            "duration": click_duration
        })
        
        return events
    
    def hover(self, position: Point, duration: float = None) -> List[dict]:
        events = self.move_to(position)
        
        if duration is None:
            duration = random.uniform(0.3, 1.0)
        
        time.sleep(duration)
        events.append({"type": "hover", "duration": duration, "x": position.x, "y": position.y})
        
        return events


class ScrollSimulator:
    def __init__(self):
        self.current_scroll_position = 0
        self.scroll_history = []
        
    def scroll_to(self, target_position: int, viewport_height: int = 800, callback: Optional[Callable[[int], None]] = None) -> List[dict]:
        events = []
        
        distance = target_position - self.current_scroll_position
        if abs(distance) < 10:
            return events
        
        direction = 1 if distance > 0 else -1
        remaining = abs(distance)
        
        while remaining > 0:
            scroll_amount = min(remaining, random.randint(100, 300))
            
            if remaining < 200:
                scroll_amount = remaining
            
            self.current_scroll_position += scroll_amount * direction
            remaining -= scroll_amount
            
            delay = random.uniform(0.02, 0.08)
            time.sleep(delay)
            
            events.append({
                "type": "scroll",
                "delta": scroll_amount * direction,
                "position": self.current_scroll_position,
                "delay": delay
            })
            
            if callback:
                callback(self.current_scroll_position)
            
            if random.random() < 0.1:
                pause = random.uniform(0.5, 1.5)
                time.sleep(pause)
                events.append({"type": "scroll_pause", "duration": pause})
        
        self.scroll_history.extend(events)
        return events
    
    def natural_scroll(self, page_height: int, viewport_height: int = 800, read_content: bool = True) -> List[dict]:
        events = []
        
        initial_pause = random.uniform(1.0, 3.0)
        time.sleep(initial_pause)
        events.append({"type": "initial_read", "duration": initial_pause})
        
        scroll_positions = []
        current = 0
        while current < page_height - viewport_height:
            scroll_amount = random.randint(200, 500)
            current += scroll_amount
            scroll_positions.append(min(current, page_height - viewport_height))
        
        for target in scroll_positions:
            scroll_events = self.scroll_to(target, viewport_height)
            events.extend(scroll_events)
            
            if read_content:
                read_time = random.uniform(0.5, 2.0)
                time.sleep(read_time)
                events.append({"type": "reading", "duration": read_time, "position": target})
        
        return events


class FormInteractionSimulator:
    def __init__(self):
        self.behavior = HumanBehaviorSimulator()
        self.typing = TypingSimulator()
        self.mouse = MouseMovementSimulator()
        
    def fill_form_field(self, field_position: Point, value: str, field_type: str = "text") -> List[dict]:
        events = []
        
        hover_events = self.mouse.hover(field_position, random.uniform(0.1, 0.3))
        events.extend(hover_events)
        
        click_events = self.mouse.click(field_position)
        events.extend(click_events)
        
        self.behavior.human_delay(action_type="form_field")
        
        if field_type == "text" or field_type == "email":
            typing_events = self.typing.type_like_human(value)
            events.extend(typing_events)
        elif field_type == "password":
            typing_events = self.typing.type_like_human(value)
            events.extend(typing_events)
        elif field_type == "card_number":
            formatted_value = self._format_card_number(value)
            typing_events = self.typing.type_like_human(formatted_value)
            events.extend(typing_events)
        elif field_type == "expiry":
            typing_events = self.typing.type_like_human(value)
            events.extend(typing_events)
        elif field_type == "cvv":
            typing_events = self.typing.type_like_human(value)
            events.extend(typing_events)
        
        post_field_delay = random.uniform(0.2, 0.5)
        time.sleep(post_field_delay)
        events.append({"type": "post_field_pause", "delay": post_field_delay})
        
        return events
    
    def _format_card_number(self, card_number: str) -> str:
        clean = ''.join(filter(str.isdigit, card_number))
        formatted = ' '.join([clean[i:i+4] for i in range(0, len(clean), 4)])
        return formatted
    
    def fill_checkout_form(self, form_data: dict, field_positions: dict) -> List[dict]:
        events = []
        
        field_order = [
            "email", "first_name", "last_name", "address", "city",
            "state", "zip", "country", "phone", "card_number",
            "expiry", "cvv"
        ]
        
        for field_name in field_order:
            if field_name in form_data and field_name in field_positions:
                field_type = self._get_field_type(field_name)
                field_events = self.fill_form_field(
                    field_positions[field_name],
                    form_data[field_name],
                    field_type
                )
                events.extend(field_events)
                
                if random.random() < 0.3:
                    think_time = random.uniform(0.5, 1.5)
                    time.sleep(think_time)
                    events.append({"type": "thinking", "duration": think_time})
        
        return events
    
    def _get_field_type(self, field_name: str) -> str:
        type_mapping = {
            "email": "email",
            "password": "password",
            "card_number": "card_number",
            "expiry": "expiry",
            "cvv": "cvv"
        }
        return type_mapping.get(field_name, "text")


class PageInteractionSimulator:
    def __init__(self):
        self.behavior = HumanBehaviorSimulator()
        self.mouse = MouseMovementSimulator()
        self.scroll = ScrollSimulator()
        
    def simulate_page_load_behavior(self, page_height: int, viewport_height: int = 800) -> List[dict]:
        events = []
        
        initial_wait = random.uniform(1.0, 3.0)
        time.sleep(initial_wait)
        events.append({"type": "initial_page_view", "duration": initial_wait})
        
        random_x = random.randint(100, 500)
        random_y = random.randint(100, 300)
        move_events = self.mouse.move_to(Point(random_x, random_y))
        events.extend(move_events)
        
        if page_height > viewport_height:
            scroll_events = self.scroll.natural_scroll(page_height, viewport_height)
            events.extend(scroll_events)
        
        return events
    
    def simulate_product_browse(self, product_positions: List[Point]) -> List[dict]:
        events = []
        
        for i, position in enumerate(product_positions):
            hover_events = self.mouse.hover(position, random.uniform(0.5, 2.0))
            events.extend(hover_events)
            
            if random.random() < 0.3:
                click_events = self.mouse.click(position)
                events.extend(click_events)
                
                view_time = random.uniform(2.0, 5.0)
                time.sleep(view_time)
                events.append({"type": "product_view", "duration": view_time, "index": i})
        
        return events
