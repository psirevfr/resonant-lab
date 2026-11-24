#!/usr/bin/python3
"""Ask GitHub credentials in a native dialog, returning the answer only to Git."""
import re
import subprocess
import sys
from urllib.parse import urlsplit


DIALOG = '''
on run argv
    if item 1 of argv is "Password" then
        set answer to display dialog "Saisissez votre jeton GitHub autorisé à publier sur ce dépôt." with title "Résonant Editor · GitHub" default answer "" buttons {"Annuler", "Continuer"} default button "Continuer" cancel button "Annuler" with hidden answer
    else
        set answer to display dialog "Saisissez votre nom d’utilisateur GitHub." with title "Résonant Editor · GitHub" default answer "" buttons {"Annuler", "Continuer"} default button "Continuer" cancel button "Annuler"
    end if
    return text returned of answer
end run
'''


def credential_kind(prompt):
    match = re.fullmatch(r"(Username|Password) for '([^']+)':\s*", prompt)
    if not match:
        return None
    try:
        url = urlsplit(match[2])
        if url.scheme == 'https' and url.hostname == 'github.com' and url.port in (None, 443) and url.password is None:
            return match[1]
    except ValueError:
        pass
    return None


def main():
    kind = credential_kind(sys.argv[1]) if len(sys.argv) == 2 else None
    if kind is None:
        return 1
    answer = subprocess.run(['/usr/bin/osascript', '-', kind], input=DIALOG, capture_output=True, text=True)
    value = answer.stdout.rstrip('\r\n')
    if answer.returncode or not value or '\n' in value or '\r' in value:
        return 1
    sys.stdout.write(value+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
