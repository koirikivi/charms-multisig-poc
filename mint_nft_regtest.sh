#!/bin/bash
set -e

# TODO: this is hardcoded now. Charms needs to be built with features=prover right now
CHARMS=/Users/rainer/work/sovryn/charms/target/release/charms
#CHARMS=charms

THIS_DIR=$(dirname "$(realpath "$0")")
# Add our bitcoin-cli to path so charms will use it
export PATH=$(realpath $THIS_DIR/bin):$PATH
cd $THIS_DIR
mkdir -p var || true

docker-compose down || true
docker-compose up -d
wait-for-bitcoin
bitcoin-cli createwallet testwallet
bitcoin-cli -rpcwallet=testwallet -generate 102

cd "$THIS_DIR/my-token"
export app_vk=$($CHARMS app vk)

export in_utxo_0="$(bitcoin-cli listunspent | jq -r '.[-1].txid'):$(bitcoin-cli listunspent | jq -r '.[-1].vout')"
funding_utxo="$(bitcoin-cli listunspent | jq -r '.[-2].txid'):$(bitcoin-cli listunspent | jq -r '.[-2].vout')"

export app_id=$(echo -n "${in_utxo_0}" | sha256sum | cut -d' ' -f1)
export addr_0=$(bitcoin-cli getnewaddress)

#cat ./spells/mint-nft.yaml | envsubst | $CHARMS app run

app_bins=$($CHARMS app build)

# pick from the output of `bitcoin-cli listunspent`
# should NOT be the same as the one you used for minting the NFT

export RUST_LOG=info
#export RUST_BACKTRACE=full

echo "Casting the spell"
cat ./spells/mint-nft.yaml | envsubst | $CHARMS spell cast --app-bins=${app_bins} --funding-utxo=${funding_utxo} | tee ../var/regtest-spell.log
PACKAGE=$(tail -1 ../var/regtest-spell.log)
# send the package to the blockchain
#echo bitcoin-cli submitpackage '["02000000000101c486ae03539877f2b56751192724a0935a675ec23b4092e0c10c166b107a68730100000000ffffffff01636c0000000000002251206ea9f0dfa0398fa94cd1ae2a50ec1b2cc537143a2eb64125eb0765ed5a8e55310140021185947c26d843e6b045a8398e19502b3fe3ebac410c4a5841f9d425219d94b03fcf9fbefe9055873a28e61646cb73909468c78593b0eb8adbc87716d0e5de00000000","0200000000010226a2807baec472f2b5d5e4951bde9bb40e7ee594974b2ba4f06fbf8b1abbb6fd0100000000ffffffffd1f9655c06f7e90661edfca5dca0547b6116a33d4820829e0579b7a9a595369b0000000000ffffffff02e8030000000000002251204d80d86ba95c905583fce5e0b29ef4c59c730505d64e73194599a4c0896b8b8b07ec000000000000225120665c42022dca78a8634f9dce3ce3de5575d24e791f6e567864188397195b997701402a51eba4514c7ad17a46838ae4a44e0010f64fc5671d4da3abd0ab0f3ab21e479fdca1074e71b7d9a687ae2c0a72478b920f97a26ba9fabb1018c24efd96e04803417b17ba5cf0d1de5459f4067fab565a0923b466088b4a2dd71bf64d005696b98c758dcd8f0d71495eb8516b90cafab61cb49dee42670268c7cb5c75dbc034b6aa81fdf3020063057370656c6c4d080282a36776657273696f6e02627478a2647265667380646f75747381a100a2667469636b6572684d592d544f4b454e6972656d61696e696e671a000186a0716170705f7075626c69635f696e70757473a183616e982018561887185018f318e018c818b118a1187a18301871183e187a18be18ef186918f718ac185f18360b188b01182300185b186d184a18aa18fb18e718af9820189918cd185c183c18491836189317182a18b918ea181918f5182b18be185c1839187118bf184a18e018f318ee18251847187c184d18711218c6189800f69901041118b618a0189d182b187d18b018d718c818c1185d189618a618af18d7187f1418d4185418bf1873185c18c318a11862189908187018c118b018730218ed18e3185018740f185c18aa186918761858189c188818f118971891183d18731818182918bc183718cf18cf18c8187215181c183f1850185e189c18ad1887185d131856181818b0188b18bf181e18ef18ec18d2187b18f018ea18fb18e3188618c01844185618fe18c518c31869181c0d18de1840182018d418e218a418ee18491853182a189718d7181e186018b818521886189b1518ac1857187b18aa186118e50a12182e188f187318cb18c1189f18c6020618b11880184f188918a2181e186d1880185e182518c618e6182618a218fd18bb18fc18fc188f189e189f1837182a18b91881181c18cd1862186a18591876183418a64cbb1876187b1518dd181c18bf1889189018871892182b18f218a618a0184218300d187a18500c161718bc184b184c184b14184c1842186218da189a18ba189d18231856182418a918bb18c418d7187918f1186f18bf18c118ef1853181a18ef18f518da1883181e183718a50f18a218a01845182b18e218d618a317182d18d318880f1894184118711118a218b518fa185e189216189e18a618cd183118fe188618af18311518f018661824182d0618441846188e186b1852186018266820703fb06cd00b7c084267c10d7e187bc052dfb904639eae17c95c5048c0a94e07ac21c1703fb06cd00b7c084267c10d7e187bc052dfb904639eae17c95c5048c0a94e0700000000"]'

echo "Testmempoolaccept"
bitcoin-cli testmempoolaccept "$PACKAGE"

echo "Submitting the package"
bitcoin-cli submitpackage "$PACKAGE" | tee ../var/regtest-submit.json

bitcoin-cli -generate 1

echo "Show tx"
bitcoin-cli gettransaction $(cat ../var/regtest-submit.json| jq -r '."tx-results" | to_entries[1].value.txid')

echo "Test the wallet"
$CHARMS wallet list


