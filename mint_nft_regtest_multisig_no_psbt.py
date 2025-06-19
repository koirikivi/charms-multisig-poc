#!.venv/bin/python
import json

from bitcointx.core import CTransaction, CTxOut, CMutableTxWitness
from bitcointx.core.script import CScriptWitness

import boilerplate
from poc import taproot_multisig
from poc.bitcoin_wallet import BitcoinWallet


def main():
    print("Testing multisig charms transaction without PSBTs")
    commit_tx, spell_tx = boilerplate.setup_boilerplate_and_prove_spell()
    wallet = BitcoinWallet('multisig')
    unsigned_spell_tx = spell_tx.to_mutable()
    unsigned_spell_tx.wit = CMutableTxWitness()

    signed_txs = [
        sign_tx_with_all_keys(
            commit_tx,
            spent_outputs=[wallet.rpc.get_output(commit_tx.vin[0].prevout)],
        ),
        sign_tx_with_all_keys(
            spell_tx,
            spent_outputs=[
                wallet.rpc.get_output(spell_tx.vin[0].prevout),
                commit_tx.vout[0],
            ],
        ),
    ]

    print("Testing mempoolaccept")
    wallet.rpc.test_mempoolaccept(signed_txs)

    print("Submitting package to Bitcoin regtest")
    response = wallet.rpc.call("submitpackage", [tx.serialize().hex() for tx in signed_txs])

    print("Response from Bitcoin regtest:", response)


def sign_tx_with_all_keys(
    tx: CTransaction,
    spent_outputs: list[CTxOut],
) -> CTransaction:
    tx = tx.to_mutable()
    tapscript, cblock = taproot_multisig.SCRIPT_TREE.get_script_with_control_block('script')

    for input_idx, _ in enumerate(tx.vin):
        if tx.wit.vtxinwit[input_idx].scriptWitness:
            continue
        sighash = tapscript.sighash_schnorr(
            tx,
            input_idx,
            spent_outputs=spent_outputs,
        )
        signatures = [
            taproot_multisig.PRIVKEYS[0].sign_schnorr_no_tweak(sighash),
            taproot_multisig.PRIVKEYS[1].sign_schnorr_no_tweak(sighash),
            b''
        ]
        signatures.reverse()
        tx.wit.vtxinwit[input_idx].scriptWitness = CScriptWitness(stack=[
            *signatures,
            tapscript,
            cblock,
        ])

    return tx.to_immutable()


if __name__ == "__main__":
    main()