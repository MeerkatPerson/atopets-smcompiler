"""
Utilities for client communication with the trusted server.
You should not need to change this file.
"""

import json
import time
from typing import Union, Tuple, Any

import requests

import jsonpickle

# Imports for benchmarking
import timeit


def serialize_object(object: Any) -> bytes:

    return jsonpickle.encode(object).encode('utf-8')


def sanitize_url_param(url_param: Union[bytes, str]) -> str:
    """
    Sanitize URL parameter to be URL-safe.
    """
    if isinstance(url_param, bytes):
        # Mypy "dislikes" variable redefinition.
        url_param = url_param.decode("ASCII")  # type: ignore

    # %2F is indistinguishable from / due to WSGI standard.
    url_param = url_param.replace(r"%2F", "_").replace(r"%2f", "_")

    return url_param.replace("/", "_").replace("+", "-")  # type: ignore


class Communication:
    """
    Network communications with the server.

    Attributes:
        server_host: hostname of the server
        server_port: port of the server
        client_id: Identifier of this client
        poll_delay: delay between requests in seconds (default: 0.2 s)
        protocol: network protocol to use (default: "http")
    """

    def __init__(
            self,
            server_host: str,
            server_port: int,
            client_id: str,
            poll_delay: float = 0.2,
            protocol: str = "http"
    ):
        self.base_url = f"{protocol}://{server_host}:{server_port}"
        self.client_id = client_id
        self.poll_delay = poll_delay

        # for performance evaluation
        self.bytes_sent_smc_party = 0
        self.bytes_received_smc_party = 0
        self.bytes_sent_ttp = 0
        self.comp_cost_ttp = 0
        self.time_spent_sending = 0 # compute time spent waiting when sending messages
        self.time_spent_retrieving = 0 # compute time spent waiting when retrieving messages

    def send_private_message(
        self,
        receiver_id: str,
        label: str,
        message: Union[bytes, str]
    ) -> None:
        """
        Send a private message to the server.
        """

        # sending bytes, add to bytes_sent
        self.bytes_sent_smc_party = self.bytes_sent_smc_party + len(message)

        client_id_san = sanitize_url_param(self.client_id)
        receiver_id_san = sanitize_url_param(receiver_id)
        label_san = sanitize_url_param(label)

        url = f"{self.base_url}/private/{client_id_san}/{receiver_id_san}/{label_san}"
        print(f"POST {url}")

        # compute time spent sending message
        starttime_send_private_msg = timeit.default_timer() 

        requests.post(url, message)

        # add the time spent sending message to the corresponding metric
        self.time_spent_sending += (timeit.default_timer() - starttime_send_private_msg)

    def retrieve_private_message(
        self,
        label: str
    ) -> bytes:
        """
        Retrieve a private message from the server.
        """

        client_id_san = sanitize_url_param(self.client_id)
        label_san = sanitize_url_param(label)

        url = f"{self.base_url}/private/{client_id_san}/{label_san}"
        # We can either use a websocket, or do some polling, but websockets would require asyncio.
        # So we are doing polling to avoid introducing a new programming paradigm.

        # compute time spent retrieving message
        starttime_retrieve_private_msg = timeit.default_timer() 

        while True:
            print(f"GET  {url}")
            res = requests.get(url)
            if res.status_code == 200:

                # received bytes, add to bytes_received
                self.bytes_received_smc_party = self.bytes_received_smc_party + \
                    len(res.content)

                # add the time spent receiving message to the corresponding metric
                self.time_spent_retrieving += (timeit.default_timer() - starttime_retrieve_private_msg)

                return res.content

            time.sleep(self.poll_delay)

    def publish_message(
        self,
        label: str,
        message: Union[bytes, str]
    ) -> None:
        """
        Publish a message on the server.
        """

        # sending bytes, add to bytes_sent
        self.bytes_sent_smc_party = self.bytes_sent_smc_party + len(message)

        client_id_san = sanitize_url_param(self.client_id)
        label_san = sanitize_url_param(label)

        url = f"{self.base_url}/public/{client_id_san}/{label_san}"
        print(f"POST {url}")

        # compute time spent publishing message
        starttime_publish_msg = timeit.default_timer() 

        requests.post(url, message)

        # add the time spent publishing message to the corresponding metric
        self.time_spent_sending += (timeit.default_timer() - starttime_publish_msg)

    def retrieve_public_message(
        self,
        sender_id: str,
        label: str
    ) -> bytes:
        """
        Retrieve a public message from the server.
        """

        client_id_san = sanitize_url_param(self.client_id)
        sender_id_san = sanitize_url_param(sender_id)
        label_san = sanitize_url_param(label)

        url = f"{self.base_url}/public/{client_id_san}/{sender_id_san}/{label_san}"

        # We can either use a websocket, or do some polling, but websockets would require asyncio.
        # So we are doing polling to avoid introducing a new programming paradigm.

        # compute time spent retrieving public message
        starttime_retrieve_public_msg = timeit.default_timer() 

        while True:
            print(f"GET  {url}")
            res = requests.get(url)
            if res.status_code == 200:

                # received bytes, add to bytes_received
                self.bytes_received_smc_party = self.bytes_received_smc_party + \
                    len(res.content)

                # add the time spent retrieving public message to the corresponding metric
                self.time_spent_retrieving += (timeit.default_timer() - starttime_retrieve_public_msg)

                return res.content
            time.sleep(self.poll_delay)

    def retrieve_beaver_triplet_shares(
        self,
        op_id: str
    ) -> Tuple[int, int, int]:
        """
        Retrieve a triplet of shares generated by the trusted server.
        """

        client_id_san = sanitize_url_param(self.client_id)
        op_id_san = sanitize_url_param(op_id)

        url = f"{self.base_url}/shares/{client_id_san}/{op_id_san}"
        print(f"GET  {url}")

        # **********************************************************
        # Measure the ttp's computation time
        # Logic here is: the first client to retrieve their beaver triplets
        # from the ttp will cause the ttp to generate the triplets
        # and the respective shares = computation cost.

        # When we have obtained the ttp_comp_costs obtained from all
        # smc_party.comm objects, we will observe:
        # one of them will be much larger than the others; that
        # was the one that requested first and triggered the computation.
        # If we subtract the average of the remaining values (= good estimate
        # of network delay), we will get the ttp's computation time metric.

        # Start timer
        starttime = timeit.default_timer()

        res = requests.get(url)

        # Compute time taken
        time_taken = timeit.default_timer() - starttime

        self.comp_cost_ttp = time_taken

        # The time the ttp spent computing was also time spent waiting
        # for the network, so add to the corresponding metric as well
        self.time_spent_retrieving += time_taken

        # **********************************************************

        # receiving bytes from ttp, add to bytes received
        self.bytes_received_smc_party = self.bytes_received_smc_party + \
            len(res.content)

        # ttp is sending those bytes, add to bytes sent
        self.bytes_sent_ttp = self.bytes_sent_ttp + \
            len(res.content)

        return tuple(json.loads(res.text))  # type: ignore
