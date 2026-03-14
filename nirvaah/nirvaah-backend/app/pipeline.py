"""
app/pipeline.py — LangGraph multi-agent pipeline for Nirvaah AI.

Imports all node functions, connects them as a directed graph,
compiles the graph, and exposes run_pipeline() to webhook.py.
"""

from dotenv import load_dotenv
load_dotenv()

import asyncio
from langgraph.graph import StateGraph, END
from app.state import PipelineState, get_initial_state
from app.agents.extraction import extraction_node
from app.agents.validation import validation_node
from app.agents.form_agent import form_agent_node
from app.agents.sync_agent import sync_node

# ----------------------------------------------------------------
# STUB NODES for Agents 5-6
# These are temporary pass-through functions. Each one will be
# replaced with the real agent as we build them one by one.
# They are stubs — they do nothing except pass state through and
# print a message so you can see the graph is running.
# ----------------------------------------------------------------


def clarification_node(state: PipelineState) -> dict:
    print("[STUB] clarification_node — would send WhatsApp message here")
    print(f"  Question: {state.get('clarification_question', '')}")
    return {"pipeline_complete": False}


def anomaly_node(state: PipelineState) -> dict:
    print("[STUB] anomaly_node running — replace with Agent 5")
    return {"anomaly_score": 0.0, "anomaly_flags": []}


def insights_node(state: PipelineState) -> dict:
    print("[STUB] insights_node running — replace with Agent 6")
    return {
        "dropout_risk": 0.0,
        "eligible_schemes": [],
        "risk_summary": "",
        "pipeline_complete": True
    }


# ----------------------------------------------------------------
# CONDITIONAL ROUTING FUNCTION
# This function is called by LangGraph after validation_node runs.
# It reads the state and returns the NAME of the next node to go to.
# This is the "fork" in the pipeline after validation.
# ----------------------------------------------------------------

def route_after_validation(state: PipelineState) -> str:
    """
    After validation, decide where to go next.
    If clarification is needed, route to clarification_node and stop.
    Otherwise, continue to form_agent_node.
    """
    if state.get("clarification_needed", False):
        return "clarification_node"
    return "form_agent_node"


# ----------------------------------------------------------------
# GRAPH BUILDER
# This is where we wire everything together.
# ----------------------------------------------------------------

def build_pipeline() -> StateGraph:
    """
    Build and compile the LangGraph pipeline.
    Returns a compiled graph ready to run.

    The graph is built once at startup and reused for every incoming
    WhatsApp message — it is stateless (the state is passed in fresh
    each time), so this is safe to do.
    """

    # Create the graph, telling LangGraph our state schema
    graph = StateGraph(PipelineState)

    # Add every node to the graph
    # First argument is the node name (used in edges)
    # Second argument is the function to call
    graph.add_node("extraction_node", extraction_node)
    graph.add_node("validation_node", validation_node)
    graph.add_node("clarification_node", clarification_node)
    graph.add_node("form_agent_node", form_agent_node)
    graph.add_node("sync_node", sync_node)
    graph.add_node("anomaly_node", anomaly_node)
    graph.add_node("insights_node", insights_node)

    # Set the entry point — where the graph starts
    graph.set_entry_point("extraction_node")

    # Add the straight edges (unconditional — always go to the next node)
    graph.add_edge("extraction_node", "validation_node")

    # Add the conditional edge after validation
    # LangGraph calls route_after_validation(state) and uses its return
    # value as the name of the next node to go to
    graph.add_conditional_edges(
        "validation_node",           # from this node
        route_after_validation,      # call this function to decide
        {
            "clarification_node": "clarification_node",  # if returns "clarification_node"
            "form_agent_node": "form_agent_node"          # if returns "form_agent_node"
        }
    )

    # Clarification is a dead end — pipeline stops here if triggered
    graph.add_edge("clarification_node", END)

    # Happy path continues straight through
    graph.add_edge("form_agent_node", "sync_node")
    graph.add_edge("sync_node", "anomaly_node")
    graph.add_edge("anomaly_node", "insights_node")
    graph.add_edge("insights_node", END)

    # Compile the graph — this validates the structure and prepares
    # it for execution
    return graph.compile()


# Build the graph once at module load time
# This compiled graph is reused for every request
pipeline_graph = build_pipeline()


# ----------------------------------------------------------------
# PUBLIC ENTRY POINT
# This is what webhook.py calls for every incoming WhatsApp message.
# ----------------------------------------------------------------

async def run_pipeline(
    sender_phone: str,
    audio_bytes: bytes = None,
    text: str = None,
    image_bytes: bytes = None
) -> dict:
    """
    Main entry point for the Nirvaah AI pipeline.
    Called by webhook.py for every incoming WhatsApp message.

    Handles all three input types (voice, text, image) by routing
    through process_input() first to get a transcript, then running
    the full LangGraph pipeline on that transcript.
    """
    from app.agents.extraction import process_input

    # Step 1: Route through process_input() to get extracted fields
    # and determine input_source. process_input handles voice→STT,
    # text→normalise, image→OCR before calling extract_fields_async.
    initial_extraction = await process_input(
        audio_bytes=audio_bytes,
        text=text,
        image_bytes=image_bytes
    )

    # Get the transcript that was used (for state initialisation)
    # For voice: it was the STT output. For text: the normalised text.
    # For image: the OCR output.
    transcript = text or ""
    input_source = initial_extraction.get("input_source", "unknown")
    ocr_text = initial_extraction.get("ocr_text", "")

    # Step 2: Build the initial state
    state = get_initial_state(
        transcript=transcript,
        sender_phone=sender_phone,
        input_source=input_source,
        ocr_text=ocr_text
    )

    # Pre-populate extracted_fields with what process_input already got
    # so the extraction_node does not run Groq twice
    state["extracted_fields"] = initial_extraction
    state["clarification_needed"] = initial_extraction.get("overall_confidence", 0) < 0.70

    # Step 3: Run the LangGraph pipeline
    # invoke() runs the graph synchronously and returns the final state
    final_state = pipeline_graph.invoke(state)

    # Step 4: Return the final state as a dict for webhook.py to use
    return dict(final_state)
