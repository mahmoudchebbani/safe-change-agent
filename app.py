import asyncio
import uuid

import logfire
import streamlit as st
from dotenv import load_dotenv
from pydantic_ai.messages import FunctionToolCallEvent

load_dotenv()

from safe_change_agent.agent import create_agent  # noqa: E402
from safe_change_agent.config import get_model  # noqa: E402
from safe_change_agent.cost import CostAccumulator  # noqa: E402
from safe_change_agent.monitoring import setup_monitoring  # noqa: E402
from safe_change_agent.tools import create_codebase_tools  # noqa: E402

st.set_page_config(page_title="Safe Change Agent", page_icon="🛠️", layout="wide")


@st.cache_resource(show_spinner=False)
def load_agent():
    setup_monitoring()
    return create_agent(create_codebase_tools(), model=get_model())


def new_session():
    st.session_state.session_id = uuid.uuid4().hex[:12]
    st.session_state.messages = []        # what the UI shows
    st.session_state.agent_messages = []  # PydanticAI message history
    st.session_state.cost = CostAccumulator(model=get_model())
    # one trace per browser session: every question is attached to this span
    with logfire.span("app conversation {conversation_id}", conversation_id=st.session_state.session_id):
        st.session_state.logfire_context = logfire.get_context()


with st.spinner("Loading the codebase index…"):
    agent = load_agent()

if "session_id" not in st.session_state:
    new_session()


def send_feedback(idx: int, score: int):
    msg = st.session_state.messages[idx]
    with logfire.attach_context(st.session_state.logfire_context):
        logfire.info(
            "user_feedback",
            conversation_id=st.session_state.session_id,
            feedback=score,
            question=msg["question"],
        )
    msg["feedback"] = score


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🛠️ Safe Change Agent")
    st.caption("Ask how the insurance claims system works. Answers cite `file:line`.")
    cost = st.session_state.cost
    st.metric("Session cost", f"${cost.total_cost:.4f}")
    st.caption(f"{cost.runs} questions · {cost.input_tokens:,} in / {cost.output_tokens:,} out tokens")
    st.caption(f"Model: `{cost.model}` · session `{st.session_state.session_id}`")
    if st.button("🗑️ New conversation", use_container_width=True):
        new_session()
        st.rerun()
    st.divider()
    st.markdown("**Try:**\n- What consumes the Fraud.Detected event?\n"
                "- Which table stores customer policies?\n"
                "- What runs behind POST /settlement?")


def render_tool_calls(calls: list[str]):
    with st.expander(f"⚙️ {len(calls)} tool calls", expanded=False):
        for c in calls:
            st.code(c, language=None)


# ── Chat history ─────────────────────────────────────────────────────────────
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message("user"):
        st.markdown(msg["question"])
    with st.chat_message("assistant"):
        render_tool_calls(msg["tool_calls"])
        st.markdown(msg["answer"])
        st.caption(f"{msg['input_tokens']:,} in / {msg['output_tokens']:,} out tokens · ${msg['cost']:.4f}")
        if msg.get("feedback") is None:
            c1, c2, _ = st.columns([0.06, 0.06, 0.88])
            c1.button("👍", key=f"up_{idx}", on_click=send_feedback, args=(idx, 1))
            c2.button("👎", key=f"down_{idx}", on_click=send_feedback, args=(idx, -1))
        else:
            st.caption("Thanks for the feedback " + ("👍" if msg["feedback"] > 0 else "👎"))


# ── New question ─────────────────────────────────────────────────────────────
async def run_agent(question: str, status) -> tuple:
    calls = []

    async def on_event(ctx, events):
        async for event in events:
            if isinstance(event, FunctionToolCallEvent):
                line = f"{event.part.tool_name}({event.part.args})"
                calls.append(line)
                status.write(f"`{line[:150]}`")

    result = await agent.run(
        question,
        message_history=st.session_state.agent_messages,
        event_stream_handler=on_event,
    )
    return result, calls


if question := st.chat_input("Ask about the claims processing codebase…"):
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.status("Investigating the codebase…", expanded=True) as status:
            with logfire.attach_context(st.session_state.logfire_context):
                result, calls = asyncio.run(run_agent(question, status))
            status.update(label=f"Done · {len(calls)} tool calls", state="complete", expanded=False)

    usage = result.usage
    before = st.session_state.cost.total_cost
    st.session_state.cost.add(usage)
    run_cost = st.session_state.cost.total_cost - before

    with logfire.attach_context(st.session_state.logfire_context):
        logfire.info(
            "run finished",
            conversation_id=st.session_state.session_id,
            question=question,
            tool_calls=len(calls),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            run_cost_usd=round(run_cost, 6),
            conversation_cost_usd=round(st.session_state.cost.total_cost, 6),
        )

    st.session_state.agent_messages = result.all_messages()
    st.session_state.messages.append({
        "question": question,
        "answer": result.output,
        "tool_calls": calls,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cost": run_cost,
        "feedback": None,
    })
    st.rerun()
