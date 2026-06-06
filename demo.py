#!/usr/bin/env python3
"""demo.py - Simple Python demo for grokdemo1 project.

Run with: python demo.py
"""

from datetime import datetime
import os
import sys


def greet(name: str = "Grok user") -> str:
    """Return a friendly greeting."""
    return f"Hello, {name}! Welcome to grokdemo1."


def show_project_info() -> dict:
    """Gather basic info about the running environment."""
    return {
        "project": "grokdemo1",
        "python_version": sys.version.split()[0],
        "cwd": os.getcwd(),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "platform": sys.platform,
    }


def main() -> None:
    print("=== GrokDemo1 Python Demo ===")
    print(greet())
    print()

    info = show_project_info()
    print("Project info:")
    for key, value in info.items():
        print(f"  {key}: {value}")

    print("\nGrok is ready to help extend this demo.")
    print("Try asking Grok to:")
    print("  - Add command-line argument parsing (argparse)")
    print("  - Turn this into a small CLI tool")
    print("  - Add tests with pytest")
    print("  - Integrate with the xAI Grok API for a real chat example")


if __name__ == "__main__":
    main()
