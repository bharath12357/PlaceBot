"""Everything that talks to the Google Gemini API lives here."""
import os

from google import genai
from google.genai import types

# topic key -> label shown in the UI + extra instruction for the model
TOPICS = {
    "general": {
        "label": "General Interview",
        "focus": "Mix questions from DSA basics, OOP, DBMS, OS, SQL and HR.",
    },
    "dsa": {
        "label": "Data Structures & Algorithms",
        "focus": "Focus on arrays, strings, linked lists, stacks, queues, trees, "
                 "sorting, searching and time complexity.",
    },
    "oop": {
        "label": "OOP Concepts",
        "focus": "Focus on classes, inheritance, polymorphism, abstraction, "
                 "encapsulation, interfaces and SOLID basics.",
    },
    "dbms": {
        "label": "DBMS",
        "focus": "Focus on normalization, keys, transactions, ACID, indexing and joins.",
    },
    "os": {
        "label": "Operating Systems",
        "focus": "Focus on processes, threads, scheduling, deadlocks, memory "
                 "management and synchronization.",
    },
    "sql": {
        "label": "SQL",
        "focus": "Focus on SELECT queries, joins, GROUP BY, subqueries and "
                 "writing small queries.",
    },
    "hr": {
        "label": "HR / Behavioural",
        "focus": "Focus on 'Tell me about yourself', strengths, weaknesses, "
                 "teamwork, conflict and career goals. Coach answer structure (STAR).",
    },
}

BASE_PROMPT = """You are PlaceBot, a friendly placement interview coach for
fresher software/IT candidates in India.
- If the user says 'start interview', ask ONE question at a time and wait
  for the answer.
- After each answer, give brief feedback (what was good, what was missing),
  then ask the next question.
- When explaining concepts, use simple language and a short example.
- Keep replies under 150 words unless the user asks for more detail.
Current topic: {label}. {focus}"""

MAX_HISTORY_MESSAGES = 20  # only the latest messages are sent, to save tokens

_client = None


def build_prompt(topic):
    info = TOPICS.get(topic, TOPICS["general"])
    return BASE_PROMPT.format(label=info["label"], focus=info["focus"])


def trim_history(history, limit=MAX_HISTORY_MESSAGES):
    """Keep the latest `limit` messages and make sure the first one is from the user."""
    trimmed = list(history[-limit:])
    while trimmed and trimmed[0]["role"] != "user":
        trimmed.pop(0)
    return trimmed


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def generate_reply(topic, history):
    """history: list of {"role": "user"|"model", "content": str}, ending with the new user message."""
    contents = [
        types.Content(role=m["role"], parts=[types.Part(text=m["content"])])
        for m in trim_history(history)
    ]
    response = _get_client().models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=build_prompt(topic)),
    )
    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("The AI returned an empty response. Please try rephrasing.")
    return text
