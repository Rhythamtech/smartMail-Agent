from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command , interrupt
from pydantic import BaseModel, Field
from typing import Annotated, Literal

load_dotenv()

llm =  ChatOpenAI( model= "gpt-5.6-luna")

class EmailState(BaseModel):
    question : str = ""
    reason : str = ""
    recipient_name : str = ""
    recipient_email : str = ""
    subject : str = ""
    body : str = ""
    feedback : str = ""
    feedback_count : int = 0
    response : str = ""
    
    
class UserDetails(BaseModel):
    mail_reason : str = Field("", description= "Reason of the mail.")
    recipient_name : str = Field("", description= "Receiver / Recipient's Name.")
    recipient_email : str = Field("", description= "Receiver / Recipient's email address.")
    

class DraftMail(BaseModel):
    subject : str = Field("", description= "Email subject within 40 words.")
    body : str = Field("", description= "Body of the email including all nesscary details based on the reasons. ")
    recipient_email : str = Field("", description= "Receiver / Recipient's email address.")
    
    
    
    
    
def retriever_node(state : EmailState) -> EmailState:
    llm_obj = llm.with_structured_output(UserDetails)
    user_details : UserDetails = llm_obj.invoke(f"Retrive the user details from the user query {state.question}")
    
    if not user_details.mail_reason or not user_details.recipient_email :
        pass
    
    state.recipient_name = user_details.recipient_name
    state.recipient_email =  user_details.recipient_email
    state.reason =  user_details.mail_reason
    
    return state


def draft_node(state : EmailState) -> EmailState:
    llm_obj = llm.with_structured_output(DraftMail)
    
    prompt = ("Write an email with these details:",
            f"To : {state.recipient_name}"
            f"Request : {state.reason}"
            "Please write a proper mail body subject without extra text. Mail body max size is 200 words.")
    
    if state.feedback :
            prompt = f"""Revise this email based on the feedback below.
                        Current Email:
                        Subject: {state.subject}
                        Body: {state. body}
                        Feedback: {state.feedback}
                        Please write a proper mail body and subject. Without extra text
                        Mail body max size will be 200 Words."""
    
    draftmail : DraftMail = llm_obj.invoke(prompt)
    
    state.body = draftmail.body
    state.recipient_email = draftmail.recipient_email
    state.subject = draftmail.subject
    
    return state
    
def review_node(state : EmailState) -> EmailState:
    print("--------")
    print(f"Subject - {state.subject}")
    print(f"Body - {state.body}")
    print("--------")
    
    response =  interrupt( {"message":"You want to approve this or re-write this email"})
    
    if response == "yes":
        state.feedback = ""
        
    else:
        state.feedback = response 
        state.feedback_count = state.feedback_count + 1
        
    return state
        
def router_node(state:EmailState) -> Literal["send","draft","cancel"]:
    
    if not state.feedback or state.feedback.strip() == "":
        return "send"
    
    if state.feedback_count > 2 :
        return "cancel"
    
    return "draft"


def cancel_node(state:EmailState) -> EmailState:
    state.response = "Email not Sent, Ratelimt exceeded for feedback"
    return state

def send_node(state:EmailState) -> EmailState:
    state.response = "Email sent Successfully"
    
    return state



builder = StateGraph(EmailState)

builder.add_node("retriever", retriever_node)
builder.add_node("draft", draft_node)
builder.add_node("send", send_node)
builder.add_node("review",review_node)
builder.add_node("cancel", cancel_node)

builder.add_edge(START, "retriever")
builder.add_edge("retriever","draft")
builder.add_edge("draft","review" )

builder.add_conditional_edges("review", router_node)
builder.add_edge("send",END)
builder.add_edge("cancel", END)


graph =  builder.compile(checkpointer= InMemorySaver())

from uuid import uuid4

thread_id = uuid4()

while True :
    config = {"configurable" : {"thread_id":thread_id}}
    
    query =  input("User: ")
    if query == 'quit' or query == 'q' or query == 'exit':
        print("Good Bye")
        break
    
    res = graph.invoke(
        {"question": query},
        config = config    
        )
    
    while True:
        
        state =  graph.get_state(config)
        
        if not state.next:
            break 
        
        print("--------")
        print(f"Subject - ",{res["subject"]})
        print(f"Body - ",{res["body"]})
        print("--------")
        
        feedback = input("Do you want to approve it [yes/no] or have some feedback: ")
        
        graph.invoke(
            Command(resume=feedback),
            config=config
        )
        
    print(res["response"])



