#!/usr/bin/env python3
"""Modernise confirm_delete et en-têtes card-header restants."""
from __future__ import annotations

import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "eCore" / "templates"

SKIP = {
    "components/base_confirm_delete.html",
    "components/page_toolbar.html",
    "evaluations/base_confirm_delete.html",
}

OLD_DELETE_HEADER = re.compile(
    r'<div class="card-header(?:[^"]*)">\s*'
    r'<h5(?: class="mb-0")?>(?:Confirmer la suppression|Confirmation de suppression)</h5>\s*'
    r"</div>\s*",
    re.DOTALL,
)

OLD_GENERIC_HEADER = re.compile(
    r'<div class="card-header(?:[^"]*)">\s*'
    r'<h5(?: class="mb-0")?>\{\{[^}]+\}\}</h5>\s*'
    r"</div>\s*",
    re.DOTALL,
)

OLD_HEADER_WITH_H5_TEXT = re.compile(
    r'<div class="card-header(?:[^"]*)">\s*'
    r"<h5(?: class=\"mb-0\")?>([^<]+)</h5>\s*"
    r"</div>\s*",
    re.DOTALL,
)

DELETE_ACTIONS = re.compile(
    r'<div class="d-flex justify-content-between(?: mt-3)?">\s*'
    r'<a href="(\{% url [^%]+%\})" class="btn btn-secondary(?:[^"]*)">'
    r'(?:\s*<i class="[^"]+"></i>\s*)?(?:Annuler|Retour)[^<]*</a>\s*'
    r'<button type="submit" class="btn btn-(danger|success|primary)(?:[^"]*)">'
    r'(?:\s*<i class="[^"]+"></i>\s*)?([^<]+)</button>\s*'
    r"</div>",
    re.DOTALL,
)

WARN_ALERT = re.compile(
    r'<div class="alert alert-warning">',
)

INFO_ALERT = re.compile(
    r'<div class="alert alert-info">',
)


def toolbar_for_delete() -> str:
    return (
        '{% include "components/page_toolbar.html" with toolbar_title="Confirmer la suppression" '
        'toolbar_subtitle="Cette action est irréversible" %}\n            '
    )


def replace_delete_actions(m: re.Match[str]) -> str:
    href = m.group(1).strip()
    btn_class = m.group(2)
    label = m.group(3).strip()
    inner = href[7:-2].strip()
    icon = "fa-trash" if btn_class == "danger" else "fa-calculator" if btn_class == "success" else "fa-save"
    return (
        f"{{% {inner} as cancel_url %}}\n"
        f'                    {{% include "components/form_actions.html" with cancel_url=cancel_url '
        f'submit_label="{label}" submit_class="btn-{btn_class}" submit_icon="{icon}" %}}'
    )


def modernize_confirm_delete(content: str) -> str:
    if "components/page_toolbar.html" in content and "Confirmer la suppression" in content:
        return content
    content = OLD_DELETE_HEADER.sub(toolbar_for_delete(), content, count=1)
    if 'include "components/messages.html"' not in content:
        content = content.replace(
            '<div class="card-body">',
            '<div class="card-body">\n                {% include "components/messages.html" %}\n',
            1,
        )
    content = WARN_ALERT.sub('<div class="alert alert-warning ecore-alert" role="alert">', content)
    content = DELETE_ACTIONS.sub(replace_delete_actions, content)
    return content


def modernize_file(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    original = content
    if path.name.endswith("confirm_delete.html"):
        content = modernize_confirm_delete(content)
    content = INFO_ALERT.sub('<div class="alert alert-info ecore-alert" role="alert">', content)
    return content if content != original else original


def main() -> None:
    updated = 0
    for path in sorted(TEMPLATES.rglob("*.html")):
        rel = path.relative_to(TEMPLATES).as_posix()
        if rel in SKIP:
            continue
        new = modernize_file(path)
        if new != path.read_text(encoding="utf-8"):
            path.write_text(new, encoding="utf-8")
            print("updated:", rel)
            updated += 1
    print(f"done — {updated} file(s)")


if __name__ == "__main__":
    main()
