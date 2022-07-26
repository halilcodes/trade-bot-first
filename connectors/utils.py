from functools import wraps
from time import time, perf_counter
import logkeeper
import logging
import requests

logger = logging.getLogger("utils.py")
logkeeper.log_keeper("connectors.log", "utils.py")


def timestamp():
    return int(time() * 1000)


def timer(f):
    @wraps(f)
    def wrap(*args, **kw):
        ts = perf_counter()
        result = f(*args, **kw)
        te = perf_counter()
        logger.info(f"Function: {f.__name__} | Runtime: {te - ts}")
        return result
    return wrap


if __name__ == '__main__':
    @timer
    def trial(n):
        return [i**2+5*i+(i**0.5) for i in range(n)]


    trial(1000000)

