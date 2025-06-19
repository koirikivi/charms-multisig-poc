# Charms multisig POC

## Setup
1. Install `charms` with `--features prover`
2. `python3.12 -m venv .venv && . .venv/bin/activate && pip install -e .`

## Example without PSBTs
```
./mint_nft_regtest_multisig_no_psbt.py
```

## Example with PSBTs
```
./mint_nft_regtest_multisig_psbt.py
```
