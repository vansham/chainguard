from flask import Flask, request, jsonify, send_file, send_file
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

# One time token approval
try:
    opg_amount = Web3.to_wei(1, "ether")
    client.llm.ensure_opg_approval(opg_amount)
    print("OPG approval successful!")
except Exception as e:
    print(f"Approval note: {e}")


# =============================================
# TOOL FUNCTIONS - Agent yeh call karta hai
# =============================================

def fetch_eth_balance(address: str) -> str:
    """Fetch ETH balance from Etherscan"""
    try:
        res = requests.get("https://api.etherscan.io/v2/api", params={
            "module": "account", "action": "balance",
            "address": address, "tag": "latest",
            "chainid": "1", "apikey": ETHERSCAN_API_KEY
        })
        data = res.json()
        if data["status"] == "1":
            eth = round(int(data["result"]) / 1e18, 4)
            return f"{eth} ETH"
        return "0 ETH"
    except:
        return "Error fetching balance"


def fetch_transactions(address: str) -> dict:
    """Fetch transaction history from Etherscan"""
    try:
        res = requests.get("https://api.etherscan.io/v2/api", params={
            "module": "account", "action": "txlist",
            "address": address, "page": 1, "offset": 20,
            "sort": "desc", "chainid": "1", "apikey": ETHERSCAN_API_KEY
        })
        txs = res.json().get("result", [])
        if not isinstance(txs, list):
            return {"total": 0, "failed": 0, "contracts": 0, "failed_rate": 0}
        total = len(txs)
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


def fetch_tokens(address: str) -> dict:
    """Fetch ERC20 token interactions from Etherscan"""
    try:
        res = requests.get("https://api.etherscan.io/v2/api", params={
            "module": "account", "action": "tokentx",
            "address": address, "page": 1, "offset": 30,
            "sort": "desc", "chainid": "1", "apikey": ETHERSCAN_API_KEY
        })
        txs = res.json().get("result", [])
        if not isinstance(txs, list):
            return {"count": 0, "tokens": [], "suspicious": 0}
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
        return {"count": 0, "tokens": [], "suspicious": 0}


# =============================================
# TOOL DEFINITIONS for OpenGradient Agent
# =============================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_wallet_balance",
            "description": "Get the ETH balance of an Ethereum wallet address",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "The Ethereum wallet address (0x...)"
                    }
                },
                "required": ["address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_transaction_history",
            "description": "Get transaction history and analyze patterns like failed transactions",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "The Ethereum wallet address"
                    }
                },
                "required": ["address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_token_interactions",
            "description": "Analyze ERC20 token interactions to detect risky or suspicious tokens",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "The Ethereum wallet address"
                    }
                },
                "required": ["address"]
            }
        }
    }
]


def execute_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a tool and return result as string"""
    address = tool_args.get("address", "")

    if tool_name == "get_wallet_balance":
        result = fetch_eth_balance(address)
        return f"ETH Balance: {result}"

    elif tool_name == "get_transaction_history":
        data = fetch_transactions(address)
        return f"""Transaction History:
- Total Transactions: {data['total']}
- Failed Transactions: {data['failed']}
- Failed Rate: {data['failed_rate']}%
- Unique Contracts Interacted: {data['contracts']}
- Activity Level: {'Active' if data['total'] > 10 else 'Low Activity' if data['total'] > 0 else 'New/Empty Wallet'}"""

    elif tool_name == "get_token_interactions":
        data = fetch_tokens(address)
        return f"""Token Interactions:
- Total Token Transfers: {data['count']}
- Unique Tokens: {data.get('unique', 0)}
- Tokens Found: {', '.join(data['tokens']) if data['tokens'] else 'None'}
- Suspicious/Unknown Tokens: {data['suspicious']}
- Token Risk: {'HIGH - many suspicious tokens' if data['suspicious'] > 3 else 'LOW - mostly known tokens'}"""

    return "Tool not found"


# =============================================
# AGENT LOOP - OpenGradient TEE Verified!
# =============================================

def run_agent(address: str):
    """
    Real agent loop:
    1. LLM decides which tool to call
    2. Tool executes (Etherscan fetch)
    3. Result goes back to LLM
    4. Repeat until final answer
    5. All via OpenGradient TEE - verified!
    """
    
    messages = [
        {
            "role": "system",
            "content": """You are ChainGuard, an expert DeFi wallet security analyzer.
You have access to blockchain tools. Use them to analyze wallets thoroughly.
Always use ALL available tools before giving your final risk assessment.
Be specific and data-driven."""
        },
        {
            "role": "user",
            "content": f"""Analyze this Ethereum wallet: {address}

Use your tools to gather data, then provide:

RISK_SCORE: [0-100]
RISK_LEVEL: [SAFE / LOW RISK / MEDIUM RISK / HIGH RISK / CRITICAL]

SUMMARY:
[2-3 sentences about wallet health]

RISK_FACTORS:
- [specific risk based on data]
- [specific risk based on data]

POSITIVE_SIGNALS:
- [positive finding]
- [positive finding]

RECOMMENDATIONS:
- [actionable advice 1]
- [actionable advice 2]
- [actionable advice 3]

Risk scoring guide:
- 0-20: Safe wallet, good history
- 21-40: Low risk, minor concerns
- 41-60: Medium risk, some issues
- 61-80: High risk, significant issues
- 81-100: Critical, very risky"""
        }
    ]

    tools_used = []
    max_iterations = 6  # Prevent infinite loop

    for iteration in range(max_iterations):
        # Call OpenGradient LLM - TEE verified!
        result = client.llm.chat(
            model="openai/gpt-4o",
            messages=messages,
            tools=TOOLS
        )

        response = result.chat_output

        # Check if agent wants to use a tool
        if response.get('tool_calls'):
            # Process each tool call
            tool_results = []
            for tool_call in response['tool_calls']:
                tool_name = tool_call['function']['name']
                tool_args = json.loads(tool_call['function']['arguments'])
                
                print(f"Agent calling tool: {tool_name} with {tool_args}")
                tools_used.append(tool_name)
                
                # Execute the tool
                tool_result = execute_tool(tool_name, tool_args)
                
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tool_call['id'],
                    "content": tool_result
                })

            # Add assistant message with tool calls
            messages.append({"role": "assistant", "content": None, "tool_calls": response['tool_calls']})
            # Add tool results
            messages.extend(tool_results)

        else:
            # Agent gave final answer - no more tool calls
            final_answer = response.get('content', '')
            return final_answer, tools_used

    # If max iterations reached, get final answer
    result = client.llm.chat(
        model="openai/gpt-4o",
        messages=messages
    )
    return result.chat_output.get('content', 'Analysis complete'), tools_used


# =============================================
# API ENDPOINTS
# =============================================

@app.route('/analyze', methods=['POST'])
def analyze_wallet():
    try:
        data = request.json
        address = data.get('address', '').strip()

        if not address:
            return jsonify({"error": "Wallet address required"}), 400
        if not address.startswith('0x') or len(address) != 42:
            return jsonify({"error": "Invalid Ethereum address format"}), 400

        # Run the agent!
        final_answer, tools_used = run_agent(address)

        # Also get raw wallet data for stats
        tx_data = fetch_transactions(address)
        token_data = fetch_tokens(address)
        eth_balance = fetch_eth_balance(address)

        # Parse agent response
        parsed = parse_response(final_answer)
        parsed["tools_used"] = tools_used

        return jsonify({
            "success": True,
            "address": address,
            "wallet_stats": {
                "eth_balance": eth_balance,
                "total_transactions": tx_data["total"],
                "failed_transactions": tx_data["failed"],
                "failed_rate": tx_data["failed_rate"],
                "token_transfers": token_data["count"],
                "tokens": token_data["tokens"][:5]
            },
            "analysis": parsed,
            "agent_info": {
                "tools_called": tools_used,
                "tools_count": len(tools_used),
                "powered_by": "OpenGradient Verifiable AI",
                "inference_type": "TEE-Secured (AWS Nitro Enclave)",
                "payment": "x402 Protocol on Base Sepolia",
                "verification": "On-chain hash stored"
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
        elif line.startswith("RISK_LEVEL:"):
            parsed["risk_level"] = line.split(":", 1)[1].strip()
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
        "status": "ChainGuard Agent running!",
        "agent": "OpenGradient Tool-Use Agent",
        "tools": ["get_wallet_balance", "get_transaction_history", "get_token_interactions"],
        "inference": "TEE-Secured via OpenGradient",
        "payment": "x402 Protocol"
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)

@app.route('/')
def home():
    return send_file('index.html')
