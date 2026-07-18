from dotenv import load_dotenv
import os, json, requests
load_dotenv('.env')
from eth_account import Account
from hyperliquid.info import Info

addr = Account.from_key(os.environ['HL_PRIVATE_KEY']).address
info = Info('https://api.hyperliquid.xyz', skip_ws=True)

state = info.user_state(addr)
ms = state['marginSummary']
print("=== PERPS ACCOUNT ===")
print(f"Account value:   ${float(ms['accountValue']):.2f}")
print(f"Total margin:    ${float(ms['totalMarginUsed']):.2f}")
print(f"Withdrawable:    ${float(state['withdrawable']):.2f}")

spot = requests.post('https://api.hyperliquid.xyz/info',
                     json={'type': 'spotClearinghouseState', 'user': addr}).json()
usdc = next((b['total'] for b in spot['balances'] if b['coin'] == 'USDC'), '0')
print(f"\n=== SPOT ===")
print(f"USDC spot:       ${float(usdc):.2f}")

print(f"\n=== POSITIONS ===")
for p in state.get('assetPositions', []):
    pos = p['position']
    print(f"{pos['coin']}: szi={pos['szi']} entry=${float(pos['entryPx']):.3f} "
          f"uPnL=${float(pos['unrealizedPnl']):.2f} lev={pos['leverage']}")

print(f"\n=== OPEN ORDERS (incl. trigger/TP/SL) ===")
oo = info.open_orders(addr)
print(f"count={len(oo)}")
for o in oo:
    print(json.dumps(o))
