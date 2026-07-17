#!/usr/bin/env python3
"""Modernise les templates *_form.html au pattern e-Core."""
from __future__ import annotations

import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "eCore" / "templates"

SKIP = {
    "students/student_form.html",
    "students/inscription_form.html",
    "students/document_form.html",
}

MESSAGES_BLOCK = re.compile(
    r"\s*\{% if messages %\}.*?\{% endif %\}\s*",
    re.DOTALL,
)

OLD_HEADER = re.compile(
    r'<div class="card-header(?:[^"]*)">\s*'
    r'<h[56](?: class="mb-0")?>\{\{ title \}\}</h[56]>\s*'
    r"</div>\s*",
    re.DOTALL,
)

ACTIONS = re.compile(
    r'<div class="d-flex justify-content-between(?: mt-4)?">\s*'
    r'<a href="(\{% url [^%]+%\})" class="btn btn-secondary(?:[^"]*)">'
    r'(?:\s*<i class="[^"]+"></i>\s*)?(?:Annuler|Retour)[^<]*</a>\s*'
    r'<button type="submit" class="btn btn-primary(?:[^"]*)">'
    r'(?:\s*<i class="[^"]+"></i>\s*)?(?:Enregistrer|Changer le mot de passe)[^<]*</button>\s*'
    r'</div>',
    re.DOTALL,
)


def modernize(content: str) -> str:
    if "components/page_toolbar.html" in content:
        return content

    content = OLD_HEADER.sub(
        '{% include "components/page_toolbar.html" with toolbar_title=title toolbar_subtitle=subtitle %}\n      ',
        content,
        count=1,
    )

    content = MESSAGES_BLOCK.sub(
        '\n        {% include "components/messages.html" %}\n\n'
        '        {% include "components/form_errors.html" %}\n',
        content,
        count=1,
    )

    def replace_actions(m: re.Match[str]) -> str:
        href = m.group(1).strip()
        inner = href[7:-2].strip()  # url 'app:name' ...
        return (
            f"{{% {inner} as cancel_url %}}\n"
            f'                    {{% include "components/form_actions.html" with cancel_url=cancel_url %}}'
        )

    content = ACTIONS.sub(replace_actions, content)

    # Fix title suffix to e-Core where old branding remains
    content = content.replace(
        "{% block title %}{{ title }} - Gestion Académique LMD{% endblock %}",
        "{% block title %}{{ title }} - e-Core{% endblock %}",
    )

    # breadcrumb active class consistency
    content = content.replace(
        '<li class="breadcrumb-item active">',
        '<li class="breadcrumb-item f-w-400 active">',
    )

    return content


def main() -> None:
    updated = 0
    for path in sorted(TEMPLATES.rglob("*_form.html")):
        rel = path.relative_to(TEMPLATES).as_posix()
        if rel in SKIP:
            continue
        original = path.read_text(encoding="utf-8")
        new = modernize(original)
        if new != original:
            path.write_text(new, encoding="utf-8")
            print(f"updated: {rel}")
            updated += 1
        else:
            print(f"skipped: {rel}")
    print(f"done — {updated} file(s) updated")


if __name__ == "__main__":
    main()
