import asyncio
import logging
import sys

from config import Config

class CustomAdapter(logging.LoggerAdapter):
    """
    This example adapter expects the passed in dict-like object to have a
    'connid' key, whose value in brackets is prepended to the log message.
    """
    def process(self, msg, kwargs):
        return '[%s] %s' % (self.extra['coproc'], asyncio.current_task().get_name()), kwargs

class ContextFilter(logging.Filter):
    """
    This is a filter which injects contextual information into the log.

    Rather than use actual contextual information, we just use random
    data in this demo.
    """

    def filter(self, record):
        #record.coproc = asyncio.current_task().get_name()
        return True

def set_logger(config: Config):
    formatter = config["logging"]["formatter"]
    log_level = config["logging"]["log_level"]

    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.coproc = asyncio.current_task().get_name()
        return record

    logging.setLogRecordFactory(record_factory)
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = 30
    logging.basicConfig(level=numeric_level, format=formatter)
