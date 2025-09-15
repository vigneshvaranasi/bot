import random
import time
import argparse
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.support_bot.crew import support_crew
import asyncio


PROMPTS = [
    "how to solve HTTP 499 timeout errors",
    "Why did the UPI Collect API start failing?",
    "How do I resolve payment latency issues?",
    "What caused the database outage last week?",
    "Explain carding attack mitigation steps",
]


def benchmark(N, log_file):
    times = []
    with open(log_file, "w") as f:
        for i in range(N):
            prompt = random.choice(PROMPTS)
            inputs = {"user_prompt": prompt, "context": ""}
            start = time.time()
            result = support_crew.kickoff(inputs=inputs)
            elapsed = time.time() - start
            times.append(elapsed)
            log_line = f"Run {i+1}: {elapsed:.2f}s | Prompt: {prompt}\n"
            print(log_line, end="")
            f.write(log_line)
        avg = sum(times) / len(times)
        avg_line = f"\nAverage time: {avg:.2f}s over {N} runs\n"
        print(avg_line, end="")
        f.write(avg_line)

async def run_one_thread(prompt):
    inputs = {"user_prompt": prompt, "context": ""}
    start = time.time()
    result = await support_crew.kickoff_async(inputs=inputs)
    elapsed = time.time() - start
    return elapsed, prompt

async def async_benchmark(N, log_file):
    tasks = [run_one_thread(random.choice(PROMPTS)) for _ in range(N)]
    results = await asyncio.gather(*tasks)
    with open(log_file, "w") as f:
        for i, (elapsed, prompt) in enumerate(results):
            log_line = f"Run {i+1}: {elapsed:.2f}s | Prompt: {prompt}\n"
            print(log_line, end="")
            f.write(log_line)
        avg = sum(elapsed for elapsed, _ in results) / N
        avg_line = f"\nAverage time: {avg:.2f}s over {N} runs\n"
        print(avg_line, end="")
        f.write(avg_line)

def main():
    parser = argparse.ArgumentParser(description="Benchmark support bot")
    parser.add_argument("--N", type=int, default=20, help="Number of runs")
    parser.add_argument("--mode", choices=["sync", "async"], default="sync", help="Benchmark mode")
    parser.add_argument("--log", type=str, default=None, help="Log file path")
    args = parser.parse_args()

    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    benchmarks_dir = os.path.join(root_dir, "benchmarks")
    os.makedirs(benchmarks_dir, exist_ok=True)
    log_file = args.log or os.path.join(benchmarks_dir, "benchmark_log.txt")

    if args.mode == "sync":
        benchmark(args.N, log_file)
    else:
        asyncio.run(async_benchmark(args.N, log_file))

if __name__ == "__main__":
    main()

