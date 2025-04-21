import asyncio
import datetime
import hashlib
import json
import logging
from typing import Optional

from websockets import InvalidStatus, ConnectionClosedError

from config import Config


import requests
from websockets.asyncio.client import connect as ws_connect
from requests import Session

logger: logging.Logger = logging.getLogger(__name__)

class ElanException(BaseException):
    pass

class ElanClient:
#    lock = asyncio.Lock()

    def __init__(self):

        self.creds = {}
        self.elan_url: Optional[str] = None
        self.logged_in: bool = False
        self.session: Optional[Session] = None
        self.cookie: Optional[str] = None

    def setup(self, data: Config) -> None:
        """configure this elan client"""
        try:
            logger.info("loading config file")
            self.elan_url = data["options"]["eLanURL"]
            elan_user = data["options"]["username"]
            elan_pass = data["options"]["password"]
            key = hashlib.sha1(elan_pass.encode('utf-8')).hexdigest()
            self.creds = {
                'name': elan_user,
                'key': key
            }

            logger.info("elan url: '{}', user: '{}', pass: '{}'".format(self.elan_url, elan_user, elan_pass))
        except BaseException as be:
            logger.error("read config exception occurred: " + str(be))
            logger.error(be, exc_info=True)
            raise

    def check_response(self, response: requests.Response) -> bool:
        """
        check if response is acceptable
        :param response:
        :return: true: ok, false: error
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
        get data from the given address
        :param url: device api endpoint
        :return: dict returned from url
        """
        if url[0:4] != 'http':
            url = self.elan_url + url
        headers = {'Cookie': "AuthAPI={}".format(self.cookie)}
        logger.debug("trying to get {}".format(url))

        reconnect = False
        for i in range(3):
            try:
                self.connect(reconnect)
                response = self.session.get(url=url, headers=headers)
                if self.check_response(response):
                    return response.json()
            except BaseException as bee:
                logger.error("trying to get failed (retrying #{}): {}".format(i, str(bee)))
            reconnect = True
        return {}

    def post(self, url: str, data=None) -> requests.Response:
        """
        post a message to elan
        :param url: device api endpoint
        :param data: command to rend to the device
        """
        self.connect()
        if url[0:4] != 'http':
            url = self.elan_url + url
        headers = {'Cookie': "AuthAPI={}".format(self.cookie)}
        logger.debug("trying to post {}".format(url))
        response = self.session.post(url=url, headers=headers, data=data)
        self.check_response(response)
        return response

    def put(self, url: str, data=None) -> str: # requests.Response:
        """
        put a message to elan
        :param url: device api endpoint
        :param data: command to rend to the device
        """
        self.connect()
        if url[0:4] != 'http':
            url = self.elan_url + url
        headers = {'Cookie': "AuthAPI={}".format(self.cookie)}
        logger.debug("trying to put {}".format(url))
        response = self.session.put(url=url, headers=headers, data=data)
        self.check_response(response)
        return response.text

    @property
    def is_connected(self):
        """check if the elan host is online"""
        return self.logged_in

    def connect(self, force: bool = False):
        """
        connect to the elan host and get a valid cookie
        :param force: get new cookie unconditionally
        """
        if self.cookie and not force:
            return
        if self.session:
            self.session.close()
        self.session = None
        self.cookie = None
        now = datetime.datetime.now()
        logger.debug(now.strftime("%Y-%m-%d %H:%M:%S trying to [re]connect"))
        try:
        #    async with self.lock:
                self.get_login_cookie()
        except BaseException as exc:
            logger.error("cannot login to elan {}".format(str(exc)))
            #print(f"Current {e.__class__}: {e}")
            #print(f"Nested {e.__cause__.__class__}:{e.__cause__}")
            while exc:
                e = exc
                logger.error("Exc: {}:{}".format(e.__class__.__name__,str(e)))
                exc = e.__cause__
            raise ElanException from exc

    async def ws_json(self) -> dict:
        """get a message on websocket"""
        self.connect()
        # name = "pan"
        # key = '1a0af0924dfcfc49af82f0d1e4eb59a681339978'
        headers = {'Cookie': "AuthAPI={}".format(self.cookie)}
        #headers = {"Authorization": f"Bearer {key}"}
        ws_host = self.elan_url.replace("http://", "ws://") + '/api/ws'
        logger.debug("checking ws at {}".format(ws_host))
        try:
            async with ws_connect(ws_host, additional_headers=headers, ping_timeout=1000) as ws:
                data = json.loads(await ws.recv())
                logger.debug("received {}".format(data))
                return data
        except asyncio.exceptions.CancelledError as ece:
            logger.error("websocket cancelled: {}".format(str(ece)))
            self.cookie = None
            # raise
        except InvalidStatus as ise:
            logger.error("websocket invalid status: {}".format(str(ise)))
            self.cookie = None
        except ConnectionClosedError as cce:
            logger.error("websocket connection closed: {}".format(str(cce)))
            self.cookie = None
        except BaseException as exc:
            logger.error("websocket error: {}".format(str(exc)))
            self.cookie = None
            raise
        await asyncio.sleep(0)
        return {}

    def get_login_cookie(self) -> None:
        name = "pan"
        key = '1a0af0924dfcfc49af82f0d1e4eb59a681339978'
        login_obj = {"name": name, 'key': key}
        if not self.session:
            self.session = Session()
        try:
            response = self.session.post(self.elan_url + '/login', data=login_obj)
        except BaseException as ose:
            logger.error("login error: {}".format(str(ose)))
            self.session.close()
            self.session = None
            raise
        self.cookie = response.cookies['AuthAPI']
        logger.debug("Cookie: AuthAPI={}".format(self.cookie))
        # headers = {'Cookie': "AuthAPI=a{}".format(self.cookie)}
        # self.ws = websockets.connect(self.elan_url.replace("http","ws") + '/api/ws', extra_headers=headers
        #                                     ,ping_timeout=1000)
        logger.info("eLan is connected")
