# skills/hello.py
NAME = "hello"
DESCRIPTION = "Greets and shows a memory fact."
TRIGGERS = [r"\bhello\b", r"\bhi orion\b"]

def run(query: str, context: dict) -> str:
    mem = context.get("mem")
    fav = mem.recall("favorite_color") if mem else None
    extra = f" Your favorite color is {fav}." if fav else ""
    return "Hello, Benjamin!" + extra