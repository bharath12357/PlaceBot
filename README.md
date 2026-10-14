# 🤖 PlaceBot: AI Placement Interview Coach

A full-stack Generative AI web app that runs mock technical and HR interviews for
fresher software/IT candidates. Users create an account, practise by topic, and
every conversation is saved in a SQLite database so they can come back to it later.

Built with **Flask**, **SQLite**, the **Google Gemini API** and vanilla **HTML/CSS/JavaScript**.

## Features
- User registration and login (passwords hashed, never stored in plain text)
- Mock interview mode: one question at a time, with feedback after each answer
- Topic selector: General, DSA, OOP, DBMS, OS, SQL, HR/Behavioural
- Chat history saved per user in SQLite, with a sidebar to reopen or delete chats
- Conversation memory: previous messages are sent to the model with every request
- Responsive UI (works on phone and desktop)
- Automated tests (pytest) that run without an API key
- API key and secrets kept in environment variables

## Tech Stack
| Layer     | Technology                                        |
|-----------|---------------------------------------------------|
| Backend   | Python, Flask (REST-style JSON API)               |
| Database  | SQLite (`sqlite3`), foreign keys + cascade delete |
| AI        | Google Gemini API (`google-genai`)                |
| Frontend  | HTML, CSS, JavaScript (fetch API)                 |
| Testing   | pytest                                            |

## Project Structure
```
placebot/
├── app.py              # Flask app: routes, auth, chat API
├── ai_service.py       # Gemini API calls, topic prompts, history trimming
├── database.py         # SQLite connection helpers
├── schema.sql          # Database tables
├── requirements.txt
├── pytest.ini
├── .env.example        # Copy to .env and add your keys
├── .gitignore
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   └── chat.html
├── static/
│   ├── style.css
│   └── chat.js
└── tests/
    ├── conftest.py
    └── test_app.py
```

## Database Design
```
users (id, username UNIQUE, password_hash, created_at)
   │ 1
   │ ── many
conversations (id, user_id → users, title, topic, created_at)
   │ 1
   │ ── many
messages (id, conversation_id → conversations, role, content, created_at)
```
Deleting a conversation automatically deletes its messages (`ON DELETE CASCADE`).

## Setup
1. **Get a free API key** at https://aistudio.google.com/apikey
2. **Clone and enter the project**
   ```bash
   git clone https://github.com/<your-username>/placebot.git
   cd placebot
   ```
3. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   ```
4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
5. **Add your settings**
   ```bash
   cp .env.example .env            # Windows: copy .env.example .env
   ```
   Open `.env`, paste your `GEMINI_API_KEY`, and set `SECRET_KEY` to any long random string.
6. **Run**
   ```bash
   python app.py
   ```
   Open http://127.0.0.1:5000, create an account and start chatting.

   (macOS: if port 5000 is busy, set `PORT=5001` in `.env`.)

The database file `placebot.db` is created automatically on first run.

## Run the Tests
```bash
pip install pytest
pytest
```
The tests replace the AI call with a fake, so they need no API key or internet.

## API Endpoints
All `/api/*` routes require login and only return the logged-in user's own data.

| Method | Route                              | Description                         |
|--------|------------------------------------|-------------------------------------|
| GET    | `/`                                | Chat page                           |
| GET/POST | `/register`, `/login`            | Sign up / log in                    |
| POST   | `/logout`                          | Log out                             |
| GET    | `/api/conversations`               | List my conversations               |
| POST   | `/api/conversations`               | Create one (`{"topic": "dbms"}`)    |
| GET    | `/api/conversations/<id>/messages` | Load a conversation's messages      |
| POST   | `/api/conversations/<id>/chat`     | Send `{"message": "..."}`, get reply |
| DELETE | `/api/conversations/<id>`          | Delete a conversation               |

## How It Works
1. The browser sends your message to `/api/conversations/<id>/chat`.
2. Flask loads that conversation's earlier messages from SQLite.
3. `ai_service.py` sends the history plus a topic-specific **system prompt** to Gemini.
4. If the AI call succeeds, both your message and the reply are saved to the database.
   If it fails, nothing is saved, so the database never holds half-finished chats.

## Security Notes
- Passwords are hashed with Werkzeug (`generate_password_hash`).
- All SQL uses parameterised queries (no SQL injection).
- Every conversation lookup checks `user_id`, so users cannot read each other's chats.
- Messages are rendered with `textContent` (no XSS from AI or user text).
- `.env` is git-ignored, so keys never reach GitHub.

## Deploying (optional)
Add `gunicorn` to `requirements.txt`, then use the start command
`gunicorn "app:create_app()"` and set `GEMINI_API_KEY`, `GEMINI_MODEL` and `SECRET_KEY`
as environment variables on your host (e.g. Render). Note: free hosts often reset local
files, so SQLite data may be lost on redeploy. Use a persistent disk or PostgreSQL for
long-term storage.

## Future Improvements
- Answer scoring and a progress dashboard
- Streaming replies
- Markdown/code rendering in answers
- Rate limiting and CSRF protection for production
- PostgreSQL for deployment

## Screenshots
(Add screenshots of the login page and chat page here.)
