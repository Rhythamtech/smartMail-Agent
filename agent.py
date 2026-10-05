import os
from uuid import uuid4

from langgraph.types import Command

from email_graph import build_graph


def main() -> None:
    graph = build_graph()
    thread_id = uuid4()
    config = {"configurable": {"thread_id": str(thread_id)}}

    while True:
        query = input("User: ")
        if query in ("quit", "q", "exit"):
            print("Good Bye")
            break

        res = graph.invoke({"question": query}, config=config)

        while True:
            state = graph.get_state(config)
            if not state.next:
                break
            print("--------")
            print(f"Subject - {res.get('subject')}")
            print(f"Body - {res.get('body')}")
            print("--------")
            feedback = input("Do you want to approve it [yes/no] or have some feedback: ")
            res = graph.invoke(Command(resume=feedback), config=config)

        print(res.get("response"))


if __name__ == "__main__":
    main()
