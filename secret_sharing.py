"""
Secret sharing scheme.
"""

from typing import List

import random

# Prime number to use: don't have to use some specific library, doesn't have to be super efficient


class Share:
    """
    A secret share in a finite field.
    """

    # Initialize a Share using its value (int mod )
    def __init__(self, val: int = 0):
        self.bn = val
        self.prime = 1753388297  # just use a random large prime for now
        # https://bigprimes.org/

    def __repr__(self):
        # Helps with debugging.
        return f'Share based on prime {self.prime} with value {self.bn}'

    def __add__(self, other):
        # Subtract the value of other from self modulo the given prime

        print(
            f'Own value: {self.bn}, other value: {other.bn}, sum of these: {self.bn + other.bn}')

        add_mod_p = (self.bn + other.bn) % self.prime
        # return a share with the computed result as value
        return Share(add_mod_p)

    def __sub__(self, other):
        # Subtract the value of other from self modulo the given prime
        sub_mod_p = (self.bn - other.bn) % self.prime
        # return a share with the computed result as value
        return Share(sub_mod_p)

    def __mul__(self, other):
        # Multiply the values of self and other modulo the given prime
        mult_mod_p = (self.bn * other.bn) % self.prime

        print(f'Multiplying {self.bn} and {other.bn}, result: {mult_mod_p}')

        # return a share with the computed result as value
        return Share(mult_mod_p)


def share_secret(secret: int, num_shares: int) -> List[Share]:

    shares = []  # list which will contain the shares we're about to generate

    # Additive secret sharing means that the shares are random elements
    # of a finite field that add up to the secret in the field.

    sum_shares = 0  # sum up all the shares except the last one
    # because the scheme relies on the last element
    # being 'secret - sum(all_previous_shares)'

    for i in range(num_shares):

        # we're at the last element - compute it as 'secret - sum(all_previous_shares)'
        if i == (num_shares-1):

            share_val = (secret - sum_shares) % get_prime()

            shares.append(Share(share_val))

        else:

            share_val = random.randint(0, get_prime() - 1)

            sum_shares = (sum_shares + share_val) % get_prime()

            shares.append(Share(share_val))

    return shares


def reconstruct_secret(shares: List[Share]) -> int:
    """Reconstruct the secret from shares."""

    # Accumulator for the reconstruction of the secret based on
    # the values of the shares in the given list
    secret_accum = 0

    for elem in shares:

        secret_accum = (secret_accum + elem.bn) % get_prime()

    return secret_accum


# Currently just a hard-coded reasonably large prime
# TODO should change this in the future?
def get_prime() -> int:

    return 1753388297
