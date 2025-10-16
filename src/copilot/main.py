import logging
import argparse
logging.getLogger('absl').setLevel(logging.ERROR)

from src.copilot.graph import create_agent_graph
from langchain_core.messages import AIMessage, ToolMessage

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agentic AI Copilot")
    parser.add_argument('-stream', action='store_true', help='Enable streaming output')
    args = parser.parse_args()

    app = create_agent_graph()

    # User Prompt
    print("Hey, how can I help you?")
    thread_config = {"configurable": {"thread_id": "cli-session"}}

    while True:
        try:
            user_question = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break

        if not user_question:
            continue
        if user_question.lower() in {"exit", "quit", "q"}:
            print("Bye!")
            break

        # Prepare inputs; the graph will retrieve prior context via checkpointer
        inputs = {"messages": [("user", user_question)]}

        if args.stream:
            # Streaming outputs from the agent
            try:
                for output in app.stream(inputs, stream_mode=["updates", "messages"], config=thread_config):
                    for key, value in output.items():
                        print(f"--- Step: {key.upper()} ---")
                        last_message = value["messages"][-1]
                        if isinstance(last_message, AIMessage):
                            if last_message.tool_calls:
                                print(f"Model wants to call tool: {last_message.tool_calls[0]['name']}")
                                print(f"   with arguments: {last_message.tool_calls[0]['args']}")
                            else:
                                print(f"Final Answer: {last_message.content}")
                        elif isinstance(last_message, ToolMessage):
                            print(f"Tool executed: {last_message.name}")
                            print(f"Tool result: {last_message.content}")
            except Exception as e:
                print(f"Error during streaming: {e}")
                continue

        else:
            # Non-streaming mode
            try:
                result = app.invoke(inputs, config=thread_config)
            except Exception as e:
                print(f"Error: {e}")
                continue

            final_message = result["messages"][-1]
            if isinstance(final_message, AIMessage):
                print(f"Final Answer: {final_message.content}")
            else:
                print(f"Response: {final_message.content}")