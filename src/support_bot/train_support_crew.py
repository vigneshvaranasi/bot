#!/usr/bin/env python
from support_bot.crew import support_crew
import pickle
import os
from typing import Dict, Any

def train_support_crew(n_iterations: int = 2, inputs: Dict[str, Any] = None, filename: str = "support_crew_model.pkl"):
    """
    Train the support crew with specified iterations and inputs.
    
    Args:
        n_iterations (int): Number of training iterations to perform
        inputs (Dict[str, Any]): Input data for training, defaults to a sample topic
        filename (str): Name of the file to save the trained model
    """
    if inputs is None:
        inputs = {"topic": "Customer Support Training"}
    
    try:
        print(f"Starting support crew training for {n_iterations} iterations...")
        print(f"Training inputs: {inputs}")
        
        for i in range(n_iterations):
            print(f"\nIteration {i+1}/{n_iterations}")
            result = support_crew.kickoff(inputs=inputs)
            print(f"Training iteration {i+1} completed")
            print(f"Result: {result}...")
            
        # Save the trained crew to a file
        model_path = os.path.join(os.path.dirname(__file__), filename)
        with open(model_path, 'wb') as f:
            pickle.dump(support_crew, f)
        print(f"\nTraining completed successfully. Model saved to: {model_path}")
        
    except Exception as e:
        raise Exception(f"An error occurred while training the support crew: {str(e)}")

if __name__ == "__main__":
    # Example usage
    training_inputs = {
        "topic": "CrewAI Training",
        "user_prompt": "How do I handle API rate limits?",
        "context": "The system is experiencing high traffic"
    }
    
    train_support_crew(
        n_iterations=2,
        inputs=training_inputs,
        filename="support_crew_model.pkl"
    )
