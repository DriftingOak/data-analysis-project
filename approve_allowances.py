"""Approve USDC allowances for Polymarket contracts on Polygon."""
from web3 import Web3
import os
import time

w3 = Web3(Web3.HTTPProvider("https://polygon-bor-rpc.publicnode.com"))
pk = os.getenv("PRIVATE_KEY")
acct = w3.eth.account.from_key(pk)
print(f"Wallet: {acct.address}")

gas_price = max(w3.eth.gas_price * 2, w3.to_wei(100, 'gwei'))
print(f"Gas price: {w3.from_wei(gas_price, 'gwei'):.1f} gwei")

usdc = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
# Full ERC20 ABI for approve
abi = [
    {"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
]
contract = w3.eth.contract(address=Web3.to_checksum_address(usdc), abi=abi)

# Approve 100 USDC (6 decimals) instead of max
approve_amt = 100 * 10**6

spenders = [
    "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
    "0xC5d563A36AE78145C45a50134d48A1215220f80a",
    "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
]

for i, addr in enumerate(spenders):
    checksum_addr = Web3.to_checksum_address(addr)
    
    # Check current allowance
    current = contract.functions.allowance(acct.address, checksum_addr).call()
    print(f"\n[{i+1}/3] {addr}")
    print(f"  Current allowance: {current}")
    
    if current >= approve_amt:
        print("  Already approved, skipping")
        continue
    
    nonce = w3.eth.get_transaction_count(acct.address)
    
    # Estimate gas first
    try:
        est_gas = contract.functions.approve(checksum_addr, approve_amt).estimate_gas({"from": acct.address})
        print(f"  Estimated gas: {est_gas}")
        use_gas = int(est_gas * 1.5)
    except Exception as e:
        print(f"  Gas estimation failed: {e}")
        print("  Skipping this address")
        continue
    
    tx = contract.functions.approve(
        checksum_addr, approve_amt
    ).build_transaction({
        "from": acct.address,
        "nonce": nonce,
        "gas": use_gas,
        "gasPrice": gas_price,
    })
    signed = acct.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  Sent tx: {h.hex()}")
    
    receipt = w3.eth.wait_for_transaction_receipt(h, timeout=120)
    print(f"  Status: {receipt.status} (1=success)")
    
    if i < len(spenders) - 1:
        time.sleep(5)

print("\nDone!")
