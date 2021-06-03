#!/usr/bin/env python
import logging
import json
import os
from logging.handlers import TimedRotatingFileHandler
import asyncio

import websockets

IVR_EMAIL_FOR_ALERT = os.getenv('IVR_EMAIL_FOR_ALERT')
IVR_ALERT_EMAIL_SUBJECT = os.getenv('IVR_ALERT_EMAIL_SUBJECT')

LOG_LEVEL = os.getenv('IVR_LOG_LEVEL')
LOG_FORMAT = '%(asctime)s.%(msecs)03d %(name)-12s %(levelname)-8s %(message)s'
DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'
PATH_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(PATH_DIR, 'logs/ivr-handler.log')
LOG_WHEN_ROTATE = 'midnight'
LOG_COUNT = 5

logging.basicConfig(level=LOG_LEVEL,
                    format=LOG_FORMAT,
                    handlers=[
                        TimedRotatingFileHandler(
                            LOG_FILE,
                            when=LOG_WHEN_ROTATE,
                            backupCount=LOG_COUNT
                        )],
                    datefmt='%Y-%m-%dT%H:%M:%S')
logger = logging.getLogger('ivr-handler')


# VoIP Engine API
VOIP_API_USER = os.getenv('VOIP_API_USER', default="username")
VOIP_API_PASS = os.getenv('VOIP_API_PASS', default="password")
VOIP_API_HOST = os.getenv('VOIP_API_HOST', default="localhost")
VOIP_API_PORT = os.getenv('VOIP_API_PORT', default="8088")
VOIP_API_APP = os.getenv('VOIP_API_APP', "ivr-handler")

API_SPCIVR_HOST = os.getenv('API_SPCIVR_HOST')

ivr_tree = {
    "1": {
        "1": {"action": "Goto", "params": "Queue 1.1"},
        "2": {"action": "ForwardNumber", "params": "1.2"},
        "3": {
            "1": {"action": "Goto", "params": "Queue 1.3.1"},
            "9": {"action": "Goto", "params": "Queue 1.3.9"},
            "*": {"action": "PreviousMenu", "params": "*"}
        },
        "*": {"action": "PreviousMenu", "params": "*"}
    },
    "2": {"action": "ForwardNumber", "params": "2.0"},
    "*": {"action": "RepeatOptions", "params": "*"}
}

state = {}
URI = f"ws://{VOIP_API_HOST}:{VOIP_API_PORT}/ari/events?api_key={VOIP_API_USER}:{VOIP_API_PASS}&app={VOIP_API_APP}"

class VoIPWS:
    def __init__(self):
        pass

    async def startup(self):
        self.event_queue = asyncio.Queue()
        self.notification_queue = asyncio.Queue()
        await self.connect_websocket()

        consumer_task = asyncio.create_task(
            self.consumer_handler()
        )

        producer_task = asyncio.create_task(
            self.producer_handler()
        )

        notifier_task = asyncio.create_task(
            self.notifier_handler()
        )

        done, pending = await asyncio.wait(
            [consumer_task, producer_task, notifier_task],
            return_when=asyncio.ALL_COMPLETED
        )

        for task in pending:
            task.cancel()

    async def connect_websocket(self):
        try:
            self.connection = await websockets.client.connect(URI)
        except:
            pass

    async def consumer_handler(self):
        async for message in self.connection:
            message_json = json.loads(message)
            await self.consumer(message_json)

    async def consumer(self, message):
        self.event_queue.put_nowait(message)

    async def producer_handler(self):
        while True:
            message = await self.producer()
            await self.ari_event_handler(message)

    async def producer(self):
        event = await self.event_queue.get()
        self.event_queue.task_done()
        return event

    async def notifier_handler(self):
        while True:
            notification = await self.notifier()
            await self.notification_handler(notification)

    async def notifier(self):
        notification = await self.notification_queue.get()
        self.notification_queue.task_done()
        return notification

    async def notification_handler(notification):
        print(notification)

    async def init_handler(self, event):
        """ Stasis Event Handler """

        channel_id = event.get('channel', {}).get('id', None)
        caller_id = event.get('channel', {}).get(
            'caller', {}).get('number', None)
        state[channel_id] = {
            "current": ivr_tree,
            "original": ivr_tree,
            "steps": []
        }
        print(f"Call from [{caller_id}] with channel_id [{channel_id}]")

    async def end_handler(self, event):
        """ Stasis Event Handler """

        channel_id = event.get('channel', {}).get('id', None)
        caller_id = event.get('channel', {}).get(
            'caller', {}).get('number', None)
        print(f"Call end [{caller_id}] with channel_id [{channel_id}]")

    async def channel_hangup_handler(self, event):
        """ ChannelDestroyed and ChannelHangupRequest Event Handler """

        channel_id = event.get('channel', {}).get('id', None)
        logger.info(f"[channel_hangup_handler][{channel_id}] - {event}")

    async def dtmf_handler(self, event):
        """ ChannelDtmfReceived Event Handler """

        channel_id = event.get('channel', {}).get('id', None)
        digit = event.get('digit')

        print(f"{channel_id} - DTMF {digit} received")

        # next_step = state.get(channel_id, {}).get('current', {}).get(digit, {})

        # if next_step:
        #     steps = state.get(channel_id, {}).get('steps', [])
        #     steps.append(digit)
        #     state[channel_id] = {
        #         "current": next_step,
        #         "original": ivr_tree,
        #         "steps": steps
        #     }
        #     print(f"Current state for {channel_id}", state[channel_id])
        #     if 'action' in next_step:
        #         print(next_step.get("action"), next_step.get("params") )
        # else:
        #     print("Already at the Bottom...")
        #     return

    def user_event_handler(self, event):
        """ ChannelUserEvent Event Handler """

        user_event = event.get('userevent')
        payload = user_event.get('payload', {})
        channel_id = payload.get('channel_id', None)
        handler_dispatcher = {
            "start_capturing": lambda: print(user_event, payload, channel_id),
            "cancel_process": lambda: print(user_event, payload, channel_id)
        }
        dispatcher = handler_dispatcher(user_event.get(
            'action', lambda: print(user_event, payload, channel_id)))
        dispatcher()

    async def default_handler(self, event):
        print(event)

    async def ari_event_handler(self, event):
        """ __ALL__ Event Handler """

        handler_dispatcher = {
            "StasisStart": self.init_handler,
            "ChannelDtmfReceived": self.dtmf_handler,
            "ChannelUserevent": self.user_event_handler,
            "ChannelDestroyed": self.channel_hangup_handler,
            "ChannelHangupRequest": self.channel_hangup_handler,
            "StasisEnd": self.end_handler,
        }

        await handler_dispatcher.get(event["type"], self.default_handler)(event)


if __name__ == "__main__":
    print('***********************')
    print(f'*** Starting App {VOIP_API_APP}... ')
    print(f'*** HOST: {VOIP_API_HOST} ')
    print(f'*** PORT: {VOIP_API_PORT} ')
    print('***********************')

    voip_ws = VoIPWS()
    asyncio.run(voip_ws.startup())
