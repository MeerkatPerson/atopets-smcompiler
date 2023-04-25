
# *****************************************************************************************************
# IMPORTS

import time
from multiprocessing import Process, Queue

from expression import Scalar, Secret
from protocol import ProtocolSpec
from server import run

from smc_party import SMCParty

# *****************************************************************************************************
# Functionality from test_integration.py for validating the sample application's circuit


def smc_client(client_id, prot, value_dict, queue):
    cli = SMCParty(
        client_id,
        "localhost",
        5000,
        protocol_spec=prot,
        value_dict=value_dict
    )
    res = cli.run()
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
    participants = list(parties.keys())

    prot = ProtocolSpec(expr=expr, participant_ids=participants)
    clients = [(name, prot, value_dict)
               for name, value_dict in parties.items()]

    results = run_processes(participants, *clients)

    for result in results:
        assert result == expected

    return results

# *****************************************************************************************************
# Our custom-application's circuit!


if __name__ == "__main__":

    """
    f(altruism_score, honesty_score, kindness_score, empathy_score, 
        generosity_score, modesty_score, animal_lover_score,
        altruism_weight, honesty_weight, kindness_weight, empathy_weight,
        generosity_weight, modesty_weight, animal_lover_weight) =
        3 * (altruism_score * altruism_weight + honesty_score * honesty_weight + 
             kindness_score * kindness_weight + empathy_score * empathy_weight + 
             generosity_score * generosity_weight + modesty_score * modesty_weight + 
             animal_lover_score * animal_lover_weight) - 50
    (Where 3 and 50 are Scalars: a scaling factor and the corruptness-index value) 
    """

    """
    Secrets of the researchers from Hochschule St. Quallen (HSQ): 
    The Bestlé CEO's scores on the subscales of the Good Guy Inventory
    - The dimensions are: Altruism, Honesty, Kindness, Empathy, Generosity, Modesty, and Love of Animals.
    - The scale assigns a score between 0 and 5 for each dimension (dimension = subscale).

    Secrets of the researchers from the École Fantastique de Gruyère (EFG): 
    - The weights associated with the dimensions (subscales) are between 1 and 10.
    These weights were determined by the research group by employing sophisticated machine learning techniques
    and are therefore extremely valuable and top-secret!!!
    """

    altruism_score = Secret()
    honesty_score = Secret()
    kindness_score = Secret()
    empathy_score = Secret()
    generosity_score = Secret()
    modesty_score = Secret()
    animal_lover_score = Secret()

    altruism_weight = Secret()
    honesty_weight = Secret()
    kindness_weight = Secret()
    empathy_weight = Secret()
    generosity_weight = Secret()
    modesty_weight = Secret()
    animal_lover_weight = Secret()

    """
    SCALARS INVOLVED IN THE CIRCUIT:

    The GGI foresees a multiplication of the raw score by 3 to 
    ensure the maximum score is 1050 (if all weights were equal to 10). 

    The corruptness index assigned to Bestlé for the period of the
    CEO being in charge of the company is 50 (out of 100, with 0 
    indicating no corruption whatsoever and 100 signifying complete corruptness); 
    it is subtracted from the final GGI score.
    """
    scaling_factor = Scalar(3)
    corruptness_score = Scalar(50)

    """
    The circuit contains two parties, which correspond to the mutually distructful
    research teams:
    - "HSQ" = the team of researchers from Hochschule St. Quallen, who carried out the
               assessment of the Bestlé CEO and don't want to reveal the raw scores
               achieved by the CEO on the individual subscales of the Good Guy Inventory (GGI)
    - "EFG" = the team of researchers from École Fantastique de Gruyère, who created the 
                Good Guy Inventory (GGI) and don't want to reveal the weights given to the 
                individual dimensions in the final score (they are their joy and pride!)
    """
    parties = {
        "HSQ": {altruism_score: 2,
                honesty_score: 0,
                kindness_score: 1,
                empathy_score: 2,
                generosity_score: 4,
                modesty_score: 2,
                animal_lover_score: 3},
        "EFG": {altruism_weight: 2,
                honesty_weight: 3,
                kindness_weight: 4,
                empathy_weight: 9,
                generosity_weight: 5,
                modesty_weight: 6,
                animal_lover_weight: 10},
    }

    expr = scaling_factor * (altruism_score * altruism_weight +
                             honesty_score * honesty_weight +
                             kindness_score * kindness_weight +
                             empathy_score * empathy_weight +
                             generosity_score * generosity_weight +
                             modesty_score * modesty_weight +
                             animal_lover_score * animal_lover_weight) - corruptness_score

    expected = 3 * (2*2 + 0*3 + 1*4 + 2*9 + 4*5 + 2*6 + 3*10) - 50

    results = suite(parties, expr, expected)

    print(f'Computation results: {results}')
