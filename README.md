# 🧠 Multi-Agent Research System

A fully offline, multi-agent AI system that collaborates to research, write, critique, and refine reports. Built with Python and Flask.

## 🤖 Agents

- **Researcher** – Gathers 5 key facts about your topic
- **Writer** – Drafts a structured report
- **Critic** – Provides 3 brutal, constructive feedback points
- **Writer (Revision)** – Improves the draft twice
- **Summariser** – Condenses the final report into an executive summary

## 🚀 Run it locally

```bash
pip install flask
python app.py
```

Then open `http://localhost:5000` in your browser.

## 🛠️ Tech Stack

- Python 3.11
- Flask (Web UI)
- 100% Mock Mode (No API keys required!)

## 📁 Project Structure

```
weekly_project_02/
├── app.py          # Web interface (Flask)
├── MAS.py          # Command-line version
└── .gitignore      # Git ignore rules
```

## 🎯 How it works

1. You enter a topic
2. **Researcher** finds 5 facts
3. **Writer** drafts a report
4. **Critic** gives feedback (twice!)
5. **Writer** revises the report (twice!)
6. **Summariser** creates an executive summary

## 📝 Example

Try this query:
> "The long-term effects of artificial intelligence on the global job market"

Watch all 5 agents collaborate to produce a po
