#!.venv/bin/python
import bitcointx
from bitcointx.core import CMutableTxWitness, BytesSerializer
from bitcointx.core.key import CKey
from bitcointx.core.psbt import PartiallySignedTransaction, PSBT_Input, PSBT_UnknownTypeData
from bitcointx.core.script import CScript, TaprootScriptTree, CScriptWitness

import boilerplate
from poc import taproot_multisig
from poc.bitcoin_wallet import BitcoinWallet
from poc.taproot_multisig import PUBKEYS, PRIVKEYS, NUM_REQUIRED_SIGNERS


def main():
    print("Testing multisig charms transaction with PSBTs")
    commit_tx, spell_tx = boilerplate.setup_boilerplate_and_prove_spell()
    wallet = BitcoinWallet('multisig')
    unsigned_spell_tx = spell_tx.to_mutable()
    unsigned_spell_tx.wit = CMutableTxWitness()

    commit_psbt = PartiallySignedTransaction(
        unsigned_tx=commit_tx,
    )
    commit_psbt.set_utxo(
        utxo=wallet.rpc.get_output(commit_tx.vin[0].prevout),
        index=0,
    )
    set_taproot_psbt_input_fields(
        commit_psbt.inputs[0],
        script_tree=taproot_multisig.SCRIPT_TREE,
        script_name='script',
    )

    combined_commit_psbt = sign_with_all_keys_and_combine(commit_psbt)
    finalized_commit_psbt = finalize_taproot_psbt(combined_commit_psbt)
    signed_commit_tx = finalized_commit_psbt.extract_transaction()
    wallet.rpc.test_mempoolaccept(signed_commit_tx)

    spell_psbt = PartiallySignedTransaction(
        unsigned_tx=unsigned_spell_tx,
    )
    spell_psbt.set_utxo(
        utxo=wallet.rpc.get_output(spell_tx.vin[0].prevout),
        index=0,
    )
    spell_psbt.set_utxo(
        utxo=commit_tx.vout[0],
        index=1,
    )
    spell_psbt.inputs[1].final_script_witness = spell_tx.wit.vtxinwit[1].scriptWitness

    set_taproot_psbt_input_fields(
        spell_psbt.inputs[0],
        script_tree=taproot_multisig.SCRIPT_TREE,
        script_name='script',
    )
    combined_spell_psbt = sign_with_all_keys_and_combine(spell_psbt)
    finalized_spell_psbt = finalize_taproot_psbt(combined_spell_psbt)
    signed_spell_tx = finalized_spell_psbt.extract_transaction()

    tx_package = [signed_commit_tx, signed_spell_tx]

    print("Testing mempoolaccept")
    wallet.rpc.test_mempoolaccept(tx_package)

    print("Submitting package to Bitcoin regtest")
    response = wallet.rpc.call("submitpackage", [tx.serialize().hex() for tx in tx_package])

    print("Response from Bitcoin regtest:", response)


PSBT_IN_TAP_KEY_SIG = 0x13
PSBT_IN_TAP_SCRIPT_SIG = 0x14
PSBT_IN_TAP_LEAF_SCRIPT = 0x15
PSBT_IN_TAP_BIP32_DERIVATION = 0x16
PSBT_IN_TAP_INTERNAL_KEY = 0x17
PSBT_IN_TAP_MERKLE_ROOT = 0x18


def set_taproot_psbt_input_fields(
    psbt_in: PSBT_Input,
    script_tree: TaprootScriptTree,
    script_name: str,
):
    tapscript, control_block = script_tree.get_script_with_control_block(script_name)
    psbt_in.unknown_fields.extend([
        PSBT_UnknownTypeData(
            PSBT_IN_TAP_LEAF_SCRIPT,
            control_block,
            bytes(tapscript) + script_tree.leaf_version.to_bytes(1, 'little'),
        ),
        PSBT_UnknownTypeData(
            PSBT_IN_TAP_INTERNAL_KEY,
            b'',
            script_tree.internal_pubkey,
        ),
    ])

def sign_taproot_multisig_psbt_input(
    *,
    psbt: PartiallySignedTransaction,
    input_index: int,
    privkey: CKey,
):
    assert all(inp.utxo for inp in psbt.inputs), "All inputs must have UTXOs set before signing"

    pubkey = privkey.xonly_pub

    psbt_in = psbt.inputs[input_index]
    if psbt_in.is_final():
        print(f"Input {input_index} is already final, skipping signing")
        return None

    leaf_script_field = _get_unknown_field(
        psbt_in.unknown_fields,
        PSBT_IN_TAP_LEAF_SCRIPT,
    )
    control_block = leaf_script_field.key_data
    tapscript = CScript(leaf_script_field.value[:-1])  # Remove the leaf version byte
    leaf_version = leaf_script_field.value[-1]

    leaf_hash = _get_leaf_hash(
        tapscript,
        leaf_version=leaf_version,
    )
    sig_keydata = pubkey + leaf_hash

    if _get_unknown_field(psbt_in.unknown_fields, PSBT_IN_TAP_SCRIPT_SIG, sig_keydata, default=None):
        # Just doing this to avoid having the same thing there two times
        print(f"Already signed by {pubkey}")
        return None

    unsigned_tx = psbt.unsigned_tx
    sighash = tapscript.sighash_schnorr(
        unsigned_tx,
        input_index,
        spent_outputs=[inp.utxo for inp in psbt.inputs]
    )

    signature = privkey.sign_schnorr_no_tweak(sighash)
    psbt_in.unknown_fields.append(
        PSBT_UnknownTypeData(
            PSBT_IN_TAP_SCRIPT_SIG,
            sig_keydata,
            signature,
        )
    )
    return psbt


def sign_with_all_keys_and_combine(
    psbt: PartiallySignedTransaction,
) -> PartiallySignedTransaction:
    signed_psbts = [
        psbt.clone()
        for _ in PUBKEYS
    ]
    for signed_psbt, privkey in zip(signed_psbts, PRIVKEYS):
        for inp in signed_psbt.inputs:
            if not inp.is_final():
                sign_taproot_multisig_psbt_input(
                    psbt=signed_psbt,
                    input_index=inp.index,
                    privkey=privkey,
                )

    combined = signed_psbts[0]
    for psbt in signed_psbts[1:]:
        combined = combined.combine(psbt)
    return combined


def finalize_taproot_psbt(
    psbt: PartiallySignedTransaction,
) -> PartiallySignedTransaction:
    psbt = psbt.clone()
    for inp in psbt.inputs:
        if inp.is_final():
            continue
        if not inp.unknown_fields:
            raise ValueError(f"Input {inp.index} has no unknown fields, cannot finalize")
        leaf_script_field = _get_unknown_field(
            inp.unknown_fields,
            PSBT_IN_TAP_LEAF_SCRIPT,
        )
        control_block = leaf_script_field.key_data
        tapscript = CScript(leaf_script_field.value[:-1])
        leaf_version = leaf_script_field.value[-1]
        leaf_hash = _get_leaf_hash(
            tapscript,
            leaf_version=leaf_version,
        )
        sigs_in_order = []
        num_sigs = 0
        for pubkey in PUBKEYS:
            if num_sigs >= NUM_REQUIRED_SIGNERS:
                sigs_in_order.append(b'')
                continue
            sig = _get_unknown_field(
                inp.unknown_fields,
                PSBT_IN_TAP_SCRIPT_SIG,
                key_data=pubkey + leaf_hash,
                default=None,
            )
            if sig is None:
                sigs_in_order.append(b'')
                continue

            sigs_in_order.append(sig.value)
            num_sigs += 1
        assert num_sigs <= NUM_REQUIRED_SIGNERS, f"Too many signatures: {num_sigs} > {NUM_REQUIRED_SIGNERS}"
        if num_sigs < NUM_REQUIRED_SIGNERS:
            raise ValueError(f"Can't finalize input {inp.index}: Not enough signatures: {num_sigs} < {NUM_REQUIRED_SIGNERS}")

        sigs_in_order.reverse()  # correct stack order
        inp.final_script_witness = CScriptWitness(stack=[
            *sigs_in_order,
            tapscript,
            control_block,
        ])
        inp._clear_nonfinal_fields()
        assert inp.is_final()
    if not psbt.is_final():
        raise ValueError("PSBT is not final after finalizing inputs")
    return psbt


_unset = object()
def _get_unknown_field(
    unknown_fields: list[PSBT_UnknownTypeData],
    key_type: int,
    key_data: bytes | None = None,
    *,
    default=_unset,
):
    """
    Retrieves a specific unknown field from the PSBT input's unknown fields.
    If key_data is provided, it will match both type and data; otherwise, it matches only by type.
    """
    for uf in unknown_fields:
        if uf.key_type == key_type and (key_data is None or uf.key_data == key_data):
            return uf
    if default is not _unset:
        return default
    raise KeyError(f'Unknown field with type {key_type} and data {key_data.hex() if key_data else None} not found')


def _get_leaf_hash(
    leaf: CScript,
    *,
    leaf_version: int = 0xc0
) -> bytes:
    return bitcointx.core.CoreCoinParams.tapleaf_hasher(
        bytes([leaf_version])
        + BytesSerializer.serialize(leaf))


if __name__ == "__main__":
    main()