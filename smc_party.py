"""
Implementation of an SMC client.

MODIFY THIS FILE.
"""
# You might want to import more classes if needed.

import ast

import collections
import json
from typing import (
    Dict,
    Set,
    Tuple,
    Union,
    Any
)

from communication import Communication
from expression import (
    Expression,
    Secret,
    AddOp,
    SubOp,
    MultOp,
    Scalar, SubOp
)
from protocol import ProtocolSpec
from secret_sharing import(
    reconstruct_secret,
    share_secret,
    Share,
)

import requests

from server import send_private_message

import jsonpickle

# Imports for benchmarking
import timeit
from statistics import mean

import sys
sys.setrecursionlimit(10000)

# Feel free to add as many imports as you want.


def serialize_object(object: Any) -> bytes:

    return jsonpickle.encode(object).encode('utf-8')


def deserialize_object(serialized_object: bytes) -> Any:

    return jsonpickle.decode(serialized_object.decode('utf-8'))


class SMCParty:
    """
    A client that executes an SMC protocol to collectively compute a value of an expression together
    with other clients.

    Attributes:
        client_id: Identifier of this client
        server_host: hostname of the server
        server_port: port of the server
        protocol_spec (ProtocolSpec): Protocol specification
        value_dict (dict): Dictionary assigning values to secrets belonging to this client.
    """

    def __init__(
        self,
        client_id: str,
        server_host: str,
        server_port: int,
        protocol_spec: ProtocolSpec,
        value_dict: Dict[Secret, int]  # Has the form: {alice_secret: 3}
    ):
        self.comm = Communication(server_host, server_port, client_id)
        self.client_id = client_id
        self.protocol_spec = protocol_spec
        self.value_dict = value_dict
        self.shares_dict = dict()  # this will store own shares of own secrets

    def run(self) -> int:
        """
        The method the client use to do the SMC.
        """

        # Make a deep copy of the participant_ids in protocol_spec so we don't modify the original list
        # when removing self from peer_ids!!!
        # This way, we can still use self.protocol_spec.participant_ids when deciding whether to add a constant

        self.peer_ids = []

        for participant_id in self.protocol_spec.participant_ids:

            self.peer_ids.append(participant_id)

        self.peer_ids.remove(self.client_id)

        # Map the secrets of self to lists of shares
        # (produces List[List[Share]])
        mapped_secrets = []

        for sec in self.value_dict.values():

            shares_list = share_secret(
                sec, len(self.protocol_spec.participant_ids))

            mapped_secrets.append(shares_list)

        print(
            f'Secrets of client with id {self.client_id} as lists of shares: {mapped_secrets}')

        # From each List[Share], take the first element and assign to self

        self_secrets_keys = list(self.value_dict.keys())

        for k, share_list in enumerate(mapped_secrets):

            own_share = share_list.pop()

            self.shares_dict.update({self_secrets_keys[k]: own_share})

        # (I) Retrieve the IDs of other participants & send own secret to all of them

        for i, participant_id in enumerate(self.peer_ids):

            for j, secret_key in enumerate(self_secrets_keys):

                self.comm.send_private_message(
                    participant_id, str(secret_key.id), serialize_object(mapped_secrets[j][i]))

                print(
                    f'Client with ID {self.client_id} sent share of secret with id {secret_key.id} to {participant_id}')

        local_comp_result = self.process_expression(self.protocol_spec.expr)

        # (III.) Send sum of received shares

        # Publish sum of received shares

        label_comp_res = f'{self.client_id}-res'

        comp_res = []  # list which will store

        comp_res.append(local_comp_result)

        # message should be bytes or string to conform to communication class API
        comp_res_to_send = serialize_object(local_comp_result)

        self.comm.publish_message(label_comp_res, comp_res_to_send)

        print(
            f'Client with ID {self.client_id} published the following computation result: {local_comp_result}')

        # (V). Retrieve the values computed by the others from the TTP

        for sender_id in self.peer_ids:

            recv_res_label = f'{sender_id}-res'

            message_received = self.comm.retrieve_public_message(
                sender_id, recv_res_label)

            # decode from bytes
            message_decoded = deserialize_object(message_received)

            print(
                f'Client with id {self.client_id} received computation result: {message_decoded} from participant {sender_id}')

            # add the received item to the value dict
            comp_res.append(message_decoded)

        # (VI). Reconstruct Secret

        return reconstruct_secret(comp_res)

    # The instrumented version of run; returns a dictionary with computation and communication
    # cost as well as the computation result
    def run_instrumented(self) -> Tuple[int, Dict[str, int]]:
        """
        The method the client use to do the SMC.
        """

        # Measure time taken overall
        starttime_overall = timeit.default_timer()

        # Set up a dictionary which will contain the metrics
        metrics = dict()

        # Map the secrets of self to lists of shares
        # (produces List[List[Share]])
        mapped_secrets = []

        # Make a deep copy of the participant_ids in protocol_spec so we don't modify the original list
        # when removing self from peer_ids!!!
        # This way, we can still use self.protocol_spec.participant_ids when deciding whether to add a constant

        self.peer_ids = []

        for participant_id in self.protocol_spec.participant_ids:

            self.peer_ids.append(participant_id)

        self.peer_ids.remove(self.client_id)

        # ***********************************************************
        # (1) First COMP metric: computation time for sharing secrets

        computation_cost_sharing = []

        for sec in self.value_dict.values():

            # Start timer
            starttime_sharing = timeit.default_timer()

            shares_list = share_secret(
                sec, len(self.protocol_spec.participant_ids))

            # Compute time taken
            time_taken_sharing = timeit.default_timer() - starttime_sharing

            # append result
            computation_cost_sharing.append(time_taken_sharing)

            mapped_secrets.append(shares_list)

        # append our first metric: average time for sharing each of this party's secrets
        metrics.update(
            {'comp_time_sharing': mean(computation_cost_sharing)})
        # ***********************************************************

        print(
            f'Secrets of client with id {self.client_id} as lists of shares: {mapped_secrets}')

        # From each List[Share], take the first element and assign to self

        self_secrets_keys = list(self.value_dict.keys())

        for k, share_list in enumerate(mapped_secrets):

            own_share = share_list.pop()

            self.shares_dict.update({self_secrets_keys[k]: own_share})

        # (I) Retrieve the IDs of other participants & send own secret to all of them

        # Make a deep copy of the participant_ids in protocol_spec so we don't modify the original list
        # when removing self from peer_ids!!!
        # This way, we can still use self.protocol_spec.participant_ids when deciding whether to add a constant

        self.peer_ids = []

        for participant_id in self.protocol_spec.participant_ids:

            self.peer_ids.append(participant_id)

        self.peer_ids.remove(self.client_id)

        for i, participant_id in enumerate(self.peer_ids):

            for j, secret_key in enumerate(self_secrets_keys):

                self.comm.send_private_message(
                    participant_id, str(secret_key.id), serialize_object(mapped_secrets[j][i]))

                print(
                    f'Client with ID {self.client_id} sent share of secret with id {secret_key.id} to {participant_id}')

        # record the time spent sending up to now so we can use it later for correcting the time spent processing
        # an expression

        time_spent_sending_shares = self.comm.time_spent_sending

        # ***********************************************************
        # (2) 2nd COMP metric: computation time for processing expression

        # Start timer
        starttime_processing = timeit.default_timer()

        local_comp_result = self.process_expression(self.protocol_spec.expr)

        # Compute time taken
        time_taken_processing = timeit.default_timer() - starttime_processing

        # append our 2nd metric: average time for processing expression
        # It needs to be corrected for time spent sending & retrieving messages:
        # (I.) to correct it by the time spent retrieving messages, we can simply
        #      subtract self.comm.time_spent_retrieving (up to this point in the protocol, 
        #      the only instances of retrieving messages occur in process_expression, when 
        #      retrieving a secret share or beaver shares)
        # (II.) to correct it for the time spent publishing messages during process_expression, we 
        #       subtract (self.comm.time_spent_sending - time_spent_sending_shares)
        # maybe all of this is nitpicking, but we want to be precise :)

        comp_time_processing = (time_taken_processing - self.comm.time_spent_retrieving - (self.comm.time_spent_sending - time_spent_sending_shares))

        metrics.update({'comp_time_processing': comp_time_processing})
        # ***********************************************************

        # (III.) Send sum of received shares

        # Publish sum of received shares

        label_comp_res = f'{self.client_id}-res'

        comp_res = []  # list which will store

        comp_res.append(local_comp_result)

        # message should be bytes or string to conform to communication class API
        comp_res_to_send = serialize_object(local_comp_result)

        self.comm.publish_message(label_comp_res, comp_res_to_send)

        print(
            f'Client with ID {self.client_id} published the following computation result: {local_comp_result}')

        # (V). Retrieve the values computed by the others from the TTP

        for sender_id in self.peer_ids:

            recv_res_label = f'{sender_id}-res'

            message_received = self.comm.retrieve_public_message(
                sender_id, recv_res_label)

            # decode from bytes
            message_decoded = deserialize_object(message_received)

            print(
                f'Client with id {self.client_id} received computation result: {message_decoded} from participant {sender_id}')

            # add the received item to the value dict
            comp_res.append(message_decoded)

        # (VI). Reconstruct Secret

        # ***********************************************************
        # (3) 3rd COMP metric: computation time for reconstructing secret

        # Start timer
        starttime_reconstruct = timeit.default_timer()

        reconstructed_secret = reconstruct_secret(comp_res)

        # Compute time taken
        time_taken_reconstruct = timeit.default_timer() - starttime_reconstruct

        # append our 3rd metric: average time for reconstructing the result
        metrics.update({'comp_time_reconstruction': time_taken_reconstruct})

        # ***********************************************************

        time_taken_overall = timeit.default_timer() - starttime_overall

        # Again, correct for time spent sending and receiving messages
        time_taken_overall_corrected = time_taken_overall - (self.comm.time_spent_sending + self.comm.time_spent_retrieving)

        # Print how much time was spent waiting for network
        print(f'Time spent sending: {self.comm.time_spent_sending}, time spent receiving: {self.comm.time_spent_retrieving}')

        # append our 4th metric: total time for running this function
        metrics.update({'runtime_overall': time_taken_overall_corrected})

        # (4) Now pull all the communication cost metrics from comm

        metrics.update(
            {'bytes_sent_smc_party': self.comm.bytes_sent_smc_party})
        metrics.update(
            {'bytes_received_smc_party': self.comm.bytes_received_smc_party})
        metrics.update({'bytes_sent_ttp': self.comm.bytes_sent_ttp})
        # metrics.update({'bytes_received_ttp': self.comm.bytes_received_ttp})
        metrics.update({'comp_cost_ttp': self.comm.comp_cost_ttp})

        return reconstructed_secret, metrics

    def process_expression(
        self,
        expr: Expression
    ) -> Share:

        # if expr is a addition operation:
        if isinstance(expr, AddOp):

            # NEW: deal with addition of constant

            # (I.) Check if one of the two components of the AddOp is a Scalar

            # Take care of the situation where both of the operands are scalars

            if (isinstance(expr.a, Scalar) and isinstance(expr.b, Scalar)):

                print(
                    f"[AddOp] expr.a AND expr.b are Scalars! Own client_id: {self.client_id}, first client ID in protocol_spec: {self.protocol_spec.participant_ids[0]}")

                if (self.client_id != self.protocol_spec.participant_ids[0]):

                    return Share(0)

                else:

                    res1: Share = self.process_expression(expr.a)

                    print(f'Value 1: {res1.bn}')

                    res2: Share = self.process_expression(expr.b)

                    print(f'Value 2: {res2.bn}')

                    return res1 + res2  # use overloaded method __add__

            # Take a care of the situation where one of the operands (expr.a) is a Scalar

            if (isinstance(expr.a, Scalar)):

                # If (self.id != self.protocol_spec.participant_ids[0]), don't add the Scalar.

                print(
                    f"[AddOp] expr.a is a Scalar! Own client_id: {self.client_id}, first client ID in protocol_spec: {self.protocol_spec.participant_ids[0]}")

                print(self.protocol_spec.participant_ids)

                if (self.client_id != self.protocol_spec.participant_ids[0]):

                    res2: Share = self.process_expression(expr.b)

                    return res2

                else:

                    res1: Share = self.process_expression(expr.a)

                    print(f'Value 1: {res1.bn}')

                    res2: Share = self.process_expression(expr.b)

                    print(f'Value 2: {res2.bn}')

                    return res1 + res2  # use overloaded method __add__

            # Take a care of the situation where one of the operands (expr.b) is a Scalar# Take a care of the situation where one of the operands (expr.b) is a Scalar

            elif (isinstance(expr.b, Scalar)):

                # If (self.id != self.protocol_spec.participant_ids[0]), don't add the Scalar.

                print(
                    f"[AddOp] expr.a is a Scalar! Own client_id: {self.client_id}, first client ID in protocol_spec: {self.protocol_spec.participant_ids[0]}")

                print(self.protocol_spec.participant_ids)

                if (self.client_id != self.protocol_spec.participant_ids[0]):

                    res1: Share = self.process_expression(expr.a)

                    return res1

                else:

                    res1: Share = self.process_expression(expr.a)

                    print(f'Value 1: {res1.bn}')

                    res2: Share = self.process_expression(expr.b)

                    print(f'Value 2: {res2.bn}')

                    return res1 + res2  # use overloaded method __add__

            else:

                res1: Share = self.process_expression(expr.a)

                print(f'Value 1: {res1.bn}')

                res2: Share = self.process_expression(expr.b)

                print(f'Value 2: {res2.bn}')

                return res1 + res2  # use overloaded method __add__

        # if expr is a subtraction operation:
        if isinstance(expr, SubOp):

            # NEW: deal with subtraction of constant

            # (I.) Check if one of the two components of the SubOp is a Scalar

            # Take care of the situation where both of the operands are scalars

            if (isinstance(expr.a, Scalar) and isinstance(expr.b, Scalar)):

                print(
                    f"[SubOp] expr.a AND expr.b are Scalars! Own client_id: {self.client_id}, first client ID in protocol_spec: {self.protocol_spec.participant_ids[0]}")

                if (self.client_id != self.protocol_spec.participant_ids[0]):

                    return Share(0)

                else:

                    res1: Share = self.process_expression(expr.a)

                    print(f'Value 1: {res1.bn}')

                    res2: Share = self.process_expression(expr.b)

                    print(f'Value 2: {res2.bn}')

                    return res1 - res2  # use overloaded method __sub__

            # Take a care of the situation where one of the operands (expr.a) is a Scalar

            if (isinstance(expr.a, Scalar)):

                # If (self.id != self.protocol_spec.participant_ids[0]), don't subtract the Scalar.

                print(
                    f"[SubOp] expr.a is a Scalar! Own client_id: {self.client_id}, first client ID in protocol_spec: {self.protocol_spec.participant_ids[0]}")

                print(self.protocol_spec.participant_ids)

                if (self.client_id != self.protocol_spec.participant_ids[0]):

                    res2: Share = self.process_expression(expr.b)

                    return res2

                else:

                    res1: Share = self.process_expression(expr.a)

                    print(f'Value 1: {res1.bn}')

                    res2: Share = self.process_expression(expr.b)

                    print(f'Value 2: {res2.bn}')

                    return res1 - res2  # use overloaded method __sub__

            # Take a care of the situation where one of the operands (expr.b) is a Scalar

            elif (isinstance(expr.b, Scalar)):

                # If (self.id != self.protocol_spec.participant_ids[0]), don't subtract the Scalar.

                print(
                    f"[SubOp] expr.a is a Scalar! Own client_id: {self.client_id}, first client ID in protocol_spec: {self.protocol_spec.participant_ids[0]}")

                print(self.protocol_spec.participant_ids)

                if (self.client_id != self.protocol_spec.participant_ids[0]):

                    res1: Share = self.process_expression(expr.a)

                    return res1

                else:

                    res1: Share = self.process_expression(expr.a)

                    print(f'Value 1: {res1.bn}')

                    res2: Share = self.process_expression(expr.b)

                    print(f'Value 2: {res2.bn}')

                    return res1 - res2  # use overloaded method __sub__

            else:

                res1: Share = self.process_expression(expr.a)

                print(f'Value 1: {res1.bn}')

                res2: Share = self.process_expression(expr.b)

                print(f'Value 2: {res2.bn}')

                return res1 - res2  # use overloaded method __sub__

        # if expr is a multiplication operation:
        if isinstance(expr, MultOp):

            res1: Share = self.process_expression(expr.a)

            res2: Share = self.process_expression(expr.b)

            # Special case: we're only multiplying scalars;
            # as the results will be addded in the end, let's only have this done
            # by one party.
            if scalars_only(expr.a) and scalars_only(expr.b):

                if self.protocol_spec.participant_ids[0] == self.client_id:

                    return res1 * res2  # use overloaded method __mul__

                else:

                    return Share(0)

            # Don't want to do anything fancy if one of our multiplicators does not contain any
            # Secrets (i.e., is only composed of Scalars).
            if scalars_only(expr.a) or scalars_only(expr.b):

                print("Performing scalar multiplication!")

                return res1 * res2  # use overloaded method __mul__

            # None of the mulitplicands (? multiplicators?) is a Scalar, so we have to go through with our scheme.
            else:

                print("Using Beaver triplet scheme!")

                # (I) Retrieve beaver triplets from ttp

                triplet: Tuple[int, int, int] = self.comm.retrieve_beaver_triplet_shares(
                    str(self.protocol_spec.expr))

                a_share: Share = Share(triplet[0])

                b_share: Share = Share(triplet[1])

                # '(II): Computate & publish

                # (a) compute [x - a], broadcast (public message)

                x_minus_a: Share = res1 - a_share

                label_x_minus_a = f'{self.client_id}-{expr}-(x-a)'

                msg_to_send_x_minus_a = serialize_object(x_minus_a)

                self.comm.publish_message(
                    label_x_minus_a, msg_to_send_x_minus_a)

                # (b) compute [y - b], broadcast (public message)

                y_minus_b: Share = res2 - b_share

                label_y_minus_b = f'{self.client_id}-{expr}-(y-b)'

                msg_to_send_y_minus_b = serialize_object(y_minus_b)

                self.comm.publish_message(
                    label_y_minus_b, msg_to_send_y_minus_b)

                # (III) Reconstruct (x-a), (x-b) using the published computation results

                # retrieve what the other peers have computed

                x_minus_a_shares = [x_minus_a]

                y_minus_b_shares = [y_minus_b]

                for peer in self.peer_ids:

                    # (a) Receive the [x-a] share of this peer

                    recv_res_label_x_minus_a = f'{peer}-{expr}-(x-a)'

                    message_received_x_minus_a = self.comm.retrieve_public_message(
                        peer, recv_res_label_x_minus_a)

                    # decode from bytes
                    message_decoded_x_minus_a = deserialize_object(
                        message_received_x_minus_a)

                    # add the received share to the respective list
                    x_minus_a_shares.append(message_decoded_x_minus_a)

                    # (b) Receive the [y-b] share of this peer

                    recv_res_label_y_minus_b = f'{peer}-{expr}-(y-b)'

                    message_received_y_minus_b = self.comm.retrieve_public_message(
                        peer, recv_res_label_y_minus_b)

                    # decode from bytes
                    message_decoded_y_minus_b = deserialize_object(
                        message_received_y_minus_b)

                    # add the received share to the respective list
                    y_minus_b_shares.append(message_decoded_y_minus_b)

                x_minus_a_reconstructed: int = reconstruct_secret(
                    x_minus_a_shares)

                y_minus_b_reconstructed: int = reconstruct_secret(
                    y_minus_b_shares)

                # (IV) Perform computation outlined in handout, with red term only if self.client_id == self.protocol_spec.participant_ids[0]

                z_share = Share(
                    triplet[2]) + res1 * Share(y_minus_b_reconstructed) + res2 * Share(x_minus_a_reconstructed)

                if self.client_id == self.protocol_spec.participant_ids[0]:

                    z_share = z_share - \
                        Share(x_minus_a_reconstructed) * \
                        Share(y_minus_b_reconstructed)

                return z_share

        # if expr is a secret:
        if isinstance(expr, Secret):

            # (I.) It is a share of one of this participant's own secrets => lookup in self.shares_dict

            if expr in list(self.shares_dict.keys()):

                print("Retrieve own value!!")

                return self.shares_dict[expr]

            # (II.) It is a share of someone else's secret => retrieve private message from TTP

            else:

                print("Retrieve someone else's value!!")

                msg_bytes = self.comm.retrieve_private_message(str(expr.id))

                msg_restored = deserialize_object(msg_bytes)

                return msg_restored

                # if expr is a scalar:
        if isinstance(expr, Scalar):

            return Share(expr.value)  # ??? slightly unsure about that
        #
        # Call specialized methods for each expression type, and have these specialized
        # methods in turn call `process_expression` on their sub-expressions to process
        # further.

    # Feel free to add as many methods as you want.

# determine if an expression contains only Scalars (for determining if we need to use the Beaver
# triplet scheme for an expression or not)
def scalars_only(expr: Expression):

    if isinstance(expr, Scalar): 

        return True

    elif isinstance(expr, Secret):

        return False

    else:

        return scalars_only(expr.a) and scalars_only(expr.b)