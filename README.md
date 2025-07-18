# 🎙️ AAWAAZ.AI — Deployment Package for Render  
**Made with ❤️ by Heart**

---

## 🧠 Overview

**AAWAAZ.AI** is a modern, multilingual **Text-to-Speech (TTS)** web application offering **12 diverse voices**, a **public REST API**, and a built-in **analytics dashboard**.  
Designed for speed, simplicity, and swag — this is voice tech reimagined.

---

## 🚀 Quick Deploy to Render

### ✅ Option 1: Auto-Deploy (Recommended)
1. Upload this zip file to your GitHub repository
2. Connect the GitHub repo to [Render](https://render.com/)
3. Render will detect the `render.yaml` and auto-configure the service
4. Set up a **PostgreSQL database** via Render Dashboard
5. Boom! You're live.

### 🛠️ Option 2: Manual Setup
1. Create a new **Web Service** on Render
2. Upload all files manually
3. Set Build Command:
   ```bash
   pip install -r requirements.txt
Set Start Command:

bash
Copy
Edit
gunicorn --bind 0.0.0.0:$PORT main:app
Add a PostgreSQL database

Set required env variable:
SESSION_SECRET (auto-generated or set manually)

🔐 Environment Variables
Variable	Description
DATABASE_URL	PostgreSQL connection string (Render auto-provides)
SESSION_SECRET	Secret key for session encryption

✨ Features
🎧 12 Voice Models (Multilingual)

🔐 User Authentication

📊 Analytics Dashboard
(Username: heart, Password: heart)

🌍 Public TTS REST API at /api

🧾 Auto-generated API Docs at /api-docs

📡 Live Endpoints (Post Deployment)
Route	Description
/	Main TTS Interface
/api	Public API Endpoint
/api-docs	Swagger / OpenAPI Docs
/login	User Login
/signup	User Signup
/analytics/login	Analytics Dashboard (Admin Only)

🛡️ Security Notes
✅ Open redirect vulnerability patched

✅ Form inputs validated and sanitized

✅ Sessions securely managed

✅ Analytics dashboard password-protected

🛠️ Support
For bugs or deployment issues, refer to:

Official Flask documentation

Render deployment guides

Or just raise an issue here on GitHub!

🧬 License
This project is open source under the MIT License.

Made with ❤️ by Heart
Powered by Flask, gTTS & open source magic.

yaml
Copy
Edit

---

### 🧨 What’s special:
- Emojis for visual clarity (Gen Z style 😎)
- Code blocks and tables for dev friendliness
- Clean AF and **bossy tone** just like you
- Instantly README.md-ready 🔥

---

Next move:
- Push to your repo ✅
- Add a sexy logo/banner? (Want help designing one?)
- Wanna convert this into a GitHub Pages docs site later?

Tere README bhi bolta hai —  
**"Sun Awaaz.AI — Heart ke haathon likha gaya hai."** 💖🧠