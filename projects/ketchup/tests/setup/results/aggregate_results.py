import glob
import json

from colorama import Fore, Style, init
from tabulate import tabulate

init()
files = glob.glob("results/result-*.json")
results = [json.load(open(f)) for f in files]
all_connections = []
for r in results:
    for row in r["results"]:
        all_connections.append(row)
total = len(all_connections)
total_successes = sum(1 for _, s, *_ in all_connections if s == "Success (Handler)")
failures = sum(
    1 for _, s, *_ in all_connections if isinstance(s, str) and s.startswith("Failed (Handler")
)
total_input_tokens = sum(inp for *_, inp, _ in all_connections if inp is not None)
total_output_tokens = sum(out for *_, _, out in all_connections if out is not None)
avg_time = sum(r[2] for r in all_connections) / total if total > 0 else 0
max_time = max(r[2] for r in all_connections) if total > 0 else 0
min_time = min(r[2] for r in all_connections) if total > 0 else 0
avg_retry_sleep = sum(r[3] for r in all_connections) / total if total > 0 else 0


def color(val, color):
    return f"{color}{val}{Style.RESET_ALL}"


header = [
    color("Metric", Fore.CYAN + Style.BRIGHT),
    color("Value", Fore.CYAN + Style.BRIGHT),
]
summary_table = [
    [color("Total Successful", Fore.CYAN), color(total_successes, Fore.GREEN)],
    [
        color("Total Failed", Fore.CYAN),
        color(failures, Fore.RED if failures else Fore.GREEN),
    ],
    [
        color("Total execution time", Fore.CYAN),
        f"{sum(r[2] for r in all_connections):.2f}s",
    ],
    [color("Average request time", Fore.CYAN), f"{avg_time:.2f}s"],
    [color("Fastest request", Fore.CYAN), f"{min_time:.2f}s"],
    [color("Slowest request", Fore.CYAN), f"{max_time:.2f}s"],
    [color("Average retry sleep time", Fore.CYAN), f"{avg_retry_sleep:.2f}s"],
    [color("Total input tokens", Fore.CYAN), f"{total_input_tokens:,}"],
    [color("Total output tokens", Fore.CYAN), f"{total_output_tokens:,}"],
    [
        color("Total tokens used", Fore.CYAN),
        f"{total_input_tokens + total_output_tokens:,}",
    ],
    [
        color("Average total tokens per request", Fore.CYAN),
        (f"{(total_input_tokens + total_output_tokens) / total:,.2f}" if total else "0.00"),
    ],
    [
        color("Average input tokens per request", Fore.CYAN),
        f"{total_input_tokens / total:,.2f}" if total else "0.00",
    ],
    [
        color("Average output tokens per request", Fore.CYAN),
        f"{total_output_tokens / total:,.2f}" if total else "0.00",
    ],
]
print("Summary Table:")
print(tabulate(summary_table, headers=header, tablefmt="fancy_grid"))
metrics_header = [
    color("Metric", Fore.CYAN + Style.BRIGHT),
    color("Value", Fore.CYAN + Style.BRIGHT),
]
metrics_table = [
    [color("Total Requests", Fore.CYAN), color(total, Fore.GREEN)],
    [
        color("Success Rate", Fore.CYAN),
        color(f"{(total_successes / total) * 100:.2f}%" if total else "0.00%", Fore.GREEN),
    ],
    [
        color("Failure Rate", Fore.CYAN),
        color(
            f"{(failures / total) * 100:.2f}%" if total else "0.00%",
            Fore.RED if failures else Fore.GREEN,
        ),
    ],
]
print("\nSuccess Metrics Summary:")
print(tabulate(metrics_table, headers=metrics_header, tablefmt="fancy_grid"))
