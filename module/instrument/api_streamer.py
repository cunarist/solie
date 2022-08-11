import json
import time
import logging

import websocket

from module import thread_toss


class ApiStreamer:
    # https://github.com/websocket-client/websocket-client/issues/580

    _instances = []
    _is_active = True

    def __init__(self, url, when_received):
        self._instances.append(self)

        self._url = url
        self._when_received = when_received
        self._websocket_app = None
        self._is_closed = False

        if url != "":
            self._create_websocket_app()

    def update_url(self, url):
        did_change = self._url != url
        before_url = self._url
        self._url = url
        if self._websocket_app is None:
            self._create_websocket_app()
        elif did_change:
            self._websocket_app.close()
            text = f"Websocket address replaced from {before_url} to {url}"
            logger = logging.getLogger("solsol")
            logger.info(text)

    @classmethod
    def close_all_forever(cls):
        cls._is_active = False
        for instance in cls._instances:
            if isinstance(instance._websocket_app, websocket.WebSocketApp):
                instance._websocket_app.close()

    def _create_websocket_app(self):
        def on_message(_, message):
            received = json.loads(message)
            try:
                # not using thread pool
                # because thread pool is even slower with frequent messages
                self._when_received(received=received)
            except Exception:
                logger = logging.getLogger("solsol")
                logger.exception(
                    "Exception occured from a streamer\nBelow is the received data\n"
                    + json.dumps(received, indent=4)
                )

        def on_close(*args):
            if self._is_active:
                time.sleep(10)
                self._create_websocket_app()

        websocket_app = websocket.WebSocketApp(
            url=self._url,
            on_message=on_message,
            on_close=on_close,
        )
        self._websocket_app = websocket_app

        # https://websocket-client.readthedocs.io/en/latest/examples.html?highlight=dispatcher#dispatching-multiple-websocketapps

        def job():
            websocket_app.run_forever(skip_utf8_validation=True)

        thread_toss.apply_async(job)
