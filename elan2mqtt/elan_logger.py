import asyncio
import logging
from logging import LogRecord

from config import Config


def set_logger(config: Config):
    formatter = config["logging"]["formatter"]
    log_level = config["logging"]["log_level"]

    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs) -> LogRecord:
        record = old_factory(*args, **kwargs)
        try:
            ttt = asyncio.current_task()
            record.coproc = ttt.get_name()
        except:  # noqa: E722
            record.coproc = "unknown"
        return record

    logging.setLogRecordFactory(record_factory)
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = 30
    logging.basicConfig(level=numeric_level, format=formatter)
