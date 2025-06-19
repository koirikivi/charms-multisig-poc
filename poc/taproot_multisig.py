import json
from bitcointx import select_chain_params
from bitcointx.core import CTransaction, CTxIn, CTxOut, COutPoint
from bitcointx.core.key import CKey, XOnlyPubKey
from bitcointx.core.script import CScript, TaprootScriptTree, CScriptOp, OP_CHECKSIGADD, OP_CHECKSIG, OP_NUMEQUAL
from bitcointx.wallet import P2TRCoinAddress

from .rpc import bitcoin_rpc
from .descriptors import descsum_create

select_chain_params('bitcoin/regtest')


NUMS_PUBKEY = XOnlyPubKey.fromhex('50929b74c1a04954b78b4b6035e97a5e078a5a0f28ec96d547bfee9ace803ac0')
NUM_REQUIRED_SIGNERS = 2

PRIVKEYS = [
    CKey.from_secret_bytes(b'\x01' * 32),
    CKey.from_secret_bytes(b'\x02' * 32),
    CKey.from_secret_bytes(b'\x03' * 32),
]
PUBKEYS = [
    priv.xonly_pub for priv in PRIVKEYS
]

MULTISIG_SCRIPT = CScript([
    PUBKEYS[0],
    OP_CHECKSIG,
    PUBKEYS[1],
    OP_CHECKSIGADD,
    PUBKEYS[2],
    OP_CHECKSIGADD,
    2,
    OP_NUMEQUAL,
], name='script')

SCRIPT_TREE = TaprootScriptTree(
    leaves=[MULTISIG_SCRIPT],
    internal_pubkey=NUMS_PUBKEY,
)

ADDRESS = P2TRCoinAddress.from_script_tree(SCRIPT_TREE)
WALLET_DESCRIPTORS = json.dumps([
    {
        "desc": descsum_create(f"addr({ADDRESS})"),
        "timestamp": 0,
        "watchonly": True,
    }
])

if __name__ == '__main__':
    print(f"Taproot multisig address: {ADDRESS}")
    print("Script")
    print(repr(MULTISIG_SCRIPT))
    print("Internal pubkey")
    print(NUMS_PUBKEY)