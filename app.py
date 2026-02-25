from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import opengradient as og
from web3 import Web3
import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

PRIVATE_KEY = os.getenv('OG_PRIVATE_KEY')
ETHERSCAN_API_KEY = os.getenv('ETHERSCAN_API_KEY')

# Initialize OpenGradient client
client = og.Client(private_key=PRIVATE_KEY)

try:
    opg_amount = Web3.to_wei(0.1, 'ether')
    client.llm.ensure_opg_approval(opg_amount)
    print("OPG approval successful!")
except Exception as e:
    print(f"Approval note: {e}")


# =============================================
# MULTI-CHAIN CONFIG
# =============================================

CHAINS = {
    "ethereum": {
        "id": "1",
        "name": "Ethereum",
        "symbol": "ETH",
        "explorer": "https://etherscan.io"
    },
    "arbitrum": {
        "id": "42161",
        "name": "Arbitrum",
        "symbol": "ETH",
        "explorer": "https://arbiscan.io"
    }
}



# =============================================
# TOOL FUNCTIONS
# =============================================

def fetch_eth_balance(address: str, chain_id: str) -> str:
    try:
        res = requests.get("https://api.etherscan.io/v2/api", params={
            "chainid": chain_id,
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
            "apikey": ETHERSCAN_API_KEY
        })
        data = res.json()
        if data["status"] == "1":
            bal = round(int(data["result"]) / 1e18, 4)
            return str(bal)
        return "0"
    except:
        return "0"


def fetch_transactions(address: str, chain_id: str) -> dict:
    try:
        # Total count fetch karo
        res_count = requests.get("https://api.etherscan.io/v2/api", params={
            "chainid": chain_id,
            "module": "account",
            "action": "txlist",
            "address": address,
            "page": 1,
            "offset": 10000,
            "sort": "desc",
            "apikey": ETHERSCAN_API_KEY
        })
        all_txs = res_count.json().get("result", [])
        total = len(all_txs) if isinstance(all_txs, list) else 0

        # Recent 20 for analysis
        res = requests.get("https://api.etherscan.io/v2/api", params={
            "chainid": chain_id,
            "module": "account",
            "action": "txlist",
            "address": address,
            "page": 1,
            "offset": 20,
            "sort": "desc",
            "apikey": ETHERSCAN_API_KEY
        })
        txs = res.json().get("result", [])
        if not isinstance(txs, list):
            return {"total": total, "failed": 0, "contracts": 0, "failed_rate": 0}
        failed = len([t for t in txs if t.get("isError") == "1"])
        contracts = len(set(t.get("to", "") for t in txs if t.get("to")))
        return {
            "total": total,
            "failed": failed,
            "contracts": contracts,
            "failed_rate": round(failed/total*100, 1) if total > 0 else 0
        }
    except:
        return {"total": 0, "failed": 0, "contracts": 0, "failed_rate": 0}


def fetch_tokens(address: str, chain_id: str) -> dict:
    try:
        res = requests.get("https://api.etherscan.io/v2/api", params={
            "chainid": chain_id,
            "module": "account",
            "action": "tokentx",
            "address": address,
            "page": 1,
            "offset": 30,
            "sort": "desc",
            "apikey": ETHERSCAN_API_KEY
        })
        txs = res.json().get("result", [])
        if not isinstance(txs, list):
            return {"count": 0, "tokens": [], "unique": 0, "suspicious": 0}
        tokens = {}
        for tx in txs:
            sym = tx.get("tokenSymbol", "UNKNOWN")
            tokens[sym] = tokens.get(sym, 0) + 1
        suspicious = sum(1 for t in tokens.keys() if len(t) > 15 or t == "UNKNOWN")
        return {
            "count": len(txs),
            "tokens": list(tokens.keys())[:15],
            "unique": len(tokens),
            "suspicious": suspicious
        }
    except:
        return {"count": 0, "tokens": [], "unique": 0, "suspicious": 0}


# =============================================
# TOOL DEFINITIONS
# =============================================

def get_tools(chain_name: str, symbol: str):
    return [
        {
            "type": "function",
            "function": {
                "name": "get_wallet_balance",
                "description": f"Get the {symbol} balance of a wallet on {chain_name}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "address": {"type": "string", "description": "Wallet address"}
                    },
                    "required": ["address"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_transaction_history",
                "description": f"Get transaction history on {chain_name}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "address": {"type": "string", "description": "Wallet address"}
                    },
                    "required": ["address"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_token_interactions",
                "description": f"Get token interactions on {chain_name}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "address": {"type": "string", "description": "Wallet address"}
                    },
                    "required": ["address"]
                }
            }
        }
    ]


def execute_tool(tool_name: str, tool_args: dict, chain_id: str, symbol: str) -> str:
    address = tool_args.get("address", "")
    if tool_name == "get_wallet_balance":
        bal = fetch_eth_balance(address, chain_id)
        return f"Balance: {bal} {symbol}"
    elif tool_name == "get_transaction_history":
        data = fetch_transactions(address, chain_id)
        return f"""Transaction History:
- Total: {data['total']}
- Failed: {data['failed']}
- Failed Rate: {data['failed_rate']}%
- Unique Contracts: {data['contracts']}
- Activity: {'Active' if data['total'] > 10 else 'Low' if data['total'] > 0 else 'New Wallet'}"""
    elif tool_name == "get_token_interactions":
        data = fetch_tokens(address, chain_id)
        return f"""Token Interactions:
- Total Transfers: {data['count']}
- Unique Tokens: {data['unique']}
- Tokens: {', '.join(data['tokens']) if data['tokens'] else 'None'}
- Suspicious: {data['suspicious']}
- Risk: {'HIGH' if data['suspicious'] > 3 else 'LOW'}"""
    return "Tool not found"


# =============================================
# AGENT LOOP
# =============================================

def run_agent(address: str, chain: dict):
    messages = [
        {
            "role": "system",
            "content": f"You are ChainGuard, a DeFi wallet security analyzer for {chain['name']} blockchain. Use tools to analyze wallets. Be specific and data-driven."
        },
        {
            "role": "user",
            "content": f"""Analyze this {chain['name']} wallet: {address}

Use all tools, then provide:

RISK_SCORE: [0-100]
RISK_LEVEL: [SAFE / LOW RISK / MEDIUM RISK / HIGH RISK / CRITICAL]

SUMMARY:
[2-3 sentences about wallet health on {chain['name']}]

RISK_FACTORS:
- [risk 1]
- [risk 2]

POSITIVE_SIGNALS:
- [positive 1]
- [positive 2]

RECOMMENDATIONS:
- [action 1]
- [action 2]
- [action 3]"""
        }
    ]

    tools_used = []
    TOOLS = get_tools(chain['name'], chain['symbol'])

    for _ in range(6):
        result = client.llm.chat(
            model="openai/gpt-4o",
            messages=messages,
            tools=TOOLS
        )
        response = result.chat_output

        if response.get('tool_calls'):
            tool_results = []
            for tc in response['tool_calls']:
                name = tc['function']['name']
                args = json.loads(tc['function']['arguments'])
                tools_used.append(name)
                tool_result = execute_tool(name, args, chain['id'], chain['symbol'])
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc['id'],
                    "content": tool_result
                })
            messages.append({"role": "assistant", "content": None, "tool_calls": response['tool_calls']})
            messages.extend(tool_results)
        else:
            return response.get('content', ''), tools_used

    result = client.llm.chat(model="openai/gpt-4o", messages=messages)
    return result.chat_output.get('content', 'Analysis complete'), tools_used


# =============================================
# API
# =============================================

@app.route('/')
def home():
    return send_file('index.html')


@app.route('/chains', methods=['GET'])
def get_chains():
    return jsonify({"chains": CHAINS})


@app.route('/analyze', methods=['POST'])
def analyze_wallet():
    try:
        data = request.json
        address = data.get('address', '').strip()
        chain_key = data.get('chain', 'ethereum').lower()

        if not address:
            return jsonify({"error": "Wallet address required"}), 400
        if not address.startswith('0x') or len(address) != 42:
            return jsonify({"error": "Invalid address format"}), 400
        if chain_key not in CHAINS:
            return jsonify({"error": "Unsupported chain"}), 400

        chain = CHAINS[chain_key]

        final_answer, tools_used = run_agent(address, chain)

        tx_data = fetch_transactions(address, chain['id'])
        token_data = fetch_tokens(address, chain['id'])
        balance = fetch_eth_balance(address, chain['id'])

        parsed = parse_response(final_answer)
        parsed["tools_used"] = tools_used

        return jsonify({
            "success": True,
            "address": address,
            "chain": chain,
            "wallet_stats": {
                "eth_balance": f"{balance} {chain['symbol']}",
                "total_transactions": tx_data["total"],
                "failed_transactions": tx_data["failed"],
                "failed_rate": tx_data["failed_rate"],
                "token_transfers": token_data["count"],
                "tokens": token_data["tokens"][:5]
            },
            "analysis": parsed,
            "agent_info": {
                "tools_called": tools_used,
                "powered_by": "OpenGradient Verifiable AI",
                "inference_type": "TEE-Secured (AWS Nitro Enclave)",
                "payment": "x402 Protocol"
            }
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500


def parse_response(text):
    lines = text.split('\n')
    parsed = {
        "risk_score": 50, "risk_level": "MEDIUM RISK",
        "summary": "", "risk_factors": [],
        "positive_signals": [], "recommendations": [],
        "raw": text
    }
    current = None
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith("RISK_SCORE:"):
            try:
                nums = ''.join(filter(str.isdigit, line.split(":", 1)[1]))
                parsed["risk_score"] = min(100, max(0, int(nums)))
            except: pass
        elif line.startswith("RISK_LEVEL:"): parsed["risk_level"] = line.split(":", 1)[1].strip()
        elif line.startswith("SUMMARY:"): current = "summary"
        elif line.startswith("RISK_FACTORS:"): current = "risk_factors"
        elif line.startswith("POSITIVE_SIGNALS:"): current = "positive_signals"
        elif line.startswith("RECOMMENDATIONS:"): current = "recommendations"
        elif line.startswith("- ") and current in ["risk_factors", "positive_signals", "recommendations"]:
            parsed[current].append(line[2:])
        elif current == "summary" and not any(line.startswith(x) for x in ["RISK", "POSITIVE", "RECOMMEND"]):
            parsed["summary"] += (" " + line if parsed["summary"] else line)
    return parsed


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ChainGuard Multi-Chain Agent running!",
        "chains": list(CHAINS.keys()),
        "powered_by": "OpenGradient Verifiable AI"
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
