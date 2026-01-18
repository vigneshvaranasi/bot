"""CLI interface for the copilot AI agent.

This module provides a command-line interface for interacting with
the incident resolution copilot.
"""

import argparse
import logging

from langchain_core.messages import AIMessage, ToolMessage

from src.copilot.graph import create_agent_graph

# Suppress verbose logging from dependencies
logging.getLogger("absl").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the copilot CLI."""
    parser = argparse.ArgumentParser(description="Agentic AI Copilot")
    parser.add_argument("-stream", action="store_true", help="Enable streaming output")
    args = parser.parse_args()

    app = create_agent_graph()

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
                for output in app.stream(
                    inputs,
                    stream_mode=["updates", "messages"],
                    config=thread_config
                ):
                    for key, value in output.items():
                        print(f"--- Step: {key.upper()} ---")
                        last_message = value["messages"][-1]
                        if isinstance(last_message, AIMessage):
                            if last_message.tool_calls:
                                print(
                                    f"Model wants to call tool: "
                                    f"{last_message.tool_calls[0]['name']}"
                                )
                                print(
                                    f"   with arguments: "
                                    f"{last_message.tool_calls[0]['args']}"
                                )
                            else:
                                print(f"Final Answer: {last_message.content}")
                        elif isinstance(last_message, ToolMessage):
                            print(f"Tool executed: {last_message.name}")
                            print(f"Tool result: {last_message.content}")
            except Exception as e:
                logger.error(f"Error during streaming: {e}")
                print(f"Error: An error occurred while processing your request.")
                continue
        else:
            # Non-streaming mode
            try:
                result = app.invoke(inputs, config=thread_config)
            except Exception as e:
                logger.error(f"Error during invocation: {e}")
                print("Error: An error occurred while processing your request.")
                continue

            final_message = result["messages"][-1]
            if isinstance(final_message, AIMessage):
                print(f"Final Answer: {final_message.content}")
            else:
                print(f"Response: {final_message.content}")


if __name__ == "__main__":
    main()
