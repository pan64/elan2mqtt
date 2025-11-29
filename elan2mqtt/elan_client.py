import asyncio
import datetime
import hashlib
import json
import logging
from collections.abc import Callable
from typing import Optional, Dict, Any

import aiologic
from websockets import InvalidStatus, ConnectionClosedError
from config import Config


from websockets.asyncio.client import connect as ws_connect
import requests

logger: logging.Logger = logging.getLogger(__name__)

class ElanException(BaseException):
    pass

class ElanClient:
    lock = aiologic.Condition()

    def __init__(self):

        self.creds = {}
        self.elan_url: Optional[str] = None
        self.logged_in: bool = False
        self.cookie: Optional[str] = None
        self.config: Optional[Config] = None

    def setup(self, data: Config) -> None:
        """configure this elan client"""
        try:
            logger.info("loading config file")
            self.config = data
            self.elan_url = data["options"]["eLanURL"]
            elan_user = data["options"]["username"]
            elan_pass = data["options"]["password"]
            key = hashlib.sha1(elan_pass.encode('utf-8')).hexdigest()
            self.creds = {
                'name': elan_user,
                'key': key
            }

            logger.info("elan url: '{}', user: '{}', pass: '{}'".format(self.elan_url, elan_user, elan_pass))
        except (KeyError, TypeError) as e:
            logger.error("Invalid configuration format: {}".format(str(e)))
            raise ValueError("Invalid eLan configuration") from e
        except Exception as e:
            logger.error("Error setting up eLan client: {}".format(str(e)))
            raise

    def check_response(self, response: requests.Response) -> bool:
        """
        check if response is acceptable
        :param response:
        :return: true: ok, false: error
        """

        logger.debug("check response code: {}, reason: {}".format(response.status_code, response.reason))
        if response.ok:
            return True
        try:
            result = response.json()
            if "error" in result:
                msg = result["error"]["message"]
                self.cookie = None
                logger.error("eLan API error: {}".format(msg))
        except (ValueError, KeyError) as e:
            logger.error("Invalid response format: {}".format(str(e)))
        finally:
            response.close()
        return False

    def get(self, url: str) -> Dict[str, Any]:
        """
        get data from the given address
        :param url: device api endpoint
        :return: dict returned from url
        """
        if url[0:4] != 'http':
            url = self.elan_url + url
        logger.debug("trying to get {}".format(url))

        reconnect = False
        for i in range(3):
            try:
                self.connect(reconnect)
                headers = {"Cookie": "AuthAPI={}".format(self.cookie)}
                response = requests.get(url=url , headers=headers, timeout=self.config['internal']['constants']['HTTP_TIMEOUT'])
                if self.check_response(response):
                    return response.json()
                logger.debug("invalid response, retrying")
            except requests.RequestException as e:
                logger.error("HTTP request failed (retry #{}): {}".format(i, str(e)))
            except (ValueError, KeyError) as e:
                logger.error("Response parsing failed (retry #{}): {}".format(i, str(e)))
            except Exception as e:
                logger.error("Unexpected error (retry #{}): {}".format(i, str(e)))
            reconnect = True
        return {}

    def post(self, url: str, data: Optional[str] = None) -> requests.Response:
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
        response = requests.post(url=url, headers=headers, data=data)
        self.check_response(response)
        return response

    def put(self, url: str, data: Optional[str] = None) -> str: # requests.Response:
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
        response = requests.put(url=url, headers=headers, data=data)
        self.check_response(response)
        return response.text


    def connect(self, force: bool = False) -> None:
        """
        connect to the elan host and get a valid cookie
        :param force: get new cookie unconditionally
        """
        try:
            with self.lock:
                if self.cookie and not force:
                    logger.debug("eLan has been already connected")
                    return
                now = datetime.datetime.now()
                logger.debug(now.strftime("%Y-%m-%d %H:%M:%S trying to [re]connect"))
                if self.lock.lock.count < 2:
                    logger.debug("first lock, connecting")
                    self.cookie = None

                    self.get_login_cookie()
                    self.lock.notify_all()
                else:
                    logger.debug("waiting for the [re]connect to complete")
                    self.lock.wait(timeout=self.config['internal']['constants']['LOCK_WAIT_TIMEOUT'])
        except requests.RequestException as e:
            logger.error("Network error during eLan connection: {}".format(str(e)))
            raise ElanException("Network connection failed") from e
        except (ValueError, KeyError) as e:
            logger.error("Authentication error: {}".format(str(e)))
            raise ElanException("Authentication failed") from e
        except Exception as e:
            logger.error("Unexpected error during eLan connection: {}".format(str(e)))
            raise ElanException("Connection failed") from e

    async def ws_listen(self, publisher: Callable) -> None:
        """get a message on websocket"""
        self.connect()
        headers = {'Cookie': "AuthAPI={}".format(self.cookie)}
        # headers = {"AuthAPI": self.cookie}
        ws_host = self.elan_url.replace("http://", "ws://") + '/api/ws'
        logger.debug("checking ws at {}".format(ws_host))
        try:
            ping_timeout = self.config['internal']['constants']['WEBSOCKET_PING_TIMEOUT']
            recv_timeout = self.config['internal']['constants']['WEBSOCKET_RECV_TIMEOUT']
            async for ws in ws_connect(ws_host, additional_headers=headers, ping_timeout=ping_timeout):
            # async for ws in ws_connect(ws_host, ping_timeout=ping_timeout):

                data: dict = json.loads(await asyncio.wait_for(ws.recv(), timeout=recv_timeout))
                logger.debug("received {}".format(data))
                await publisher(data['device'])
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
        except TimeoutError as toe:
            logger.error("websocket timeout error: {}".format(str(toe)))
            self.cookie = None
        except KeyError:
            return
        except BaseException as exc:
            logger.error("websocket error: {}".format(str(exc)))
            self.cookie = None
            raise
        await asyncio.sleep(0)


    def get_login_cookie(self) -> None:
        name = self.creds.get("name")
        key = self.creds.get("key")
        login_obj = {"name": name, 'key': key}
        try:
            response = requests.post(self.elan_url + '/login', data=login_obj, timeout=self.config['internal']['constants']['HTTP_TIMEOUT'])
            self.check_response(response)
        except requests.RequestException as e:
            logger.error("Network error during login: {}".format(str(e)))
            raise
        except KeyError as e:
            logger.error("Missing authentication cookie: {}".format(str(e)))
            raise
        except Exception as e:
            logger.error("Login failed: {}".format(str(e)))
            raise
        self.cookie = response.cookies['AuthAPI']
        logger.debug("Cookie: AuthAPI={}".format(self.cookie))
        # headers = {'Cookie': "AuthAPI=a{}".format(self.cookie)}
        # self.ws = websockets.connect(self.elan_url.replace("http","ws") + '/api/ws', extra_headers=headers
        #                                     ,ping_timeout=1000)

        logger.info("eLan is connected")
