"""Corrige l'indentation des balises <form> après form_errors."""
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "eCore" / "templates"
needle = '{% include "components/form_errors.html" %}\n<form'
replacement = '{% include "components/form_errors.html" %}\n\n                <form'
for p in root.rglob("*_form.html"):
    t = p.read_text(encoding="utf-8")
    if needle in t:
        t = t.replace(needle, replacement)
        p.write_text(t, encoding="utf-8")
        print("indented", p.relative_to(root))
