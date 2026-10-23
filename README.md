# 🧊 Planning Frigo — BDE 42 Perpignan

Bot Discord + interface web (`https://frigo.bde42perpignan.fr`) pour organiser le nettoyage du frigo.

- **Calendrier web** : on clique sur un jour, on coche les membres du serveur, on enregistre.
- **Accès réservé** : connexion via Discord, seuls les membres ayant le rôle ADMIN_BDE peuvent entrer.
  Le rôle est revérifié à chaque requête : retirer le rôle coupe l'accès immédiatement.
- **Rappels** : le jour J, le bot ping les personnes de corvée 3 fois (9h, 12h, 16h par défaut).
- **Changement le jour même** : les personnes ajoutées sont pingées tout de suite, celles qui
  sont retirées sont prévenues qu'elles sont libérées.

Un seul processus Python fait tourner le bot et le site ; les données sont dans `data/frigo.db` (SQLite).

## 1. Créer l'application Discord

1. <https://discord.com/developers/applications> → **New Application**.
2. Onglet **Bot** :
   - **Reset Token** → copier dans `DISCORD_TOKEN`.
   - Activer **Server Members Intent** (obligatoire pour lister les membres et vérifier les rôles).
3. Onglet **OAuth2** :
   - Copier **Client ID** → `DISCORD_CLIENT_ID` et **Client Secret** → `DISCORD_CLIENT_SECRET`.
   - **Redirects** : ajouter `https://frigo.bde42perpignan.fr/callback`.
4. Inviter le bot : OAuth2 → URL Generator → scope `bot`, permissions *View Channels* + *Send Messages*.
   Ouvrir l'URL et choisir le serveur du BDE.

Récupérer les IDs (Discord → Paramètres → Avancés → **Mode développeur**, puis clic droit → *Copier l'identifiant*) :
`GUILD_ID` (le serveur), `CHANNEL_ID` (le salon des rappels), `ALLOWED_ROLE_ID` (le rôle ADMIN_BDE).

## 2. DNS

Chez le registrar de `bde42perpignan.fr`, ajouter un enregistrement :

| Type | Nom    | Valeur                  |
|------|--------|-------------------------|
| A    | frigo  | IP publique du serveur  |

## 3. Lancer sur le serveur

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"   # → SESSION_SECRET
nano .env                                                    # remplir les valeurs
docker compose up -d --build
docker compose logs -f frigo
```

Caddy obtient automatiquement le certificat HTTPS dès que le DNS pointe vers le serveur
(ports 80 et 443 ouverts).

**Le serveur a déjà un nginx / reverse proxy ?** Supprimer le service `caddy` de
`docker-compose.yml`, exposer le port (`ports: ["127.0.0.1:8080:8080"]` sur le service `frigo`)
et ajouter un vhost qui fait `proxy_pass http://127.0.0.1:8080;` pour `frigo.bde42perpignan.fr`.

### Sans Docker

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m frigo
```

## Configuration

| Variable          | Défaut              | Rôle                                  |
|-------------------|---------------------|---------------------------------------|
| `REMINDER_TIMES`  | `09:00,12:00,16:00` | Heures des rappels                    |
| `TIMEZONE`        | `Europe/Paris`      | Fuseau horaire des rappels            |
| `WEB_PORT`        | `8080`              | Port interne du site                  |
| `DB_PATH`         | `data/frigo.db`     | Fichier SQLite                        |

## Sauvegarde

Tout le planning est dans `data/frigo.db` : il suffit de copier ce fichier.
