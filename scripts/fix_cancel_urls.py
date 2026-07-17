import re
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "eCore" / "templates"
pat = re.compile(r"\{% '([^']+)'([^%]*?) as cancel_url %\}")
for p in list(root.rglob("*_form.html")) + list(root.rglob("*confirm_delete*.html")):
    t = p.read_text(encoding="utf-8")
    n = pat.sub(r"{% url '\1'\2 as cancel_url %}", t)
    if n != t:
        p.write_text(n, encoding="utf-8")
        print("fixed", p.relative_to(root))
