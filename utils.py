
import os
import json
import logging

import aiohttp

VOIP_API_USER = os.getenv('VOIP_API_USER', default="username")
VOIP_API_PASS = os.getenv('VOIP_API_PASS', default="password")
VOIP_API_HOST = os.getenv('VOIP_API_HOST', default="localhost")
VOIP_API_PORT = os.getenv('VOIP_API_PORT', default="8088")
VOIP_API_APP = os.getenv('VOIP_API_APP', "ivr-handler")

logger = logging.getLogger('ivr-handler')

async def __send_http_event(channel_id, data=None):
    """ HTTP Event Dispatcher to R3 - Steps Notification """
    session_id = ""
    URL = ""

    logger.info(
        f"[__send_http_event][{channel_id}] - {URL} - {data}")

    erc_headers = {
        "Content-Type": "application/json",
    }

    erc_headers["X-API-KEY"] = ""

    payload = dict()

    try:
        async with aiohttp.ClientSession(headers=erc_headers) as session:
            async with session.post(url=URL, data=json.dumps(payload), verify_ssl=False) as response:
                MSG_CONTENT = f"[SCPIVR][{session_id}][{channel_id}] - HTTP POST {URL} - {response.status}"
                logger.info(MSG_CONTENT)

                if response.status >= 400:
                    MSG_CONTENT = f"[SCPIVR][{session_id}][{channel_id}] - HTTP POST {URL} - {response.status}"
                    logger.error(MSG_CONTENT)
    except Exception:
        MSG_CONTENT = f"[SCPIVR][{session_id}][{channel_id}] - HTTP POST {URL} - TIMEOUT"
        logger.error(MSG_CONTENT)


async def play_media(channel_id=None, media='sound:beep'):
    URL = f"http://{VOIP_API_HOST}:{VOIP_API_PORT}/ari/channels/{channel_id}/play?media={media}&api_key={VOIP_API_USER}:{VOIP_API_PASS}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url=URL, verify_ssl=False) as response:
            pass

async def channel_hangup(channel_id):
    URL = f"http://{VOIP_API_HOST}:{VOIP_API_PORT}/ari/channels/{channel_id}?api_key={VOIP_API_USER}:{VOIP_API_PASS}"
    async with aiohttp.ClientSession() as session:
        async with session.delete(url=URL, verify_ssl=False) as response:
            pass

