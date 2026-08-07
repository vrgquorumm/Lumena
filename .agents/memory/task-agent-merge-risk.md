---
name: Task agent merge — entry point deletion risk
description: Task agents that append code to bot.py can silently delete asyncio.run(main()) causing invisible crash loop
---

# Task agent merge — entry point deletion risk

## Rule
After any task agent merge into bot.py, always verify `asyncio.run(main())` still exists at the very end of the file.

**Why:** Task agents implementing features sometimes append helper functions (like `_apply_data()`) to the bottom of bot.py. This overwrites the `if __name__ == "__main__": asyncio.run(main())` entry point. Without it, the bot imports fine, registers all handlers, but polling never starts — the process exits with code 0. Railway sees this as a crash and restart-loops infinitely with no useful error message.

**How to apply:** After every task agent merge to bot.py, run:
```
grep -n "if __name__\|asyncio\.run" bot/bot.py | tail -5
```
If `asyncio.run(main())` is missing, append:
```python
if __name__ == "__main__":
    asyncio.run(main())
```
