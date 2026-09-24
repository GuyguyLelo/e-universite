"""Compte de connexion d'un étudiant inscrit."""
from django.contrib.auth.models import Group, User

GROUPE_ETUDIANT = "Etudiant"


def _normaliser_identifiant(valeur):
    return " ".join((valeur or "").casefold().split())


def resoudre_identifiant(saisie):
    """Retourne le nom d'utilisateur à partir du matricule ou du nom affiché."""
    saisie = (saisie or "").strip()
    if not saisie:
        return None

    utilisateur = User.objects.filter(username__iexact=saisie).only("username").first()
    if utilisateur:
        return utilisateur.username

    from students.models import Student

    etudiant = (
        Student.objects.filter(numero_etudiant__iexact=saisie, user__isnull=False)
        .select_related("user")
        .first()
    )
    if etudiant:
        return etudiant.user.username

    cle = _normaliser_identifiant(saisie)
    candidats = Student.objects.filter(user__isnull=False).select_related("user")
    morceaux = cle.split()
    if len(morceaux) >= 2:
        candidats = candidats.filter(nom__icontains=morceaux[-1])
    else:
        candidats = candidats.filter(nom__iexact=saisie)
    for etudiant in candidats:
        variantes = {
            _normaliser_identifiant(etudiant.nom),
            _normaliser_identifiant(f"{etudiant.prenom} {etudiant.nom}"),
            _normaliser_identifiant(f"{etudiant.nom} {etudiant.prenom}"),
        }
        if cle in variantes:
            return etudiant.user.username
    return None


def variantes_mot_de_passe(mot_de_passe):
    """Accepte la date de naissance avec ou sans séparateurs."""
    mot_de_passe = mot_de_passe or ""
    variantes = [mot_de_passe]
    chiffres = "".join(caractere for caractere in mot_de_passe if caractere.isdigit())
    if len(chiffres) == 8:
        for variante in (chiffres, chiffres[6:8] + chiffres[4:6] + chiffres[0:4]):
            if variante not in variantes:
                variantes.append(variante)
    return variantes


def mot_de_passe_initial(student):
    """Date de naissance au format JJMMAAAA, communiquée à l'étudiant."""
    if not student.date_naissance:
        return ""
    return student.date_naissance.strftime("%d%m%Y")


def assurer_compte_etudiant(student):
    """Crée ou met à jour le compte lié à l'étudiant. Ne réinitialise pas un mot de passe existant."""
    if not student.pk or not student.numero_etudiant or not student.email:
        return None

    user = student.user
    if user is None:
        user = User.objects.filter(username=student.numero_etudiant).first()
    nouveau = user is None
    if nouveau:
        user = User(username=student.numero_etudiant)
        initial = mot_de_passe_initial(student)
        if initial:
            user.set_password(initial)
        else:
            user.set_unusable_password()

    user.username = student.numero_etudiant
    user.first_name = (student.prenom or "")[:150]
    user.last_name = (student.nom or "")[:150]
    user.email = student.email
    user.is_staff = False
    user.is_superuser = False
    user.is_active = student.statut == "actif"
    user.save()

    if student.user_id != user.pk:
        type(student).objects.filter(pk=student.pk).update(user=user)
        student.user = user

    groupe, _ = Group.objects.get_or_create(name=GROUPE_ETUDIANT)
    user.groups.add(groupe)
    return user
