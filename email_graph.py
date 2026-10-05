import os
from typing import Annotated, Literal

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from tools import send_email

load_dotenv()


class EmailState(BaseModel):
    question: str = ""
    reason: str = ""
    recipient_name: str = ""
    recipient_email: str = ""
    subject: str = ""
    body: str = ""
    feedback: str = ""
    feedback_count: int = 0
    response: str = ""


class UserDetails(BaseModel):
    mail_reason: str = Field(description="Reason of the mail.")
    recipient_name: str = Field(description="Receiver / Recipient's Name.")
    recipient_email: str = Field(description="Receiver / Recipient's email address.")


class DraftMail(BaseModel):
    subject: str = Field(description="Email subject within 40 words.")
    body: str = Field(description="Body of the email including all nesscary details based on the reasons. ")
    recipient_email: str = Field(description="Receiver / Recipient's email address.")


def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=os.environ.get("OPENAI_MODEL", "gpt-5.6-luna"))


def retriever_node(state: EmailState) -> EmailState:
    user_details: UserDetails = _llm().with_structured_output(UserDetails).invoke(
        "Extract the following from the user query: mail_reason (why they want to send the email), "
        "recipient_name, and recipient_email. All three fields are required.\n"
        f"User query: {state.question}"
    )
    if not user_details.mail_reason or not user_details.recipient_email:
        raise ValueError(
            "Could not extract recipient email or reason from your request. "
            "Please include both, e.g. 'Email Alice at alice@example.com about X'."
        )
    state.recipient_name = user_details.recipient_name
    state.recipient_email = user_details.recipient_email
    state.reason = user_details.mail_reason
    return state


def draft_node(state: EmailState) -> EmailState:
    llm_obj = _llm().with_structured_output(DraftMail)
    prompt = (
        "Write an email with these details:\n"
        f"Recipient name: {state.recipient_name}\n"
        f"Recipient email: {state.recipient_email}\n"
        f"Request: {state.reason}\n"
        "Return JSON with exactly these keys: subject, body, recipient_email. "
        "Mail body max size is 200 words, no extra text outside the JSON."
    )
    if state.feedback:
        prompt = f"""Revise this email based on the feedback below.
                    Current Email:
                    Subject: {state.subject}
                    Body: {state.body}
                    Feedback: {state.feedback}
                    Please write a proper mail body and subject. Without extra text
                    Mail body max size will be 200 Words."""
    draftmail: DraftMail = llm_obj.invoke(prompt)
    state.body = draftmail.body
    if draftmail.recipient_email and not state.recipient_email:
        state.recipient_email = draftmail.recipient_email
    state.subject = draftmail.subject
    return state


def review_node(state: EmailState) -> EmailState:
    response = interrupt({"message": "Approve this email, or provide feedback to rewrite it"})
    if response == "yes":
        state.feedback = ""
    else:
        state.feedback = response
        state.feedback_count = state.feedback_count + 1
    return state


def router_node(state: EmailState) -> Literal["send", "draft", "cancel"]:
    if not state.feedback or state.feedback.strip() == "":
        return "send"
    if state.feedback_count > 2:
        return "cancel"
    return "draft"


def cancel_node(state: EmailState) -> EmailState:
    state.response = "Email not Sent, Ratelimt exceeded for feedback"
    return state


def send_node(state: EmailState) -> EmailState:
    send_email(recipient=state.recipient_email, subject=state.subject, body=state.body)
    state.response = "Email sent Successfully"
    return state


def build_graph():
    builder = StateGraph(EmailState)
    builder.add_node("retriever", retriever_node)
    builder.add_node("draft", draft_node)
    builder.add_node("send", send_node)
    builder.add_node("review", review_node)
    builder.add_node("cancel", cancel_node)
    builder.add_edge(START, "retriever")
    builder.add_edge("retriever", "draft")
    builder.add_edge("draft", "review")
    builder.add_conditional_edges("review", router_node)
    builder.add_edge("send", END)
    builder.add_edge("cancel", END)
    return builder.compile(checkpointer=InMemorySaver())
