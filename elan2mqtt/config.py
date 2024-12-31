import json
import logging
logger = logging.getLogger(__name__)

class Config:
    data = {}
    def __init__(self, filename: str):
        """
        initialize config
        :param filename: json file containing the parameter
        """

        logger.info("loading config file")

        try:
            with open(filename, "r", encoding="utf8") as json_file:
                self.data = json.load(json_file)
        except BaseException as be:
            logger.error("read config exception occurred")
            logger.error(be, exc_info=True)
            raise

    def __getattr__(self, item: str):
        """ get config data """
        if item in self.data:
            return self.data[item]
        print(str)

    def __getitem__(self, item):
        return self.data[item]
