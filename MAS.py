#!/usr/bin/env python3
"""
Research & Report Generator
============================
A multi-agent pipeline: Researcher -> Writer -> Critic -> Writer (revision) -> Summariser.

MOCK_MODE = True  -> runs 100% offline with hardcoded mock data, no API key needed.
MOCK_MODE = False -> attempts to call the Anthropic Claude API, falling back to mock
                     data automatically if the API key is missing or any call fails.

Only standard library modules are used (json, os, time, random, re).
The `anthropic` package is imported lazily inside a try/except so the script
never hard-crashes if it isn't installed.
"""

import json
import os
import time
import random
import re

# ----------------------------------------------------------------------------
# GLOBAL CONFIG
# ----------------------------------------------------------------------------
MOCK_MODE = True          # <--- Flip to False to attempt real Claude API calls
MODEL_NAME = "claude-sonnet-4-6"
MAX_RETRIES = 2           # max retry attempts for live API calls


# ----------------------------------------------------------------------------
# MOCK DATABASE (used by the Researcher agent when offline)
# ----------------------------------------------------------------------------
# Each topic maps to exactly 5 "facts" that the Researcher will hand off
# to the Writer agent. Keys are lowercase keywords we match against the query.
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

# Generic fallback facts used if no topic keyword matches the query.
MOCK_GENERIC_FACTS = [
    "Industry analysts note rapid structural shifts driven by emerging technology.",
    "Adoption rates vary significantly across regions due to regulatory and economic factors.",
    "Long-term forecasts remain uncertain, with experts citing both opportunities and risks.",
    "Investment in this domain has grown steadily over the past five years.",
    "Public perception remains mixed, balancing optimism with concerns over disruption."
]


# ----------------------------------------------------------------------------
# CORE LLM CALL WRAPPER
# ----------------------------------------------------------------------------
def call_llm(system_prompt, user_prompt, mock_response_fn, *mock_args):
    """
    Unified entry point for every agent's "thinking" step.

    Parameters
    ----------
    system_prompt : str
        The role-playing system prompt for this agent (only used in live mode).
    user_prompt : str
        The task-specific prompt content (only used in live mode).
    mock_response_fn : callable
        A function that generates the mock/offline response for this agent.
    mock_args : tuple
        Arguments forwarded to mock_response_fn so each agent can produce
        context-appropriate mock output (e.g. the query, prior agent's output).

    Returns
    -------
    str : raw text response from either the mock generator or the live API.

    Behavior
    --------
    - If MOCK_MODE is True -> immediately return mock data (no network calls at all).
    - If MOCK_MODE is False -> check for an API key; if missing, fall back to mock.
    - If a key exists, attempt up to MAX_RETRIES live calls to the Anthropic API.
      Any failure (import error, network error, malformed response) gracefully
      falls back to the mock generator so the pipeline NEVER hard-crashes.
    """
    # ---- Path 1: Explicit mock mode, skip all network logic entirely ----
    if MOCK_MODE:
        return mock_response_fn(*mock_args)

    # ---- Path 2: Live mode requested, but verify prerequisites first ----
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[call_llm] No ANTHROPIC_API_KEY found in environment -> falling back to mock data.")
        return mock_response_fn(*mock_args)

    try:
        import anthropic  # lazy import; only required for live mode
    except ImportError:
        print("[call_llm] 'anthropic' package not installed -> falling back to mock data.")
        return mock_response_fn(*mock_args)

    # ---- Path 3: Attempt the real API call with retry logic ----
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
            # Concatenate all text blocks in the response.
            text_parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
            return "\n".join(text_parts).strip()
        except Exception as e:
            last_error = e
            print(f"[call_llm] API call attempt {attempt} failed: {e}")
            time.sleep(1)  # brief backoff before retrying

    # ---- All live attempts exhausted -> fall back to mock as a safety net ----
    print(f"[call_llm] All {MAX_RETRIES} attempts failed ({last_error}). Falling back to mock data.")
    return mock_response_fn(*mock_args)


# ----------------------------------------------------------------------------
# JSON SAFETY NET
# ----------------------------------------------------------------------------
def safe_json_parse(raw_text, fallback_wrapper_key=None, expected_count=None):
    """
    Attempts to parse raw_text as JSON. If parsing fails (e.g. the LLM wrapped
    the JSON in prose or markdown fences), this function tries to recover by:
      1. Stripping markdown code fences.
      2. Extracting the first [...] or {...} block via regex.
      3. As an absolute last resort, wrapping the raw text itself into a list
         (or dict, depending on fallback_wrapper_key) so the pipeline can
         keep moving instead of crashing.

    Parameters
    ----------
    raw_text : str
        The text returned by call_llm (mock or live).
    fallback_wrapper_key : str or None
        If parsing totally fails and we need a dict shape, use this key.
    expected_count : int or None
        If parsing succeeds but the list is the wrong length, pad/truncate.

    Returns
    -------
    list or dict : the parsed (or recovered) JSON structure.
    """
    text = raw_text.strip()

    # Strip common markdown code fences like ```json ... ```
    text = re.sub(r"^```(json)?", "", text.strip(), flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text.strip()).strip()

    # Attempt direct parse first.
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Try to extract the first bracketed JSON-looking substring.
        match = re.search(r"(\[.*\]|\{.*\})", text, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                parsed = None
        else:
            parsed = None

    # Absolute fallback: wrap raw text into the expected structure manually.
    if parsed is None:
        # Split into lines / sentences as a crude best-effort recovery.
        lines = [l.strip("-* ").strip() for l in text.split("\n") if l.strip()]
        if not lines:
            lines = [text]
        parsed = lines if fallback_wrapper_key is None else {fallback_wrapper_key: lines}

    # Normalize list length if an expected_count was specified.
    if isinstance(parsed, list) and expected_count:
        if len(parsed) < expected_count:
            parsed += ["(no additional detail provided)"] * (expected_count - len(parsed))
        elif len(parsed) > expected_count:
            parsed = parsed[:expected_count]

    return parsed


# ----------------------------------------------------------------------------
# AGENT 1: RESEARCHER
# ----------------------------------------------------------------------------
def researcher_agent(query):
    """
    The Researcher agent. Role: a meticulous analyst who digs up exactly
    5 relevant, concrete facts related to the user's query.

    State handoff: takes the raw user query (str), returns a list[str] of
    facts. This list becomes part of the Writer agent's input state.
    """
    system_prompt = """You are a meticulous research analyst.
Your sole job is to surface exactly 5 precise, factual, and relevant data points
for the user's query. You are rigorous, you avoid speculation, and you cite
concrete figures or trends wherever possible. Respond ONLY with a JSON array
of exactly 5 strings, each a single self-contained fact. No commentary."""

    user_prompt = f"Research query: '{query}'\nReturn exactly 5 facts as a JSON array of strings."

    def mock_researcher(q):
        # Match the query against our mock topic database (case-insensitive keyword match).
        q_lower = q.lower()
        for topic_key, facts in MOCK_RESEARCH_DB.items():
            if topic_key in q_lower:
                return json.dumps(facts)
        # No topic matched -> fall back to generic facts so the pipeline still works.
        return json.dumps(MOCK_GENERIC_FACTS)

    raw_output = call_llm(system_prompt, user_prompt, mock_researcher, query)
    facts = safe_json_parse(raw_output, expected_count=5)

    # Ensure we always hand off a clean list[str] downstream, regardless of
    # how messy the raw LLM/mock output was.
    if isinstance(facts, dict):
        facts = list(facts.values())[0] if facts else MOCK_GENERIC_FACTS
    if not isinstance(facts, list):
        facts = [str(facts)]

    return facts[:5]  # enforce exactly 5


# ----------------------------------------------------------------------------
# AGENT 2: WRITER
# ----------------------------------------------------------------------------
def writer_agent(query, facts, critique=None, previous_draft=None):
    """
    The Writer agent. Role: a professional technical writer who drafts a
    structured 3-paragraph report (Intro, Body, Conclusion).

    State handoff:
      - On first call: takes query + facts (from Researcher) -> returns draft v1 (str).
      - On revision call: ALSO receives critique (list[str], from Critic) and
        the previous_draft (str) so it can produce an improved draft v2.
    """
    system_prompt = """You are a professional technical writer.
You write clear, well-structured reports in exactly three paragraphs:
1) Introduction - framing the topic and its significance.
2) Body - synthesizing the supplied facts into a coherent narrative.
3) Conclusion - forward-looking takeaway.
Your tone is objective, precise, and accessible to a general audience."""

    if critique:
        user_prompt = (
            f"Original query: '{query}'\n"
            f"Previous draft:\n{previous_draft}\n\n"
            f"Senior editor feedback to address:\n{json.dumps(critique, indent=2)}\n\n"
            f"Facts available:\n{json.dumps(facts, indent=2)}\n\n"
            "Revise the draft into an improved 3-paragraph report addressing all feedback."
        )
    else:
        user_prompt = (
            f"Query: '{query}'\n"
            f"Facts:\n{json.dumps(facts, indent=2)}\n\n"
            "Write a 3-paragraph report (Intro, Body, Conclusion) based on these facts."
        )

    def mock_writer(q, fct, crit, prev_draft):
        # --- Mock draft v1 (no critique yet) ---
        if not crit:
            intro = (
                f"In recent years, the topic of '{q}' has become a focal point of public and "
                f"policy discourse, driven by rapid technological and economic shifts. Understanding "
                f"the underlying dynamics requires examining the latest available evidence."
            )
            body = (
                "Several key data points illustrate the current landscape: " +
                " ".join(fct) +
                " Together, these findings highlight both the scale and complexity of the issue at hand."
            )
            conclusion = (
                f"Looking ahead, '{q}' will likely continue to evolve as stakeholders adapt to new "
                "realities. Continued monitoring, balanced policy responses, and investment in adaptive "
                "strategies will be essential to navigate the path forward."
            )
            return f"{intro}\n\n{body}\n\n{conclusion}"

        # --- Mock revision (incorporating critique) ---
        intro = (
            f"The implications of '{q}' remain a critical area of analysis, and recent evidence "
            "offers a more nuanced picture once examined closely. This revised report refines the "
            "earlier analysis by directly addressing key editorial concerns, including added specificity "
            "and stronger evidentiary grounding."
        )
        body = (
            "Incorporating editorial feedback, the report now more explicitly ties each claim to "
            "supporting evidence: " + " ".join(fct) +
            " Additionally, counterpoints and regional variation are acknowledged to avoid overgeneralization, "
            "and transitions between ideas have been tightened for clarity."
        )
        conclusion = (
            f"In summary, while uncertainty remains around the long-term trajectory of '{q}', "
            "the strengthened evidence base presented here supports cautious, well-informed "
            "expectations. Stakeholders are encouraged to revisit these findings as new data emerges."
        )
        return f"{intro}\n\n{body}\n\n{conclusion}"

    draft = call_llm(system_prompt, user_prompt, mock_writer, query, facts, critique, previous_draft)
    return draft.strip()


# ----------------------------------------------------------------------------
# AGENT 3: CRITIC
# ----------------------------------------------------------------------------
def critic_agent(query, draft):
    """
    The Critic agent. Role: a strict senior editor who reviews the Writer's
    draft and returns exactly 3 specific, constructive criticisms.

    State handoff: takes the query + draft (str) -> returns list[str] of
    3 criticisms. This becomes input to the Writer's revision call.
    """
    system_prompt = """You are a strict senior editor with decades of publishing experience.
You review drafts critically but constructively, looking for vague claims, missing nuance,
structural weaknesses, or unsupported assertions. Respond ONLY with a JSON array of exactly
3 specific, actionable criticisms. No praise, no preamble - just the 3 critique points."""

    user_prompt = (
        f"Query: '{query}'\n"
        f"Draft to review:\n{draft}\n\n"
        "Provide exactly 3 specific, constructive criticisms as a JSON array of strings."
    )

    def mock_critic(q, d):
        # Hardcoded but draft-aware-sounding critiques to simulate a real editorial pass.
        return json.dumps([
            "The introduction is somewhat generic; it should explicitly state why this topic matters "
            "to the reader right now, rather than relying on broad framing language.",
            "Several facts are listed in sequence without enough analytical synthesis -- the body "
            "paragraph should explain HOW the facts relate to one another, not just enumerate them.",
            "The conclusion makes a forward-looking claim without acknowledging any counterargument "
            "or uncertainty, which weakens its credibility; add a note of nuance or caveat."
        ])

    raw_output = call_llm(system_prompt, user_prompt, mock_critic, query, draft)
    criticisms = safe_json_parse(raw_output, expected_count=3)

    if isinstance(criticisms, dict):
        criticisms = list(criticisms.values())[0] if criticisms else []
    if not isinstance(criticisms, list):
        criticisms = [str(criticisms)]

    return criticisms[:3]  # enforce exactly 3


# ----------------------------------------------------------------------------
# AGENT 4: SUMMARISER
# ----------------------------------------------------------------------------
def summariser_agent(final_draft):
    """
    The Summariser agent. Role: an executive briefing officer who condenses
    the final revised draft into a tight ~50-word executive summary.

    State handoff: takes the final draft (str) -> returns a short summary (str).
    This is the terminal node of the pipeline.
    """
    system_prompt = """You are an executive briefing officer. You condense long reports into
crisp, high-signal executive summaries for time-constrained decision-makers. Your summaries
are approximately 50 words, no fluff, no bullet points -- just dense, clear prose capturing
the single most important takeaway and its implication."""

    user_prompt = (
        f"Final report:\n{final_draft}\n\n"
        "Produce a concise executive summary of approximately 50 words."
    )

    def mock_summariser(draft):
        return (
            "This report finds that emerging technological and economic forces are reshaping "
            "the landscape in measurable, data-backed ways. While uncertainty persists around "
            "long-term outcomes, the evidence supports cautious optimism paired with proactive "
            "adaptation, monitoring, and policy responsiveness from stakeholders across affected sectors."
        )

    summary = call_llm(system_prompt, user_prompt, mock_summariser, final_draft)
    return summary.strip()


# ----------------------------------------------------------------------------
# ORCHESTRATOR
# ----------------------------------------------------------------------------
def orchestrate(query):
    """
    Main pipeline coordinator. Manages state handoff between agents:

        Researcher -> Writer (draft 1) -> Critic (feedback 1) -> Writer (revision 1)
                    -> Critic (feedback 2) -> Writer (revision 2) -> Summariser

    The Writer-Critic loop runs exactly TWICE to demonstrate iterative
    improvement, as required. Each stage's output is printed under a clear
    visual header so the full chain-of-thought is observable.
    """

    def header(title):
        print("\n" + "=" * 60)
        print(f"===== {title} =====")
        print("=" * 60)

    header(f"ORCHESTRATOR START | Query: '{query}'")
    print(f"(MOCK_MODE = {MOCK_MODE})")

    # ---- STAGE 1: Researcher ----
    # State: query (str) -> facts (list[str])
    header("RESEARCHER OUTPUT")
    facts = researcher_agent(query)
    for i, fact in enumerate(facts, 1):
        print(f"  {i}. {fact}")

    # ---- STAGE 2: Writer (initial draft) ----
    # State: query + facts -> draft (str)
    header("WRITER DRAFT 1")
    draft = writer_agent(query, facts)
    print(draft)

    # ---- ITERATIVE WRITER-CRITIC LOOP (runs exactly twice) ----
    # Each iteration: Critic reviews current draft -> Writer revises using
    # that feedback. The 'draft' variable is reassigned each loop so state
    # flows forward cleanly into the next iteration.
    for iteration in range(1, 3):  # iteration = 1, 2  (exactly twice)
        header(f"CRITIC FEEDBACK (Round {iteration})")
        critique = critic_agent(query, draft)
        for i, point in enumerate(critique, 1):
            print(f"  {i}. {point}")

        header(f"WRITER REVISION (Round {iteration})")
        draft = writer_agent(query, facts, critique=critique, previous_draft=draft)
        print(draft)

    # ---- STAGE 5: Summariser ----
    # State: final revised draft (str) -> executive summary (str)
    header("FINAL SUMMARY")
    summary = summariser_agent(draft)
    print(summary)

    header("ORCHESTRATOR COMPLETE")

    # Return the full state trail in case a caller wants programmatic access.
    return {
        "query": query,
        "facts": facts,
        "final_draft": draft,
        "executive_summary": summary,
    }


# ----------------------------------------------------------------------------
# ENTRY POINT
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    demo_query = "The long-term effects of artificial intelligence on the global job market"
    result_state = orchestrate(demo_query)

    # Optional: dump the final state object as JSON for inspection/debugging.
    print("\n\n[Full pipeline state object available as JSON below]")
    print(json.dumps(result_state, indent=2))
