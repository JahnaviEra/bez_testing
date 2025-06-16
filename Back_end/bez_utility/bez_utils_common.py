import random, string
from datetime import datetime, timezone

def _generate_uid(data):
    # Declare a digits variable which stores all digits as digits
    n = int(data.get("n"))
    if n < 1:
        raise ValueError("Number of digits must be at least 1")
    lower_bound = 10**(n - 1)  # Smallest number with the given digits
    upper_bound = (10**n) - 1  # Largest number with the given digits
    return str(random.randint(lower_bound, upper_bound))

def _current_time():
    # returns 1742234790.334879
    return datetime.now(timezone.utc).timestamp()

def _date_to_timestamp(data):
    date_obj = data.get("date_obj", "")
    return date_obj.timestamp()

def _date_now():
    # returns 2025-03-17T18:06:03.613662+00:00
    return datetime.now(timezone.utc)

def _generate_otp():
    return ''.join(random.choices(string.digits, k=6))
