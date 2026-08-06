"""
Entry point for Railway deployment.
Runs the actual bot from the bot/ directory.
"""
import os
import sys

# Change to bot directory so all relative paths (data/, etc.) work correctly
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot"))
sys.path.insert(0, os.getcwd())

# Run bot
import asyncio
from bot import main

if __name__ == "__main__":
    asyncio.run(main())
