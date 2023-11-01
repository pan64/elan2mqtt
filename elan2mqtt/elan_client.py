import hashlib
import json
import logging
import time
from logging import Logger
import aiohttp
from aiohttp import ClientResponse, ClientWebSocketResponse

logger: Logger = logging.getLogger(__name__)


class ElanException(BaseException):
    pass


class ElanClient:

    def __init__(self):
        pass
        self.creds = {}
        self.elan_url = None
        self.logged_in = False
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        self.session = aiohttp.ClientSession(cookie_jar=cookie_jar)

    def setup(self):
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

    async def check_resp(self, resp: ClientResponse) -> None:
        if resp.status == 200:
            return
        msg = "status: {}, reason: {}".format(resp.status, resp.reason)
        self.logged_in = False
        raise ElanException(msg)

    async def get(self, url: str = "") -> dict:
        if url[0:4] != 'http':
            url = self.elan_url + url
        logger.debug("trying to GET '{}'".format(url))
        resp: ClientResponse = await self.session.get(url, timeout=3)
        if resp.status == 401:
            logging.warning("Status: 401, unauthorized")
            await self.login()
            resp = await self.session.get(url, timeout=3)

        await self.check_resp(resp)
        result = {}
        try:
            # result = await resp.json(content_type='text/html')
            result = await resp.json()
        except:
            logger.error(resp.text)
            pass
        return result

    async def post(self, url: str = "", data=None) -> None:
        resp: ClientResponse = await self.session.post(url = self.elan_url + url, data = data)
        await self.check_resp(resp)

    async def put(self, url: str = "", data=None) -> ClientResponse:
        logger.debug("trying to PUT '{}', '{}'".format(url, data))
        resp: ClientResponse = await self.session.put(url = url, data = data)
        await self.check_resp(resp)
        return resp

    async def login(self):
        logger.info("Get main/login page (to get cookies)")
        # dirty check if we are authenticated and to get session
        # await self.get('/')

        logger.info("Are we already authenticated? E.g. API check")
        # dirty check if we are authenticated and to get session
        # await self.get('/api')

        while True:
            # perform login
            # it should result in new AuthID cookie
            logger.info("Authenticating to eLAN")
            await self.post(url = '/login', data=self.creds)

            # Get list of devices
            # If we are not authenticated if will raise exception due to json
            # --> it triggers loop reset with new authenticating attempt
            logger.info("Getting eLan device list")
            try:
                await self.session.get(self.elan_url + '/api/devices', timeout=3)
                self.logged_in = True
                logger.info("logged in to eLAN")
                break
            except ElanException:
                time.sleep(1)

    async def ws_connect(self) -> ClientWebSocketResponse:
        logger.info("Connecting to websocket to get updates")
        websocket: ClientWebSocketResponse = await self.session.ws_connect(self.elan_url + '/api/ws', timeout=1, autoping=True)
        logger.info("Socket connected")
        return websocket

    @property
    def is_connected(self):
        return self.logged_in
