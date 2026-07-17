import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "eCore"
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.urls import resolve
from config.navigation import get_active_module

rf = RequestFactory()
cases = [
    ("/students/etudiants/", "students"),
    ("/academics/sections/", "structure"),
    ("/academics/semestres/", "maquette"),
    ("/evaluations/evaluations/", "evaluations"),
    ("/prestation/prestations/", "prestation"),
    ("/accounts/password/change/", None),
    ("/projets-tutores-realises/", "projets"),
]

for path, expected in cases:
    req = rf.get(path)
    req.user = AnonymousUser()
    req.resolver_match = resolve(path)
    got = get_active_module(req)
    status = "OK" if got == expected else f"FAIL expected {expected}"
    print(path, "->", got, status)
