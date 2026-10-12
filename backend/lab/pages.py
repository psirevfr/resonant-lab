"""Accessible account pages sharing the lab's dark palette."""
from html import escape
from .auth import csrf_token


def shell(title,body,embedded=False):
    return f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · Résonant</title><link rel="stylesheet" href="/auth.css"></head><body class="{'auth-embedded' if embedded else ''}"><main class="auth-shell"><section class="auth-intro"><a class="brand" href="/mon-lab/">∿ <span>résonant<small>LAB</small></span></a><span class="eyebrow">DU SIGNAL AU MODÈLE</span><h1>Votre espace<br>de recherche sonore.</h1><p>Analyser une note. Comprendre ses résonances. Construire un modèle dont chaque module reste visible.</p><div class="signal-art" aria-hidden="true"><svg viewBox="0 0 500 120"><path d="M0 60 H45 L55 10 L65 110 L75 20 L85 100 L95 27 L105 93 L115 32 L125 88 L135 37 L145 83 L155 42 L165 78 L175 46 L185 74 L195 49 L205 71 L215 51 L225 69 L235 53 L245 67 L255 55 L265 65 L275 56 L285 64 L295 57 L305 63 L315 58 L325 62 L335 59 L345 61 H500"/></svg><span>01 / ANALYSE</span><span>02 / SYNTHÈSE</span><span>03 / EXPLORATION</span></div></section><section class="auth-card">{body}</section></main><script src="/auth.js" defer></script></body></html>'''


def auth_form(mode,nonce,error='',username='',email='',registered=False,embedded=False):
    signup=mode=='register';title='Créer un compte' if signup else 'Connexion';target=('/register' if signup else '/login')+('?embed=1' if embedded else '')
    feedback=f'<div id="form-error" class="form-error" role="alert">{escape(error)}</div>' if error else '<div id="form-error"></div>'
    if registered:feedback+='<p role="status" class="success">Compte créé. Vous pouvez vous connecter.</p>'
    invalid=' aria-invalid="true" aria-describedby="form-error"' if error else ''
    fields=f'''<label for="username">Pseudo</label><input id="username" name="username" autocomplete="username" required maxlength="80" value="{escape(username,quote=True)}"{invalid}>'''
    if signup:fields+=f'<label for="email">Adresse e-mail</label><input id="email" name="email" type="email" autocomplete="email" required maxlength="254" value="{escape(email,quote=True)}"{invalid}>'
    fields+=f'<label for="password">Mot de passe</label><input id="password" name="password" type="password" autocomplete="{"new-password" if signup else "current-password"}" required{invalid}>'
    hint='<p class="hint">Au moins 8 caractères, au plus 72 octets UTF-8.</p>' if signup else ''
    suffix='?embed=1' if embedded else ''
    link=f'<a href="/login{suffix}">Vous avez déjà un compte ? Connexion</a>' if signup else f'<a href="/register{suffix}">Créer un compte</a>'
    return shell(title,f'''<span class="eyebrow">MON LAB</span><h2>{title}</h2><p>Retrouvez vos calculs et poursuivez vos expérimentations.</p>{feedback}<form method="post" action="{target}"><input type="hidden" name="csrf" value="{csrf_token(nonce)}">{fields}{hint}<button type="submit" data-wait="Vérification…">{title if signup else 'Se connecter'}</button><p class="form-status" role="status" aria-live="polite"></p></form><div class="auth-links">{link}{'' if embedded else '<a href="/mon-lab/">Retour à Mon Lab</a>'}</div>''',embedded)


def signed_out():
    return shell('Mon Lab','''<span class="eyebrow">MON LAB</span><h2>Un espace pour vos modèles.</h2><p>Connectez-vous pour lancer vos analyses, suivre vos calculs et retrouver leurs résultats.</p><a class="primary-link" href="/login">Connexion</a><a class="secondary-link" href="/register">Créer un compte</a><p class="hint">Les modèles et résultats de votre compte sont accessibles après connexion.</p>''')
