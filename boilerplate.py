import hashlib
import json
from textwrap import dedent

from bitcointx.core import CTransaction

from poc import taproot_multisig
from poc.harness import restart_docker_compose, shell, charms
from poc.taproot_multisig import ADDRESS


def setup_boilerplate_and_prove_spell() -> tuple[CTransaction, CTransaction]:
    print("Setup bitcoin regtest")
    restart_docker_compose()

    shell('bitcoin-cli createwallet multisig true true')
    shell(f"bitcoin-cli -rpcwallet=multisig importdescriptors '{taproot_multisig.WALLET_DESCRIPTORS}'")
    shell(f'bitcoin-cli generatetoaddress 102 {taproot_multisig.ADDRESS}')

    print("Setup conditions for charms")
    utxos = json.loads(shell('bitcoin-cli listunspent'))
    prev_tx = utxos[-1]
    prev_tx_raw = shell(f'bitcoin-cli getrawtransaction {prev_tx["txid"]}')
    in_utxo_0 = f'{prev_tx["txid"]}:{prev_tx["vout"]}'
    funding_utxo = f'{utxos[-2]["txid"]}:{utxos[-2]["vout"]}'
    app_id = hashlib.sha256(in_utxo_0.encode()).hexdigest()

    print("Get charms app vk")
    app_vk = charms("app vk")

    print("Build charms app")
    app_bins = charms("app build")

    print("Test using charms app run")
    nft_spell = dedent(f"""
    version: 2

    apps:
      $00: n/{app_id}/{app_vk}

    private_inputs:
      $00: "{in_utxo_0}"

    ins:
      - utxo_id: {in_utxo_0}
        charms: {{}}

    outs:
      - address: {ADDRESS}
        charms:
          $00:
            ticker: MY-TOKEN
            remaining: 100000
    """)

    charms(
        "app run",
        input=nft_spell,
    )

    print("Prove the spell (will take a while)")
    prove_output = charms(
        "spell prove "
        f"--prev-txs={prev_tx_raw} "
        f"--app-bins={app_bins} --funding-utxo-value=5000000000 --funding-utxo={funding_utxo} --change-address={ADDRESS}",
        input=nft_spell,
    )
    # It outputs multiple lines. The last line is the actual package
    tx_package_raw = prove_output.splitlines()[-1]
    commit_tx_hex, spell_tx_hex = json.loads(tx_package_raw)
    commit_tx = CTransaction.deserialize(bytes.fromhex(commit_tx_hex))
    spell_tx = CTransaction.deserialize(bytes.fromhex(spell_tx_hex))
    return commit_tx, spell_tx
