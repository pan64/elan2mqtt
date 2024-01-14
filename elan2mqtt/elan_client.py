import datetime
import hashlib
import json
import logging
from logging import Logger

import requests
import websockets

logger: Logger = logging.getLogger(__name__)


class ElanException(BaseException):
    pass


class ElanClient:

    def __init__(self):

        self.creds = {}
        self.elan_url: str = None
        self.logged_in: bool = False
        self.session: requests.Session = None
        self.cookie: str = None
        self.ws: websockets.WebSocketClientProtocol = None

    def setup(self) -> None:
        self.read_config()

    def read_config(self) -> None:
        logging.info("loading config file")
        with open("config.json", "r") as json_file:
            data = json.load(json_file)
        self.elan_url = data["options"]["eLanURL"]
        elan_user = data["options"]["username"]
        elan_pass = data["options"]["password"]
        key = hashlib.sha1(elan_pass.encode('utf-8')).hexdigest()
        self.creds = {
            'name': elan_user,
            'key': key
        }

        logger.info("elan url: '{}', user: '{}', pass: '{}'".format(self.elan_url, elan_user, elan_pass))

    def check_response(self, response: requests.Response) -> bool:
        """
        check if response is acceptable
        :param response:
        :return: true/false
        """
        if response.status_code == 200:
            return True
        logger.debug(response.status_code)
        logger.debug(response.reason)
        result = response.json()
        response.close()
        if "error" in result:
            msg = result["error"]["message"]
            self.cookie = None
            self.session = None
            logger.error(msg)
        return False

    def get(self, url: str) -> dict:
        """
        :param url:
        :return: dict returned from url
        """
        self.connect()
        if url[0:4] != 'http':
            url = self.elan_url + url
        headers = {'Cookie': "AuthAPI={}".format(self.cookie)}
        logger.debug("trying to get {}".format(url))
        restart = False
        try:
            response = self.session.get(url=url, headers=headers)
        except:
            restart = True
        if restart or not self.check_response(response):
            self.connect(True)
            response = self.session.get(url=url, headers=headers)
            self.check_response(response)
        return response.json()

    def post(self, url: str, data=None) -> requests.Response:
        self.connect()
        full_url = "{}{}".format(self.elan_url, url)
        headers = {'Cookie': "AuthAPI={}".format(self.cookie)}
        logger.debug("trying to put {}".format(full_url))
        response = self.session.post(url=full_url, headers=headers, data=data)
        self.check_response(response)
        return response

    def put(self, url: str, data=None) -> requests.Response:
        self.connect()
        full_url = "{}{}".format(self.elan_url, url)
        headers = {'Cookie': "AuthAPI={}".format(self.cookie)}
        logger.debug("trying to put {}".format(full_url))
        response = self.session.put(url=full_url, headers=headers, data=data)
        self.check_response(response)
        return response

    @property
    def is_connected(self):
        return self.logged_in

    def connect(self, force: bool = False):
        if self.cookie and not force:
            return
        now = datetime.datetime.now()
        logger.debug(now.strftime("%Y-%m-%d %H:%M:%S trying to [re]connect"))
        self.get_login_cookie()

    async def ws_json(self) -> dict:
        self.connect()
        headers = {'Cookie': "AuthAPI={}".format(self.cookie)}
        data = ()
        logger.debug("checking ws")
        ws_host = self.elan_url.replace("http", "ws") + '/api/ws'
        async with websockets.connect(ws_host, extra_headers=headers, ping_timeout=1000) as ws:
            data = json.loads(await ws.recv())
        return data

    def ws_close(self):
        if self.ws:
            self.ws.close()
            self.ws = None
            self.cookie = None

    def get_login_cookie(self) -> None:
        name = "pan"
        key = '1a0af0924dfcfc49af82f0d1e4eb59a681339978'
        login_obj = {"name": name, 'key': key}
        if not self.session:
            self.session = requests.Session()
        if self.ws:
            self.ws.close()
            self.ws = None
        response = self.session.post(self.elan_url + '/login', data=login_obj)
        self.cookie = response.cookies['AuthAPI']
        logger.debug("Cookie: AuthAPI={}".format(self.cookie))
        # headers = {'Cookie': "AuthAPI=a{}".format(self.cookie)}
        # self.ws = websockets.connect(self.elan_url.replace("http","ws") + '/api/ws', extra_headers=headers
        #                                     ,ping_timeout=1000)
        logger.info("Socket connected")
