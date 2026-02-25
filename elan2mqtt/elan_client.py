import asyncio
import datetime
import hashlib

import logging
from typing import Optional, Dict, Any

import aiologic
from config import Config

import httpx

logger: logging.Logger = logging.getLogger(__name__)


class ElanException(Exception):
    pass


class ElanClient:
    lock = aiologic.Condition()
    cookie_dict = None  # Shared dict for process pool

    def __init__(self):

        self.creds = {}
        self.elan_url: Optional[str] = None
        self.logged_in: bool = False
        self.cookie: Optional[str] = None
        self.config: Optional[Config] = None
        self.client: Optional[httpx.AsyncClient] = None

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
            # Close existing client if present
            if self.client is not None:
                asyncio.create_task(self.client.aclose())
            self.client = httpx.AsyncClient()

            logger.info("elan url: '{}', user: '{}'".format(self.elan_url, elan_user))
        except (KeyError, TypeError) as e:
            logger.error("Invalid configuration format: {}".format(str(e)))
            raise ValueError("Invalid eLan configuration") from e
        except Exception as e:
            logger.error("Error setting up eLan client: {}".format(str(e)))
            raise

    async def cleanup(self) -> None:
        """Cleanup resources"""
        if self.client is not None:
            try:
                await self.client.aclose()
                logger.debug("HTTP client closed")
            except Exception as e:
                logger.error("Error closing HTTP client: {}".format(str(e)))

    def check_response(self, response: httpx.Response) -> bool:
        """
        check if response is acceptable
        :param response:
        :return: true: ok, false: error
        """

        logger.debug("check response code: {}, text: {}".format(response.status_code, response.text[:100]))
        if response.is_success:
            return True
        try:
            result = response.json()
            if "error" in result:
                msg = result["error"]["message"]
                self.cookie = None
                # Sync cookie invalidation to shared dict
                if self.cookie_dict is not None:
                    self.cookie_dict['cookie'] = None
                logger.error("eLan API error: {}".format(msg))
        except (ValueError, KeyError) as e:
            logger.error("Invalid response format: {}".format(str(e)))
        return False

    async def get(self, url: str) -> Dict[str, Any]:
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
                await self.connect(reconnect)
                headers = {"Cookie": "AuthAPI={}".format(self.cookie)}
                response = await self.client.get(url=url, headers=headers, timeout=self.config['internal']['constants']['HTTP_TIMEOUT'])
                if self.check_response(response):
                    return response.json()
                logger.debug("invalid response, retrying")
            except httpx.HTTPError as e:
                logger.error("HTTP request failed (retry #{}): {}".format(i, str(e)))
            except (ValueError, KeyError) as e:
                logger.error("Response parsing failed (retry #{}): {}".format(i, str(e)))
            except Exception as e:
                logger.error("Unexpected error (retry #{}): {}".format(i, str(e)))
            reconnect = True
        return {}

    async def post(self, url: str, data: Optional[str] = None) -> httpx.Response:
        """
        post a message to elan
        :param url: device api endpoint
        :param data: command to rend to the device
        """
        await self.connect()
        if url[0:4] != 'http':
            url = self.elan_url + url
        headers = {'Cookie': "AuthAPI={}".format(self.cookie)}
        logger.debug("trying to post {}".format(url))
        response = await self.client.post(url=url, headers=headers, data=data, timeout=self.config['internal']['constants']['HTTP_TIMEOUT'])
        self.check_response(response)
        return response

    async def put(self, url: str, data: Optional[str] = None) -> str:
        """
        put a message to elan
        :param url: device api endpoint
        :param data: command to rend to the device
        """
        await self.connect()
        if url[0:4] != 'http':
            url = self.elan_url + url
        headers = {'Cookie': "AuthAPI={}".format(self.cookie)}
        logger.debug("trying to put {}".format(url))
        response = await self.client.put(url=url, headers=headers, data=data, timeout=self.config['internal']['constants']['HTTP_TIMEOUT'])
        self.check_response(response)
        return response.text

    async def connect(self, force: bool = False) -> None:
        """
        connect to the elan host and get a valid cookie
        :param force: get new cookie unconditionally
        """
        try:
            async with self.lock:
                if self.cookie and not force:
                    logger.debug("eLan has been already connected")
                    return
                now = datetime.datetime.now()
                logger.debug(now.strftime("%Y-%m-%d %H:%M:%S trying to [re]connect"))
                if self.lock.lock.count < 2:
                    logger.debug("first lock, connecting")
                    self.cookie = None

                    await self.get_login_cookie()
                    self.lock.notify_all()
                else:
                    logger.debug("waiting for the [re]connect to complete")
                    await self.lock.wait(timeout=self.config['internal']['constants']['LOCK_WAIT_TIMEOUT'])
        except httpx.HTTPError as e:
            logger.error("Network error during eLan connection: {}".format(str(e)))
            raise ElanException("Network connection failed") from e
        except (ValueError, KeyError) as e:
            logger.error("Authentication error: {}".format(str(e)))
            raise ElanException("Authentication failed") from e
        except Exception as e:
            logger.error("Unexpected error during eLan connection: {}".format(str(e)))
            raise ElanException("Connection failed") from e


    async def get_login_cookie(self) -> None:
        name = self.creds.get("name")
        key = self.creds.get("key")
        login_obj = {"name": name, 'key': key}
        try:
            response = await self.client.post(self.elan_url + '/login', data=login_obj, timeout=self.config['internal']['constants']['HTTP_TIMEOUT'])
            self.check_response(response)
        except httpx.HTTPError as e:
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

        # Sync cookie to shared dict for process pool
        if self.cookie_dict is not None:
            self.cookie_dict['cookie'] = self.cookie

        logger.info("eLan is connected")
