from flask import Flask, request, jsonify
from flask_cors import CORS
import opengradient as og
from web3 import Web3
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

PRIVATE_KEY = os.getenv('OG_PRIVATE_KEY')
ETHERSCAN_API_KEY = os.getenv('ETHERSCAN_API_KEY')

client = og.Client(private_key=PRIVATE_KEY)

# One time token approval
try:
    opg_amount = Web3.to_wei(0.1, 'ether')
    client.llm.ensure_opg_approval(opg_amount)
except Exception as e:
    print(f"Approval note: {e}")


def get_wallet_data(address):
    """Fetch all wallet data from Etherscan"""
    base_url = "https://api.etherscan.io/api"
    data = {}

    # ETH Balance
    balance_res = requests.get(base_url, params={
        "module": "account",
        "action": "balance",
        "address": address,
        "tag": "latest",
        "apikey": ETHERSCAN_API_KEY
    })
    balance_data = balance_res.json()
    if balance_data["status"] == "1":
        eth_balance = int(balance_data["result"]) / 1e18
        data["eth_balance"] = round(eth_balance, 4)
    else:
        data["eth_balance"] = 0

    # Transaction History (last 20)
    tx_res = requests.get(base_url, params={
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": 20,
        "sort": "desc",
        "apikey": ETHERSCAN_API_KEY
    })
    tx_data = tx_res.json()
    transactions = tx_data.get("result", [])
    if isinstance(transactions, list):
        data["total_transactions"] = len(transactions)
        failed_txs = [tx for tx in transactions if tx.get("isError") == "1"]
        data["failed_transactions"] = len(failed_txs)
        
        # Unique contracts interacted with
        contracts = set()
        for tx in transactions:
            if tx.get("to"):
                contracts.add(tx["to"].lower())
        data["unique_contracts"] = len(contracts)
        
        # Recent activity
        if transactions:
            data["last_tx_age_days"] = "recent"
            data["sample_transactions"] = [
                {
                    "hash": tx["hash"][:20] + "...",
                    "value_eth": round(int(tx.get("value", 0)) / 1e18, 4),
                    "is_error": tx.get("isError") == "1",
                    "to": tx.get("to", "")[:20] + "..." if tx.get("to") else "Contract Creation"
                }
                for tx in transactions[:5]
            ]
    else:
        data["total_transactions"] = 0
        data["failed_transactions"] = 0
        data["unique_contracts"] = 0

    # ERC20 Token Transfers
    token_res = requests.get(base_url, params={
        "module": "account",
        "action": "tokentx",
        "address": address,
        "page": 1,
        "offset": 20,
        "sort": "desc",
        "apikey": ETHERSCAN_API_KEY
    })
    token_data = token_res.json()
    token_txs = token_data.get("result", [])
    if isinstance(token_txs, list):
        token_names = set()
        for tx in token_txs:
            token_names.add(tx.get("tokenSymbol", "UNKNOWN"))
        data["tokens_interacted"] = list(token_names)[:10]
        data["token_transfer_count"] = len(token_txs)
    else:
        data["tokens_interacted"] = []
        data["token_transfer_count"] = 0

    return data


def analyze_with_ai(address, wallet_data):
    """Send wallet data to OpenGradient for AI risk analysis"""
    
    prompt = f"""You are ChainGuard, an expert DeFi wallet security analyzer powered by verifiable AI on OpenGradient.

Analyze this Ethereum wallet and provide a comprehensive risk assessment:

WALLET ADDRESS: {address}

WALLET DATA:
- ETH Balance: {wallet_data.get('eth_balance', 0)} ETH
- Total Transactions (last 20): {wallet_data.get('total_transactions', 0)}
- Failed Transactions: {wallet_data.get('failed_transactions', 0)}
- Unique Contracts Interacted: {wallet_data.get('unique_contracts', 0)}
- Token Transfers: {wallet_data.get('token_transfer_count', 0)}
- Tokens Interacted: {', '.join(wallet_data.get('tokens_interacted', [])) or 'None'}
- Recent Transactions: {wallet_data.get('sample_transactions', [])}

Provide analysis in this EXACT format:

RISK_SCORE: [number 0-100, where 0=very safe, 100=very risky]

RISK_LEVEL: [one of: SAFE / LOW RISK / MEDIUM RISK / HIGH RISK / CRITICAL]

SUMMARY:
[2-3 sentence overview of wallet health and activity]

RISK_FACTORS:
- [risk factor 1]
- [risk factor 2]
- [risk factor 3]

POSITIVE_SIGNALS:
- [positive signal 1]
- [positive signal 2]

RECOMMENDATIONS:
- [recommendation 1]
- [recommendation 2]
- [recommendation 3]

Be specific, data-driven, and focus on DeFi security risks like:
- High failure rate (>20% failed txs = risky)
- Too many unknown token interactions
- Suspicious contract patterns
- Low activity (new wallet = higher risk)
- High ETH balance with risky behavior"""

    result = client.llm.chat(
        model="openai/gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    
    return result.chat_output['content']


def parse_ai_response(ai_text):
    """Parse AI response into structured data"""
    lines = ai_text.split('\n')
    
    parsed = {
        "risk_score": 50,
        "risk_level": "MEDIUM RISK",
        "summary": "",
        "risk_factors": [],
        "positive_signals": [],
        "recommendations": [],
        "raw": ai_text
    }
    
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("RISK_SCORE:"):
            try:
                score = int(''.join(filter(str.isdigit, line.split(":")[1])))
                parsed["risk_score"] = min(100, max(0, score))
            except:
                pass
                
        elif line.startswith("RISK_LEVEL:"):
            parsed["risk_level"] = line.split(":", 1)[1].strip()
            
        elif line.startswith("SUMMARY:"):
            current_section = "summary"
            
        elif line.startswith("RISK_FACTORS:"):
            current_section = "risk_factors"
            
        elif line.startswith("POSITIVE_SIGNALS:"):
            current_section = "positive_signals"
            
        elif line.startswith("RECOMMENDATIONS:"):
            current_section = "recommendations"
            
        elif line.startswith("- ") and current_section in ["risk_factors", "positive_signals", "recommendations"]:
            parsed[current_section].append(line[2:])
            
        elif current_section == "summary" and not line.startswith(("RISK", "POSITIVE", "RECOMMEND")):
            if parsed["summary"]:
                parsed["summary"] += " " + line
            else:
                parsed["summary"] = line
    
    return parsed


@app.route('/analyze', methods=['POST'])
def analyze_wallet():
    try:
        data = request.json
        address = data.get('address', '').strip()
        
        # Validate address
        if not address:
            return jsonify({"error": "Wallet address required"}), 400
        
        if not address.startswith('0x') or len(address) != 42:
            return jsonify({"error": "Invalid Ethereum address format"}), 400
        
        # Fetch wallet data
        wallet_data = get_wallet_data(address)
        
        # AI Analysis via OpenGradient
        ai_response = analyze_with_ai(address, wallet_data)
        
        # Parse response
        parsed = parse_ai_response(ai_response)
        
        return jsonify({
            "success": True,
            "address": address,
            "wallet_data": wallet_data,
            "analysis": parsed
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ChainGuard is running!", "powered_by": "OpenGradient"})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
