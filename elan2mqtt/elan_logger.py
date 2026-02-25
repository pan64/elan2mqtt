import asyncio
import logging
from logging import LogRecord

from config import Config


def set_logger(config: Config) -> None:
    formatter = config["logging"]["formatter"]
    log_level = config["logging"]["log_level"]

    try:
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs) -> LogRecord:
            record = old_factory(*args, **kwargs)
            try:
                current_task = asyncio.current_task()
                record.coproc = current_task.get_name() if current_task else "main"
            except Exception:
                record.coproc = "unknown"
            return record

        logging.setLogRecordFactory(record_factory)
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        if not isinstance(numeric_level, int):
            numeric_level = logging.INFO
        logging.basicConfig(level=numeric_level, format=formatter)
    except (KeyError, TypeError):
        # Use safe defaults
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s - %(message)s')
    except Exception:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s - %(message)s')
