
from random import randint
import time
from multiprocessing import Process, Queue

from expression import Scalar, Secret
from protocol import ProtocolSpec
from server import run

from smc_party import SMCParty

from typing import (
    Dict,
    List
)

from statistics import mean

import random

import json

import sys
sys.setrecursionlimit(10000)

# import pandas as pd


def process_metrics(metrics_dicts: List[Dict[str, int]]) -> Dict[str, int]:

    # For the computation times (sharing secrets, processing expression, reconstructing secrets) as well as bytes_sent & bytes received of smc_parties: get avg
    comp_times_sharing = []
    comp_times_processing = []
    comp_times_reconstruction = []
    bytes_sent_smc_parties = []
    bytes_received_smc_parties = []
    runtime_overall = []

    # For the ttp: add the bytes sent across the different participants (no received bytes as smc_party instances only
    # communicate with the ttp via GET requests);
    # for the comp. time: get the max value and subtract the avg of all the other values
    bytes_sent_ttp = 0
    comp_times_ttp = []

    for metrics_dict in metrics_dicts:

        comp_times_sharing.append(metrics_dict['comp_time_sharing'])
        comp_times_processing.append(metrics_dict['comp_time_processing'])
        comp_times_reconstruction.append(
            metrics_dict['comp_time_reconstruction'])
        bytes_received_smc_parties.append(
            metrics_dict['bytes_received_smc_party'])
        bytes_sent_smc_parties.append(metrics_dict['bytes_sent_smc_party'])
        runtime_overall.append(metrics_dict['runtime_overall'])

        # NOTE obv metrics related to ttp only make sense in the cases where
        # there is multiplication of secrets involved
        bytes_sent_ttp += metrics_dict['bytes_sent_ttp']
        # bytes_received_ttp += metrics_dict['bytes_received_ttp']
        comp_times_ttp.append(metrics_dict['comp_cost_ttp'])

    overall_metrics = dict()
    overall_metrics['comp_time_sharing'] = mean(comp_times_sharing)
    overall_metrics['comp_time_processing'] = mean(comp_times_processing)
    overall_metrics['comp_time_reconstruction'] = mean(
        comp_times_reconstruction)
    overall_metrics['bytes_received_smc_party'] = mean(
        bytes_received_smc_parties)
    overall_metrics['bytes_sent_smc_party'] = mean(bytes_sent_smc_parties)
    overall_metrics['runtime_overall'] = mean(runtime_overall)
    overall_metrics['bytes_sent_ttp'] = bytes_sent_ttp

    # The logic here is: when an smc_party first requests their triplet shares from the ttp,
    # the ttp will have to generate the triplets & shares.
    # For all the smc_party instances requesting their shares from the ttp thereafter, the time we
    # are measuring is simply network delay.
    # therefore: time taken to respond to first request - avg(time taken to respond to subsequent requests) = approx. comp time ttp
    max_ttp_comp_time = max(comp_times_ttp)
    comp_times_ttp.remove(max_ttp_comp_time)  # this is 'in place'
    comp_time_ttp_corrected = max_ttp_comp_time - mean(comp_times_ttp)

    overall_metrics['comp_time_ttp'] = comp_time_ttp_corrected

    return overall_metrics


def smc_client(client_id, prot, value_dict, queue):
    cli = SMCParty(
        client_id,
        "localhost",
        5000,
        protocol_spec=prot,
        value_dict=value_dict
    )
    res = cli.run_instrumented()  # New: run instrumented so we can get metrics
    queue.put(res)
    print(f"{client_id} has finished!")


def smc_server(args):
    run("localhost", 5000, args)


def run_processes(server_args, *client_args):
    queue = Queue()

    server = Process(target=smc_server, args=(server_args,))
    clients = [Process(target=smc_client, args=(*args, queue))
               for args in client_args]

    server.start()
    time.sleep(3)
    for client in clients:
        client.start()

    results = list()
    for client in clients:
        client.join()

    for client in clients:
        results.append(queue.get())

    server.terminate()
    server.join()

    # To "ensure" the workers are dead.
    time.sleep(2)

    print("Server stopped.")

    return results


def suite(parties, expr, expected):

    print(f"Expr: {expr}")

    print(f"Expected: {expected}")

    participants = list(parties.keys())

    prot = ProtocolSpec(expr=expr, participant_ids=participants)
    clients = [(name, prot, value_dict)
               for name, value_dict in parties.items()]

    results = run_processes(participants, *clients)

    # List which will contain all the dictionaries with metrics as measured by the parties
    metrics_dicts = []

    for result in results:
        print(result[1])
        metrics_dicts.append(result[1])
        print(f'Result: {result[0]}, expected: {expected}')
        assert result[0] == expected

    # Then process the results dictionaries
    # For the computation times (sharing secrets, processing expression, reconstructing secrets) as well as bytes_sent & bytes received of smc_parties: get avg
    # For the ttp: add the bytes sent and received across the different participants; for the comp. time: get the max value and subtract the avg of all the other values
    metrics_processed = process_metrics(metrics_dicts)

    return metrics_processed

# **************************************************************
# MEASUREMENT 1: influence of number of participants


def test_influence_of_number_of_participants() -> None:
    """
    We want to use an expression that contains all our operations
    f(a, b, c) = (a*b + c) * K1 + K2
    """

    # Initialize randomness generator with seed
    random.seed(10)

    # List which will store dictionaries with results
    results = []

    # now we are adding some dummy participants whose secrets we won't use
    for num_parts in [5, 10, 25, 50, 75, 100]:

        # 30 iterations each => central limit theorem
        for iteration in range(30):

            # Generate three secrets & associated values
            alice_secret = Secret()
            alice_val = random.randint(0, 1753388297-1)

            bob_secret = Secret()
            bob_val = random.randint(0, 1753388297-1)

            charlie_secret = Secret()
            charlie_val = random.randint(0, 1753388297-1)

            parties = {
                "Alice": {alice_secret: alice_val},
                "Bob": {bob_secret: bob_val},
                "Charlie": {charlie_secret: charlie_val}
            }

            # Generate two scalars
            scalar_one = random.randint(0, 1753388297-1)
            scalar_two = random.randint(0, 1753388297-1)

            expr = ((alice_secret * bob_secret) + charlie_secret) * \
                Scalar(scalar_one) + Scalar(scalar_two)

            expected = ((alice_val * bob_val + charlie_val) *
                        scalar_one + scalar_two) % 1753388297

            # create the dummy parties
            # subtract 3 because we already have 3 participants in all cases
            for i in range(num_parts-3):

                # the secrets don't need a variable identifier as they're not used in the expression
                parties.update(
                    {f'party_{i}': {Secret(): random.randint(0, 1753388297-1)}})

            # Grab the metrics computed
            metrics_processed = suite(parties, expr, expected)

            # Add our variables: number of parties, iteration
            metrics_processed.update({'num_parties': num_parts})
            metrics_processed.update({'iteration': iteration})

            print("Metrics aggregated: ")

            print(metrics_processed)

            # append to results
            results.append(metrics_processed)

    # write result to json array
    with open('num_participants_results.json', 'w') as out:
        json.dump(results, out)


# **************************************************************
# MEASUREMENT 2: influence of number of secret additions

def test_influence_of_number_of_secret_additions() -> None:
    """
    We want to use an expression that contains many additions of secrets
    f(a, b, c) = a + b + c + a + b + c + ..... + a + b + c
    """

    # Initialize randomness generator with seed
    random.seed(10)

    # List which will store dictionaries with results
    results = []

    # Now vary the number of additions
    for num_secret_additions in [10, 100, 500, 1000]:

        print(f"Number of secret additions: {num_secret_additions}")

        # 30 iterations each => central limit theorem
        for iteration in range(30):

            # Generate three secrets & associated values
            alice_secret = Secret()
            alice_val = random.randint(0, 1753388297-1)

            bob_secret = Secret()
            bob_val = random.randint(0, 1753388297-1)

            charlie_secret = Secret()
            charlie_val = random.randint(0, 1753388297-1)

            parties = {
                "Alice": {alice_secret: alice_val},
                "Bob": {bob_secret: bob_val},
                "Charlie": {charlie_secret: charlie_val}
            }

            # add the three secrets to a list
            secrets_list = [alice_secret, bob_secret, charlie_secret]
            values_list = [alice_val, bob_val, charlie_val]

            # Initial expression + expected
            expr = alice_secret + bob_secret + charlie_secret
            expected = (alice_val + bob_val + charlie_val) % 1753388297

            # add terms to our addition
            for i in range(num_secret_additions-3):

                ind = i % 3

                expr += secrets_list[ind]

                expected = (expected + values_list[ind]) % 1753388297

            # run the suite and grab the results
            metrics_processed = suite(parties, expr, expected)

            # Add our variables: number of parties, iteration
            metrics_processed.update(
                {'num_secret_additions': num_secret_additions})
            metrics_processed.update({'iteration': iteration})

            print("Metrics aggregated: ")

            print(metrics_processed)

            # append to results
            results.append(metrics_processed)

     # write result to json array
    with open('num_secret_additions_results.json', 'w') as out:
        json.dump(results, out)

# **************************************************************
# MEASUREMENT 3: influence of number of scalar additions


def test_influence_of_number_of_scalar_additions() -> None:
    """
    We want to use an expression that contains many additions of scalars
    f(a, b, c) = k1 + k2 + k3 + ..... + kn
    """

    # Initialize randomness generator with seed
    random.seed(10)

    # List which will store dictionaries with results
    results = []

    # Now vary the number of additions
    for num_scalar_additions in [10, 100, 500, 1000]:

        # 30 iterations each => central limit theorem
        for iteration in range(30):

            # Generate three secrets & associated values
            alice_secret = Secret()
            alice_val = random.randint(0, 1753388297-1)

            bob_secret = Secret()
            bob_val = random.randint(0, 1753388297-1)

            charlie_secret = Secret()
            charlie_val = random.randint(0, 1753388297-1)

            parties = {
                "Alice": {alice_secret: alice_val},
                "Bob": {bob_secret: bob_val},
                "Charlie": {charlie_secret: charlie_val}
            }

            expected = 0

            # add terms to our addition
            for i in range(num_scalar_additions):

                scalar_val = random.randint(0, 1753388297-1)

                if i == 0:

                    expr = Scalar(scalar_val)

                else:
                
                    expr += Scalar(scalar_val)

                expected = (expected + scalar_val) % 1753388297

            # run the suite and grab the results
            metrics_processed = suite(parties, expr, expected)

            # Add our variables: number of parties, iteration
            metrics_processed.update(
                {'num_scalar_additions': num_scalar_additions})
            metrics_processed.update({'iteration': iteration})

            print("Metrics aggregated: ")

            print(metrics_processed)

            # append to results
            results.append(metrics_processed)

    # write result to json array
    with open('num_scalar_additions_results.json', 'w') as out:
        json.dump(results, out)

# **************************************************************
# MEASUREMENT 4: influence of number of secret multiplications


def test_influence_of_number_of_secret_multiplications() -> None:
    """
    We want to use an expression that contains many multiplications of secrets
    f(a, b, c) = a * b * c * a * b * c * ..... * a * b * c
    """

    # Initialize randomness generator with seed
    random.seed(10)

    # List which will store dictionaries with results
    results = []

    # Now vary the number of multiplications
    for num_secret_multiplications in [10, 100, 500, 1000]:

        # 30 iterations each => central limit theorem
        for iteration in range(30):

            # Generate three secrets & associated values
            alice_secret = Secret()
            alice_val = random.randint(0, 1753388297-1)

            bob_secret = Secret()
            bob_val = random.randint(0, 1753388297-1)

            charlie_secret = Secret()
            charlie_val = random.randint(0, 1753388297-1)

            parties = {
                "Alice": {alice_secret: alice_val},
                "Bob": {bob_secret: bob_val},
                "Charlie": {charlie_secret: charlie_val}
            }

            # add the three secrets to a list
            secrets_list = [alice_secret, bob_secret, charlie_secret]
            values_list = [alice_val, bob_val, charlie_val]

            # Initial expression + expected
            expr = alice_secret * bob_secret * charlie_secret
            expected = (alice_val * bob_val * charlie_val) % 1753388297

            # add terms to our addition
            for i in range(num_secret_multiplications-3):

                ind = i % 3

                expr *= secrets_list[ind]

                expected = (expected * values_list[ind]) % 1753388297

            # run the suite and grab the results
            metrics_processed = suite(parties, expr, expected)

            # Add our variables: number of parties, iteration
            metrics_processed.update(
                {'num_secret_multiplications': num_secret_multiplications})
            metrics_processed.update({'iteration': iteration})

            print("Metrics aggregated: ")

            print(metrics_processed)

            # append to results
            results.append(metrics_processed)

    # write result to json array
    with open('num_secret_multiplications_results.json', 'w') as out:
        json.dump(results, out)

    # **************************************************************
    # MEASUREMENT 5: influence of number of scalar multiplications


def test_influence_of_number_of_scalar_multiplications() -> None:
    """
    We want to use an expression that contains many additions of scalars
    f(a, b, c) = k1 * k2 * k3 * ..... * kn
    """

    # Initialize randomness generator with seed
    random.seed(10)

    # List which will store dictionaries with results
    results = []

    # Now vary the number of multiplications
    for num_scalar_multiplications in [10, 100, 500, 1000]:

        # 30 iterations each => central limit theorem
        for iteration in range(30):

            # Generate three secrets & associated values
            alice_secret = Secret()
            alice_val = random.randint(0, 1753388297-1)

            bob_secret = Secret()
            bob_val = random.randint(0, 1753388297-1)

            charlie_secret = Secret()
            charlie_val = random.randint(0, 1753388297-1)

            parties = {
                "Alice": {alice_secret: alice_val},
                "Bob": {bob_secret: bob_val},
                "Charlie": {charlie_secret: charlie_val}
            }

            expected = 1

            # add terms to our multiplicative term
            for i in range(num_scalar_multiplications):

                # subtracting 1 because randint includes both upper and lower end of range
                scalar_val = random.randint(0, 1753388297-1)

                if i == 0:

                    expr = Scalar(scalar_val)

                else: 

                    expr = expr * Scalar(scalar_val)

                expected = (expected * scalar_val) % 1753388297

            # run the suite and grab the results
            metrics_processed = suite(parties, expr, expected)

            # Add our variables: number of parties, iteration
            metrics_processed.update(
                {'num_scalar_multiplications': num_scalar_multiplications})
            metrics_processed.update({'iteration': iteration})

            print("Metrics aggregated: ")

            print(metrics_processed)

            # append to results
            results.append(metrics_processed)

    # write result to json array
    with open('num_scalar_multiplications_results.json', 'w') as out:
        json.dump(results, out)


if __name__ == "__main__":

    test_influence_of_number_of_secret_additions()

    test_influence_of_number_of_scalar_additions()

    test_influence_of_number_of_secret_multiplications()

    test_influence_of_number_of_scalar_multiplications()

    test_influence_of_number_of_participants()

