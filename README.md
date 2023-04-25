# Secure Multi-party Computation System

## Introduction

The goal of this project is to present an implementation of a secure multi-party (SMC) scheme which 
enables a group of participants to evaluate arithmetic expressions based on their joint inputs without
revealing those inputs. 

The arithmetic operations supported are addition, subtraction, and multiplication of secret inputs and/or
scalars (= non-secret constants).

Our implementation relies on additive secret sharing: in a setting with *n* participants, each participant 
divides each of their secret values into *n* shares (one for each participant). After each participant has
completed their local computation (based on the shares in their possession), the final result is then
obtained by adding up all of the individual local computation results. 

Multiplication of secret values relies on the *Beaver Triplet Scheme*, with a trusted third party (ttp) supplying
shares of blinding values.

We further include a fine-grained evaluation of computation- and communication cost incurred by the implementation and exemplify the usefulness of the system by means of an example use case: scientific collaboration in the absence of mutual trust.

## Files in the directory

Files that were provided in the template and modified to achieve the desired functionality:
* `expression.py`—Tools for defining arithmetic expressions.
* `secret_sharing.py`—Secret sharing scheme
* `ttp.py`—Trusted parameter generator for the Beaver multiplication scheme.
* `smc_party.py`—SMC party implementation
* `test_integration.py`—Integration test suite.

Code that handles the communication (NOT modified):
* `protocol.py`—Specification of SMC protocol
* `communication.py`—SMC party-side of communication
* `server.py`—Trusted server to exchange information between SMC parties.

Files that were ADDED:
* `evaluate_performance.py`: experimental evaluation of the system's performance in the form of 
  computation- and communication cost. Five different experiments in which the number of participants,
  secret additions, scalar additions, secret multiplications and scalar multiplications are varied 
  systematically (keeping all other factors constant). 
  Computation cost measurements are collected in the `smc_party` instances, with corrections for network
  delays which are obtained from the associated `communication`-instances. Communication cost measurements
  for the individual `smc_party` instances are collected via their associated `communication` instances.
  For each value of a varied factor, 30 repetitions of the computation are carried out to show 
  centrality trends to show up with numerical significance.
  The data produced from each experiment is written to a `.json`-file.
* `data_analysis.ipynb`: a Jupyter notebook for generating the plots shown in the report based on the data
  produced by the experiments in `evaluate_performance.py`. Note that executing this notebook relies on some
  additional packages (`seaborn`, `pandas`, `ipykernel`) which are included in `requirements.txt`.
* `custom_application.py`: this script demonstrates the sample use case of the system: scientific collaboration) in the absence of mutual trust. Please refer to the report as well as the extensive comments in the script itself for details.
* `num_participants_results.json`, `num_secret_additions_results.json`, `num_scalar_additions_results.json`,
  `num_secret_multiplications_results.json`, `num_scalar_multiplications_results.json`: the results of the five
  experiments for evaluating computation- and communication cost incurred in the system.