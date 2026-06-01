from slowapi import Limiter
from slowapi.util import get_remote_address
from config import API_RATE_LIMIT

limiter = Limiter(key_func=get_remote_address, default_limits=[API_RATE_LIMIT])