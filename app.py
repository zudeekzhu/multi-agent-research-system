#!/usr/bin/env python3
"""
Multi-Agent System - Web Interface
Run this file, then open http://localhost:5000 in your browser
"""

from flask import Flask, render_template_string, request, jsonify
import json
import os
import time
import random
import re

app = Flask(__name__)

# ==================== COPY YOUR ENTIRE MAS CODE HERE ====================
# (Paste everything from your MAS.py file here, from the very top
#  down to the bottom. Then add the routes below.)
# ========================================================================

# --- I'll paste the full working code for you below ---
# (Just copy everything from here to the bottom)

MOCK_MODE = True
MODEL_NAME = "claude-sonnet-4-6"
MAX_RETRIES = 2

MOCK_RESEARCH_DB = {
    "artificial intelligence": [
        "AI-driven automation could displace 85 million jobs globally by 2027, per WEF estimates.",
        "Simultaneously, AI is projected to create 97 million new roles centered on human-machine collaboration.",
        "Sectors like manufacturing and customer service show the highest automation exposure (>60%).",
        "Reskilling programs in the EU and Singapore have reduced AI-related unemployment spikes by ~15%.",
        "Generative AI tools are now augmenting, not replacing, creative and knowledge-work roles in 40% of surveyed firms."
    ],
    "climate": [
        "Global average temperatures have risen 1.2°C above pre-industrial levels as of 2023.",
        "Renewable energy now accounts for over 30% of global electricity generation.",
        "Carbon capture technology costs have dropped 45% over the past decade.",
        "Coastal cities face a projected 0.5m sea-level rise risk by 2100 under moderate emission scenarios.",
        "Reforestation initiatives have offset roughly 2 gigatons of CO2 annually since 2015."
    ],
    "remote work": [
        "58% of the global workforce now works remotely at least one day per week.",
        "Companies report a 22% increase in productivity metrics among fully remote teams.",
        "Commercial office vacancy rates rose to 19% in major US cities post-2020.",
        "Remote work has been linked to a 12% reduction in reported commuting-related stress.",
        "Hybrid models are now the dominant policy choice for 65% of Fortune 500 companies."
    ],
    "cryptocurrency": [
        "Bitcoin's market capitalization has fluctuated between $400B and $1.3T over the past three years.",
        "Over 420 million people worldwide are estimated to own some form of cryptocurrency.",
        "Regulatory frameworks like the EU's MiCA are reshaping global crypto compliance standards.",
        "Energy consumption for Bitcoin mining is comparable to that of mid-sized countries.",
        "Stablecoins now represent roughly 7% of total crypto market value, aiding transactional use."
    ],
    "space exploration": [
        "Private companies now account for over 70% of global orbital launches.",
        "NASA's Artemis program aims to return humans to the Moon by the late 2020s.",
        "Satellite constellations like Starlink have grown to over 5,000 active units.",
        "Mars sample-return missions are projected to deliver Martian soil to Earth by 2033.",
        "Space tourism flights have carried over 600 paying passengers since 2021."
    ],
    "mental health": [
        "Global anxiety and depression rates rose by 25% during the pandemic period.",
        "Teletherapy adoption increased fivefold between 2019 and 2023.",
        "Workplace mental health programs report a 4:1 return on investment in productivity.",
        "Youth mental health concerns have prompted new screen-time guidelines in 12 countries.",
        "AI-assisted mental health chatbots now handle an estimated 40 million conversations monthly."
    ],
    "electric vehicles": [
        "Global EV sales surpassed 14 million units in 2023, a 35% year-over-year increase.",
        "Battery costs have fallen approximately 80% over the last decade.",
        "Charging infrastructure has expanded to over 2.7 million public stations worldwide.",
        "EVs now represent roughly 18% of new car sales in major markets like China and Norway.",
        "Battery recycling rates remain low, at under 5% globally, raising sustainability concerns."
    ],
    "blockchain": [
        "Enterprise blockchain adoption has grown across supply chain, finance, and healthcare sectors.",
        "Ethereum's transition to proof-of-stake cut its energy consumption by over 99%.",
        "Smart contract platforms now process upwards of $50B in decentralized finance value.",
        "Government pilot programs in over 30 countries are exploring blockchain-based digital IDs.",
        "Interoperability between blockchain networks remains a key unsolved technical challenge."
    ],
    "gene editing": [
        "CRISPR-based therapies have received regulatory approval for sickle cell disease treatment.",
        "Gene editing costs have dropped significantly, enabling broader academic and clinical research.",
        "Ethical guidelines around germline editing remain inconsistent across different countries.",
        "Agricultural gene editing has produced drought-resistant crop varieties in over 15 nations.",
        "Clinical trials for gene-edited cancer immunotherapies have shown a 50% remission rate in early studies."
    ],
    "quantum computing": [
        "Quantum processors have surpassed 1,000 qubits in experimental research systems.",
        "Quantum computing could potentially break widely used RSA encryption within a decade.",
        "Major cloud providers now offer quantum-computing-as-a-service to enterprise clients.",
        "Error correction remains the primary bottleneck preventing practical quantum advantage.",
        "Investment in quantum startups exceeded $2.5B globally in the most recent fiscal year."
    ],
}

MOCK_GENERIC_FACTS = [
    "Industry analysts note rapid structural shifts driven by emerging technology.",
    "Adoption rates vary significantly across regions due to regulatory and economic factors.",
    "Long-term forecasts remain uncertain, with experts citing both opportunities and risks.",
    "Investment in this domain has grown steadily over the past five years.",
    "Public perception remains mixed, balancing optimism with concerns over disruption."
]

def call_llm(system_prompt, user_prompt, mock_response_fn, *mock_args):
    if MOCK_MODE:
        return mock_response_fn(*mock_args)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return mock_response_fn(*mock_args)
    try:
        import anthropic
    except ImportError:
        return mock_response_fn(*mock_args)
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=MODEL_NAME,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text_parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
            return "\n".join(text_parts).strip()
        except Exception as e:
            last_error = e
            time.sleep(1)
    return mock_response_fn(*mock_args)

def safe_json_parse(raw_text, fallback_wrapper_key=None, expected_count=None):
    text = raw_text.strip()
    text = re.sub(r"^```(json)?", "", text.strip(), flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text.strip()).strip()
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"(\[.*\]|\{.*\})", text, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                parsed = None
        else:
            parsed = None
    if parsed is None:
        lines = [l.strip("-* ").strip() for l in text.split("\n") if l.strip()]
        if not lines:
            lines = [text]
        parsed = lines if fallback_wrapper_key is None else {fallback_wrapper_key: lines}
    if isinstance(parsed, list) and expected_count:
        if len(parsed) < expected_count:
            parsed += ["(no additional detail provided)"] * (expected_count - len(parsed))
        elif len(parsed) > expected_count:
            parsed = parsed[:expected_count]
    return parsed

def researcher_agent(query):
    system_prompt = """You are a meticulous research analyst. Your sole job is to surface exactly 5 precise, factual, and relevant data points for the user's query. Respond ONLY with a JSON array of exactly 5 strings."""
    user_prompt = f"Research query: '{query}'\nReturn exactly 5 facts as a JSON array of strings."
    def mock_researcher(q):
        q_lower = q.lower()
        for topic_key, facts in MOCK_RESEARCH_DB.items():
            if topic_key in q_lower:
                return json.dumps(facts)
        return json.dumps(MOCK_GENERIC_FACTS)
    raw_output = call_llm(system_prompt, user_prompt, mock_researcher, query)
    facts = safe_json_parse(raw_output, expected_count=5)
    if isinstance(facts, dict):
        facts = list(facts.values())[0] if facts else MOCK_GENERIC_FACTS
    if not isinstance(facts, list):
        facts = [str(facts)]
    return facts[:5]

def writer_agent(query, facts, critique=None, previous_draft=None):
    system_prompt = """You are a professional technical writer. You write clear, well-structured reports in exactly three paragraphs: 1) Introduction, 2) Body, 3) Conclusion. Your tone is objective and precise."""
    if critique:
        user_prompt = f"Original query: '{query}'\nPrevious draft:\n{previous_draft}\n\nSenior editor feedback to address:\n{json.dumps(critique, indent=2)}\n\nFacts available:\n{json.dumps(facts, indent=2)}\n\nRevise the draft into an improved 3-paragraph report addressing all feedback."
    else:
        user_prompt = f"Query: '{query}'\nFacts:\n{json.dumps(facts, indent=2)}\n\nWrite a 3-paragraph report (Intro, Body, Conclusion) based on these facts."
    def mock_writer(q, fct, crit, prev_draft):
        if not crit:
            intro = f"In recent years, the topic of '{q}' has become a focal point of public and policy discourse, driven by rapid technological and economic shifts. Understanding the underlying dynamics requires examining the latest available evidence."
            body = "Several key data points illustrate the current landscape: " + " ".join(fct) + " Together, these findings highlight both the scale and complexity of the issue at hand."
            conclusion = f"Looking ahead, '{q}' will likely continue to evolve as stakeholders adapt to new realities. Continued monitoring, balanced policy responses, and investment in adaptive strategies will be essential to navigate the path forward."
            return f"{intro}\n\n{body}\n\n{conclusion}"
        intro = f"The implications of '{q}' remain a critical area of analysis, and recent evidence offers a more nuanced picture once examined closely. This revised report refines the earlier analysis by directly addressing key editorial concerns."
        body = "Incorporating editorial feedback, the report now more explicitly ties each claim to supporting evidence: " + " ".join(fct) + " Additionally, counterpoints and regional variation are acknowledged to avoid overgeneralization, and transitions between ideas have been tightened for clarity."
        conclusion = f"In summary, while uncertainty remains around the long-term trajectory of '{q}', the strengthened evidence base presented here supports cautious, well-informed expectations. Stakeholders are encouraged to revisit these findings as new data emerges."
        return f"{intro}\n\n{body}\n\n{conclusion}"
    draft = call_llm(system_prompt, user_prompt, mock_writer, query, facts, critique, previous_draft)
    return draft.strip()

def critic_agent(query, draft):
    system_prompt = """You are a strict senior editor. Review drafts critically but constructively. Respond ONLY with a JSON array of exactly 3 specific, actionable criticisms."""
    user_prompt = f"Query: '{query}'\nDraft to review:\n{draft}\n\nProvide exactly 3 specific, constructive criticisms as a JSON array of strings."
    def mock_critic(q, d):
        return json.dumps([
            "The introduction is somewhat generic; it should explicitly state why this topic matters to the reader right now.",
            "Several facts are listed in sequence without enough analytical synthesis -- explain HOW the facts relate.",
            "The conclusion makes a forward-looking claim without acknowledging any counterargument or uncertainty."
        ])
    raw_output = call_llm(system_prompt, user_prompt, mock_critic, query, draft)
    criticisms = safe_json_parse(raw_output, expected_count=3)
    if isinstance(criticisms, dict):
        criticisms = list(criticisms.values())[0] if criticisms else []
    if not isinstance(criticisms, list):
        criticisms = [str(criticisms)]
    return criticisms[:3]

def summariser_agent(final_draft):
    system_prompt = """You are an executive briefing officer. Condense long reports into crisp, ~50 word executive summaries."""
    user_prompt = f"Final report:\n{final_draft}\n\nProduce a concise executive summary of approximately 50 words."
    def mock_summariser(draft):
        return "This report finds that emerging technological and economic forces are reshaping the landscape in measurable, data-backed ways. While uncertainty persists around long-term outcomes, the evidence supports cautious optimism paired with proactive adaptation, monitoring, and policy responsiveness."
    summary = call_llm(system_prompt, user_prompt, mock_summariser, final_draft)
    return summary.strip()

def orchestrate(query):
    facts = researcher_agent(query)
    draft = writer_agent(query, facts)
    for iteration in range(1, 3):
        critique = critic_agent(query, draft)
        draft = writer_agent(query, facts, critique=critique, previous_draft=draft)
    summary = summariser_agent(draft)
    return {
        "query": query,
        "facts": facts,
        "final_draft": draft,
        "executive_summary": summary,
    }

# ==================== WEB ROUTES ====================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Multi-Agent Research System</title>
    <style>
        body { background: #0a0a0f; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; padding: 40px; }
        .container { max-width: 900px; margin: 0 auto; }
        h1 { color: #00d4ff; font-size: 2.5rem; border-bottom: 2px solid #00d4ff33; padding-bottom: 10px; }
        textarea { width: 100%; padding: 15px; background: #1a1a2e; color: #fff; border: 1px solid #333; border-radius: 8px; font-size: 16px; }
        button { background: #00d4ff; color: #0a0a0f; padding: 12px 30px; border: none; border-radius: 8px; font-weight: bold; font-size: 18px; cursor: pointer; }
        button:hover { background: #00b8d4; }
        .card { background: #12121f; border: 1px solid #2a2a40; border-radius: 12px; padding: 20px; margin: 20px 0; }
        .card h3 { color: #00d4ff; margin-top: 0; border-bottom: 1px solid #2a2a40; padding-bottom: 10px; }
        .badge { background: #00d4ff22; padding: 4px 12px; border-radius: 20px; font-size: 12px; color: #00d4ff; }
        .loading { display: none; text-align: center; padding: 40px; color: #888; }
        .spinner { border: 4px solid #1a1a2e; border-top: 4px solid #00d4ff; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .result { display: none; }
        .fact { background: #1a1a2e; padding: 8px 12px; margin: 5px 0; border-radius: 4px; border-left: 3px solid #00d4ff; }
        .critique { background: #2a1a1a; padding: 8px 12px; margin: 5px 0; border-radius: 4px; border-left: 3px solid #ff6b6b; }
        .summary { font-size: 1.1rem; background: #0a2a1a; padding: 15px; border-radius: 8px; border-left: 4px solid #4ecdc4; }
    </style>
</head>
<body>
<div class="container">
    <h1>🧠 Multi-Agent Research System</h1>
    <p>Enter a topic to see the <span class="badge">Researcher</span> <span class="badge">Writer</span> <span class="badge">Critic</span> pipeline in action.</p>
    
    <div style="display:flex; gap:10px; align-items:center; margin:20px 0;">
        <textarea id="queryInput" rows="2" placeholder="e.g. The future of electric vehicles" style="flex:1;">The long-term effects of artificial intelligence on the global job market</textarea>
        <button onclick="generate()" style="height:60px;">🚀 Generate</button>
    </div>
    
    <div id="loading" class="loading">
        <div class="spinner"></div>
        <p>Agents are analyzing...</p>
    </div>
    
    <div id="results" class="result">
        <div id="factsCard" class="card"><h3>🔍 Researcher Facts</h3><div id="factsList"></div></div>
        <div id="draft1Card" class="card"><h3>✍️ Writer Draft 1</h3><div id="draft1Text" style="white-space:pre-wrap;"></div></div>
        <div id="critiqueCard" class="card"><h3>🔴 Critic Feedback</h3><div id="critiqueList"></div></div>
        <div id="finalCard" class="card"><h3>📝 Final Report</h3><div id="finalText" style="white-space:pre-wrap;"></div></div>
        <div id="summaryCard" class="card"><h3>📊 Executive Summary</h3><div id="summaryText" class="summary"></div></div>
    </div>
</div>
<script>
function generate() {
    const query = document.getElementById('queryInput').value.trim();
    if (!query) return;
    
    document.getElementById('loading').style.display = 'block';
    document.getElementById('results').style.display = 'none';
    
    fetch('/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query })
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('results').style.display = 'block';
        
        // Facts
        let factsHtml = '';
        data.facts.forEach(f => factsHtml += `<div class="fact">📌 ${f}</div>`);
        document.getElementById('factsList').innerHTML = factsHtml;
        
        // Critiques
        let critHtml = '';
        if (data.critiques) {
            data.critiques.forEach(c => critHtml += `<div class="critique">⚠️ ${c}</div>`);
        }
        document.getElementById('critiqueList').innerHTML = critHtml;
        
        document.getElementById('draft1Text').textContent = data.draft1 || 'N/A';
        document.getElementById('finalText').textContent = data.final_draft || 'N/A';
        document.getElementById('summaryText').textContent = data.summary || 'N/A';
    })
    .catch(err => {
        document.getElementById('loading').style.display = 'none';
        alert('Error: ' + err);
    });
}
// Auto-run on load
window.onload = function() { generate(); };
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    query = data.get('query', '')
    if not query:
        return jsonify({"error": "No query provided"}), 400
    
    # Run the pipeline
    facts = researcher_agent(query)
    draft1 = writer_agent(query, facts)
    critiques = []
    draft = draft1
    for _ in range(2):
        critique = critic_agent(query, draft)
        critiques = critique  # keep last round
        draft = writer_agent(query, facts, critique=critique, previous_draft=draft)
    summary = summariser_agent(draft)
    
    return jsonify({
        "facts": facts,
        "draft1": draft1,
        "critiques": critiques,
        "final_draft": draft,
        "summary": summary
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)