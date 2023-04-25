"""
Trusted parameters generator.

MODIFY THIS FILE.
"""

import collections
from typing import (
    Dict,
    Set,
    Tuple,
    List
)

from communication import Communication
from secret_sharing import(
    share_secret,
    Share,
)

import random

# Feel free to add as many imports as you want.


class TrustedParamGenerator:
    """
    A trusted third party that generates random values for the Beaver triplet multiplication scheme.
    """

    def __init__(self):
        self.participant_ids: Set[str] = set()
        self.prime = 1753388297  # just use a random large prime for now
        self.triplet = []
        self.triplet_shares = dict()

    def generate_triplet(self) -> List[int]:
        # random includes both upper and lower end of range, so need to subtract one from upper end
        a: int = random.randint(0, self.prime - 1)
        b: int = random.randint(0, self.prime - 1)
        c: int = a * b % self.prime
        return [a, b, c]

    def share_triplet(self) -> Dict[str, List[Share]]:
        # Generate a list of lists containing the shares for a, b, and c
        # => a, b, and c will each be mapped to a list of Shares of the length = number of participants
        mapped_values = []

        for val in self.triplet:

            # generate a list of shares for this component of triplet (a, b, or c)
            shares_list = share_secret(val, len(self.participant_ids))

            mapped_values.append(shares_list)

        # Generate a dict with participant_ids as keys and list containing shares for that respective participant as values

        shares_for_participants = dict()

        for i, participant_id in enumerate(self.participant_ids):

            shares_for_participant = [share_list[i]
                                      for share_list in mapped_values]

            shares_for_participants.update(
                {participant_id: shares_for_participant})

        print(f'Shares for participants: {shares_for_participants}')

        return shares_for_participants

    def add_participant(self, participant_id: str) -> None:
        """
        Add a participant.
        """
        self.participant_ids.add(participant_id)

    def retrieve_share(self, client_id: str, op_id: str) -> Tuple[Share, Share, Share]:
        """
        Retrieve a triplet of shares for a given client_id.
        """

        # Have to deal with a subtlety here: at the point when ttp is created, we cannot
        # already generate the beaver triplet shares because participants are added later
        # (=> in order to generate the shares the ttp has to know the list of participant_ids,
        # which is doesn't at the time the constructor is called)

        if not self.triplet_shares:  # i.e., this client is the first to request their shares of the beaver triplets;
            # have to generate the triplet shares dict first

            # NOTE now also generating the triplets themselve here because it is more convenient for
            # performance evaluation
            self.triplet = self.generate_triplet()

            self.triplet_shares = self.share_triplet()

        return self.triplet_shares[client_id]
