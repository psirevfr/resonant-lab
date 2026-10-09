import json
from google_auth_oauthlib.flow import InstalledAppFlow

# Le scope strict requis par l'architecture
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def main():
    # Lance le flux local pour récupérer le refresh token
    flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
    creds = flow.run_local_server(port=0)

    # Sauvegarde les identifiants au format attendu par le script de diagnostic
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': list(creds.scopes)
    }

    with open('drive_token.json', 'w') as f:
        json.dump(token_data, f, indent=2)
    print("Succès ! Fichier 'drive_token.json' généré avec le refresh token.")

if __name__ == '__main__':
    main()
