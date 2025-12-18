<div align="center">

<h1>
  <img src="https://readme-typing-svg.herokuapp.com?font=Fira+Code&size=40&duration=3000&pause=1000&color=6366F1&center=true&vCenter=true&width=600&lines=VOID!+%F0%9F%92%B3;Stripe+Hitter;Stripe+%7C+Checkout+%7C+Hitter" alt="Typing SVG" />
</h1>

<p>
  <img src="https://img.shields.io/badge/Node.js-43853D?style=for-the-badge&logo=node.js&logoColor=white" alt="Node.js"/>
  <img src="https://img.shields.io/badge/Stripe-008CDD?style=for-the-badge&logo=stripe&logoColor=white" alt="Stripe"/>
</p>

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&height=100&section=header&animation=twinkling" width="100%"/>

<p>
  <a href="https://t.me/victusxgod">
    <img src="https://img.shields.io/badge/Created%20by-@victusxgod-blue?style=for-the-badge&logo=telegram&logoColor=white&labelColor=0088cc" alt="Creator"/>
  </a>
</p>

<p>
  <img src="https://img.shields.io/badge/Status-Active-success?style=flat-square&logo=statuspage&logoColor=white" alt="Status"/>
  <img src="https://img.shields.io/badge/Version-2.0.0-blue?style=flat-square&logo=semver&logoColor=white" alt="Version"/>
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square&logo=opensourceinitiative&logoColor=white" alt="License"/>
  <img src="https://img.shields.io/badge/Gateways-2+-red?style=flat-square&logo=stripe&logoColor=white" alt="Gateways"/>
</p>

</div>

---

## 🎯 What is VOID!?

<div align="center">
  <img src="https://readme-typing-svg.herokuapp.com?font=Fira+Code&size=18&duration=2000&pause=500&color=22C55E&center=true&vCenter=true&multiline=true&width=800&height=100&lines=Stripe+Checkout+Hitter;Fast+%E2%9A%A1+Reliable+%F0%9F%94%92+Easy+to+Use+%F0%9F%9A%80" alt="Description"/>
</div>

VOID! is a **stripe checkout hitter** tool that allows you proccess payment through api directly.

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🚀 Speed & Performance
- ⚡ Fast response
- 🔄 Auto retry
- 📊 Own card supported
- 🎯 Gen card supported

</td>
<td width="50%">

### 🔐 Security & Reliability
- 🔑 API key authentication
- 📝 Debug mode logging
- ✅ Luhn validation

</td>
</tr>
<tr>
<td width="50%">
</td>
<td width="50%">

### 🌐 Deployment Ready
- ☁️ Vercel support
- 🚢 Render support
- 🐳 Docker ready
- 📦 One-click deploy

</td>
</tr>
</table>

---

## 🎬 Quick Start

<div align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&height=2" width="100%"/>
</div>

### 📦 Installation

```bash
git clone https://github.com/pixelnbit/stripe-hitter
cd stripe-hitter
npm install
```

### 🔧 Configuration

Create a `.env` file:

```env
PORT=8080
DEBUG_MODE=false
USE_API_KEY=false
API_KEY=your-secret-key
MAX_WORKERS=3
```

### ▶️ Run Locally

```bash
node proxy-server.js
```

<div align="center">
  <img src="https://img.shields.io/badge/Server%20Running-localhost:8080-success?style=for-the-badge&logo=nodedotjs&logoColor=white" alt="Server"/>
</div>

---

## 💳 Stripe Integration

<div align="center">
  <img src="https://readme-typing-svg.herokuapp.com?font=Fira+Code&size=24&duration=2000&pause=1000&color=635BFF&center=true&vCenter=true&width=500&lines=%F0%9F%94%B5+Stripe+Checkout+Automation" alt="Stripe"/>
</div>

### 🔍 Get Checkout Info

Extract session details from any Stripe checkout URL:

```bash
curl "http://localhost:8080/stripe/checkout-based/url/{CHECKOUT_URL}/info"
```

**Example:**
```bash
curl "http://localhost:8080/stripe/checkout-based/url/https://checkout.stripe.com/c/pay/cs_live_abc123.../info"
```

**Response:**
```json
{
  "sessionId": "cs_live_abc123...",
  "publicKey": "pk_live_xyz789...",
  "totals": {
    "total": 1999,
    "currency": "usd"
  },
  "merchant": {
    "name": "Cool Store",
    "country": "US"
  }
}
```

---

### 🎲 Generate Random Cards (BIN-based)

Test with randomly generated cards from a specific BIN:

```bash
curl "http://localhost:8080/stripe/checkout-based/url/{CHECKOUT_URL}/pay/gen/{BIN}?retry={N}"
```

**Parameters:**
- `{CHECKOUT_URL}`: Full Stripe checkout URL (URL-encoded)
- `{BIN}`: 6+ digit BIN number (e.g., `424242`, `555555`)
- `retry`: Number of attempts with different cards (0-10)

**Example:**
```bash
curl "http://localhost:8080/stripe/checkout-based/url/https%3A%2F%2Fcheckout.stripe.com%2Fc%2Fpay%2Fcs_live_abc123.../pay/gen/424242?retry=5"
```

**Response (Success):**
```json
{
  "success": true,
  "attempts": 2,
  "card": {
    "last4": "4242",
    "exp": "12/29"
  },
  "message": "Payment completed"
}
```

**Response (3DS Challenge):**
```json
{
  "success": true,
  "requires3DS": true,
  "attempts": 1,
  "card": {
    "last4": "4242",
    "exp": "12/29"
  },
  "paymentIntent": {
    "id": "pi_...",
    "status": "requires_action"
  },
  "message": "Payment method accepted (3DS challenge required)"
}
```

---

### 💳 Use Specific Card

Use with exact card details (no retries):

```bash
curl "http://localhost:8080/stripe/checkout-based/url/{CHECKOUT_URL}/pay/cc/{CARD_DATA}"
```

**Card Format:** `number|month|year|cvv`

**Example:**
```bash
curl "http://localhost:8080/stripe/checkout-based/url/https%3A%2F%2Fcheckout.stripe.com%2Fc%2Fpay%2Fcs_live_abc123.../pay/cc/4242424242424242%7C12%7C25%7C123"
```

**Response:**
```json
{
  "success": true,
  "attempts": 1,
  "card": {
    "last4": "4242",
    "exp": "12/25"
  },
  "message": "Payment completed"
}
```

---

### 🔄 Retry Logic

**Important:** Retry only works with `/gen/` endpoint!

- `/pay/gen/{bin}?retry=5` → Tries **5 different random cards** from same BIN
- `/pay/cc/{card}` → Tries specific card **once only** (retry ignored)

Each retry generates a **new random card** with valid:
- ✅ Luhn checksum
- ✅ Future expiration date
- ✅ Correct CVC length
- ✅ Proper card length (14-16 digits)

---

## 🌐 Deployment

<div align="center">
  <img src="https://capsule-render.vercel.app/api?type=soft&color=gradient&height=80&section=header&text=Deploy%20Anywhere&fontSize=40&animation=fadeIn" width="100%"/>
</div>

### ▲ Vercel

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/pixelnbit/stripe-hitter)

Or manually:

```bash
npm install -g vercel
vercel
```

### 🚢 Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

### 🐳 Docker

```bash
docker build -t void-payment .
docker run -p 8080:8080 void-payment
```

### ☁️ Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/pixelnbit/stripe-hitter)

---

## 📊 API Reference

<details>
<summary><b>🔵 Stripe Endpoints</b></summary>

### Get Checkout Info
```
GET /stripe/checkout-based/url/{url}/info
```

### Generate Cards (BIN)
```
GET /stripe/checkout-based/url/{url}/pay/gen/{bin}?retry={n}
```

### Use Specific Card
```
GET /stripe/checkout-based/url/{url}/pay/cc/{card}
```

</details>

---

## 🛠️ Advanced Configuration

```env
PORT=8080                    # Server port
DEBUG_MODE=true              # Enable debug logs
USE_API_KEY=true             # Require API key
API_KEY=your-secret-key      # API authentication
MAX_WORKERS=3                # Concurrent requests
```

### 🔐 API Key Authentication

```bash
curl -H "X-API-Key: your-key" "http://localhost:8080/stripe/..."
```

---

## 📸 Screenshots

<div align="center">

### Server Startup
```
$$\    $$\  $$$$$$\  $$$$$$\ $$$$$$$\  $$\ 
$$ |   $$ |$$  __$$\ \_$$  _|$$  __$$\ $$ |
$$ |   $$ |$$ /  $$ |  $$ |  $$ |  $$ |$$ |
\$$\  $$  |$$ |  $$ |  $$ |  $$ |  $$ |$$ |
 \$$\$$  / $$ |  $$ |  $$ |  $$ |  $$ |\__|
  \$$$  /  $$ |  $$ |  $$ |  $$ |  $$ |    
   \$  /    $$$$$$  |$$$$$$\ $$$$$$$  |$$\ 
    \_/     \______/ \______|\_______/ \__|

=================================================
Port:        8080
Workers:     3 concurrent
API Key:     DISABLED
Debug Mode:  ENABLED
=================================================
```

</div>

---

## 🤝 Contributing

<div align="center">
  <img src="https://readme-typing-svg.herokuapp.com?font=Fira+Code&size=20&duration=2000&pause=1000&color=F77F00&center=true&vCenter=true&width=600&lines=Contributions+are+Welcome!;Found+a+Bug%3F+Report+It!;Want+a+Feature%3F+Request+It!" alt="Contributing"/>
</div>

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📜 License

MIT License - see [LICENSE](LICENSE) file for details

---

## ⚠️ Disclaimer

<div align="center">

**This tool is for educational and testing purposes only.**

- 🔒 Use only with proper authorization
- 🎓 Intended for learning and QA testing
- ⚖️ Not responsible for misuse
- 🛡️ Follow payment gateway ToS

</div>

---

## 📞 Contact & Support

<div align="center">

### Created by [@victusxgod](https://t.me/victusxgod)

<p>
  <a href="https://t.me/victusxgod">
    <img src="https://img.shields.io/badge/Telegram-@victusxgod-blue?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram"/>
  </a>
</p>

<img src="https://readme-typing-svg.herokuapp.com?font=Fira+Code&size=16&duration=3000&pause=1000&color=6366F1&center=true&vCenter=true&width=500&lines=Questions%3F+DM+on+Telegram!;Need+Help%3F+Open+an+Issue!;Want+Updates%3F+Star+the+Repo!" alt="Contact"/>

</div>

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&height=100&section=footer&animation=twinkling" width="100%"/>

### ⭐ Star this repo if you found it helpful!

<img src="https://img.shields.io/github/stars/pixelnbit/stripe-hitter?style=social" alt="Stars"/>
<img src="https://img.shields.io/github/forks/pixelnbit/stripe-hitter?style=social" alt="Forks"/>

**Made with ❤️ by [@victusxgod](https://t.me/victusxgod)**

</div>
