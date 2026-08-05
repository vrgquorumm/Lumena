"""
Очищает обе Telegraph-страницы и выводит их текст.
"""
import json, os, urllib.request
from create_telegraph import PAGE1, PAGE2

def post(url, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def extract_text(nodes, indent=0):
    """Рекурсивно извлекает текст из Telegraph-нод."""
    out = []
    for node in nodes:
        if isinstance(node, str):
            out.append(node)
        elif isinstance(node, dict):
            tag = node.get("tag", "")
            children = node.get("children", [])
            text = extract_text(children, indent)
            if tag in ("h3",):
                out.append(f"\n{'═'*50}\n{text.upper()}\n{'═'*50}")
            elif tag in ("h4",):
                out.append(f"\n── {text}")
            elif tag in ("p",):
                t = text.strip()
                if t:
                    out.append(t)
            elif tag in ("b",):
                out.append(text)
            elif tag in ("i",):
                out.append(f"[{text}]")
            elif tag in ("code",):
                out.append(f"`{text}`")
            elif tag == "a":
                out.append(text)
            elif tag == "li":
                out.append(f"  • {text.strip()}")
            elif tag in ("ul", "ol"):
                out.append(text)
            elif tag == "blockquote":
                out.append(f'  "{text.strip()}"')
            elif tag == "hr":
                out.append("─" * 50)
            elif tag == "br":
                out.append("")
            else:
                out.append(text)
    return "\n".join(filter(lambda x: x is not None, out))

token = open("telegraph_token.txt").read().strip()
urls_file = "telegraph_url.txt"

# Текст обеих страниц
print("=" * 60)
print("СТРАНИЦА 1 — О проекте, Правила и Команды")
print("=" * 60)
print(extract_text(PAGE1))

print("\n\n")
print("=" * 60)
print("СТРАНИЦА 2 — ИИ, Советы, FAQ и Контакты")
print("=" * 60)
print(extract_text(PAGE2))

# Очищаем страницы
BLANK = [{"tag": "p", "children": ["Страница удалена."]}]

pages = [
    ("Lumena--O-proekte-Pravila-i-Komandy-12-08-05",
     "Лумена — удалено"),
    ("Lumena--II-Sovety-FAQ-i-Kontakty-22-08-05",
     "Лумена — удалено"),
]

for path, title in pages:
    r = post("https://api.telegra.ph/editPage", {
        "access_token": token,
        "path": path,
        "title": title,
        "content": BLANK,
        "author_name": "Hydra",
    })
    status = "✅ очищена" if r.get("ok") else f"❌ {r}"
    print(f"\n[{path}] → {status}")
