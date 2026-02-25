# 🔒 AI Smart Contract Auditor

AI-powered security auditor for Solidity smart contracts using OpenGradient & GPT-4.

## 🌐 Live Demo

**Frontend:** https://opengradient-auditor.vercel.app

**Backend API:** https://web-production-6560.up.railway.app

## ✨ Features

- 🤖 AI-powered vulnerability detection using GPT-4
- 🔍 Security scoring (0-100)
- ⚠️ Issue categorization (Critical/High/Medium)
- 📊 Real-time analysis
- 🎨 Beautiful UI with gradient design
- ✅ Verifiable AI execution via OpenGradient

## 🛠️ Tech Stack

**Frontend:**
- HTML/CSS/JavaScript
- Tailwind CSS
- Deployed on Vercel

**Backend:**
- Python 3.12
- Flask
- OpenGradient SDK v0.7.4
- Web3.py
- Deployed on Railway

**AI:**
- OpenGradient Platform
- GPT-4 (via TEE execution)
- On-chain verifiable results

## 🚀 Quick Start

### Backend (Local)
```bash
cd server
pip install -r requirements.txt
export OG_PRIVATE_KEY=your_private_key
python server.py
```

### Frontend (Local)
```bash
cd frontend
# Open index.html in browser
# Or use: python -m http.server 8080
```

## 📖 How It Works

1. **User** pastes Solidity contract code
2. **Frontend** sends code to Flask API
3. **Backend** uses OpenGradient SDK to call GPT-4
4. **AI** analyzes contract for vulnerabilities
5. **Results** displayed with security score & issues

## 🔐 Security Checks

- ✅ Reentrancy attacks
- ✅ Access control issues
- ✅ Integer overflow/underflow
- ✅ Unchecked external calls
- ✅ Front-running vulnerabilities

## 📸 Screenshots

![Demo](https://opengradient-auditor.vercel.app)

## 🤝 Contributing

Built for the OpenGradient community showcase.

## 📝 License

MIT

## 🙏 Acknowledgments

- OpenGradient team for the amazing SDK
- GPT-4 for AI analysis
- Inspired by OpenAI's EVM-Bench

---

**Built with ❤️ using OpenGradient**