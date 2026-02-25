import json
import logging
import os
from typing import Dict, Any, Optional


logger = logging.getLogger(__name__)


class Config:
    data: Dict[str, Any] = {}

    def __init__(self, filename: str):
        """
        initialize config
        :param filename: json file containing the parameter
        """

        logger.info("loading config file: '{}'".format(filename))

        try:
            # Validate file path to prevent path traversal
            if not filename or '..' in filename or filename.startswith('/'):
                raise ValueError("Invalid config filename")

            # Ensure file exists and is readable
            if not os.path.isfile(filename):
                raise FileNotFoundError("Config file not found: {}".format(filename))

            with open(filename, "r", encoding="utf8") as json_file:
                self.data = json.load(json_file)
        except (FileNotFoundError, PermissionError) as e:
            logger.error("Config file access error: {}".format(str(e)))
            raise
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Config file format error: {}".format(str(e)))
            raise
        except Exception as e:
            logger.error("Unexpected error reading config: {}".format(str(e)))
            raise

    def __getattr__(self, item: str) -> Optional[Any]:
        """ get config data """
        if not isinstance(item, str):
            raise TypeError("Config key must be string")
        if item in self.data:
            return self.data[item]
        return None

    def __getitem__(self, item: str) -> Any:
        return self.data[item]
