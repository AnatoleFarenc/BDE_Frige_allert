# 🧊 Fridge Duty

A Discord bot with a web calendar to organize who cleans the shared fridge — built for student
unions (BDE) but usable by any Discord community.

- **Web calendar**: click a day, tick the server members on duty, save.
- **Restricted access**: sign in with Discord; only members with a given role can get in.
  The role is re-checked on every request, so removing it revokes access immediately.
- **Reminders**: on the day, the bot pings the people on duty 3 times (9:00, 12:00, 16:00 by default).
- **Same-day changes**: people added are pinged right away, people removed are told they're free.

A single Python process runs both the bot and the website; data is stored in `data/fridge.db` (SQLite).

## 1. Create the Discord application

1. <https://discord.com/developers/applications> → **New Application**.
2. **Bot** tab:
   - **Reset Token** → copy it into `DISCORD_TOKEN`.
   - Enable **Server Members Intent** (required to list members and check roles).
3. **OAuth2** tab:
   - Copy **Client ID** → `DISCORD_CLIENT_ID` and **Client Secret** → `DISCORD_CLIENT_SECRET`.
   - **Redirects**: add `https://<your-domain>/callback` (and `http://localhost:8080/callback` for local testing).
4. Invite the bot to your server (replace `CLIENT_ID`):
   `https://discord.com/oauth2/authorize?client_id=CLIENT_ID&scope=bot&permissions=3072`
   (permissions: *View Channels* + *Send Messages*). Make sure it can see the reminder channel.

Get the IDs (Discord → Settings → Advanced → **Developer Mode**, then right-click → *Copy ID*):
`GUILD_ID` (the server), `CHANNEL_ID` (the reminder channel), `ALLOWED_ROLE_ID` (the role allowed on the website).

## 2. DNS

At your domain registrar, add a record pointing a subdomain to your server:

| Type | Name   | Value                    |
|------|--------|--------------------------|
| A    | fridge | Public IP of your server |

## 3. Run on the server

Requires Docker Engine with the Compose plugin.

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"   # → SESSION_SECRET
nano .env                                                    # fill in the values (BASE_URL, IDs…)
```

The bot listens on `127.0.0.1:8080` and needs a reverse proxy in front of it for HTTPS.
Pick the option matching your server:

**A. The server has no web server yet** — use the bundled Caddy (set `DOMAIN` in `.env`):

```bash
docker compose --profile caddy up -d --build
```

Caddy gets an HTTPS certificate automatically once the DNS points to the server (ports 80 and 443 open).

**B. Caddy is already installed on the server** — add this to `/etc/caddy/Caddyfile`:

```
fridge.example.com {
	reverse_proxy 127.0.0.1:8080
}
```

```bash
sudo systemctl reload caddy
docker compose up -d --build
```

**C. nginx is already installed** — add a virtual host, then get a certificate with
`sudo certbot --nginx -d fridge.example.com`:

```nginx
server {
    listen 80;
    server_name fridge.example.com;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Check the logs with `docker compose logs -f fridge`.

### Without Docker / local testing

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m fridge
```

For local testing, set `BASE_URL=http://localhost:8080` in `.env` and open <http://localhost:8080>.

## Configuration

| Variable          | Default             | Description                             |
|-------------------|---------------------|-----------------------------------------|
| `DOMAIN`          | —                   | Domain for the bundled Caddy (option A) |
| `BASE_URL`        | —                   | Public URL of the website               |
| `REMINDER_TIMES`  | `09:00,12:00,16:00` | Reminder times                          |
| `TIMEZONE`        | `UTC`               | Timezone for reminders                  |
| `WEB_PORT`        | `8080`              | Internal web port                       |
| `DB_PATH`         | `data/fridge.db`    | SQLite file                             |

## Troubleshooting

- **"Access denied" for everyone**: check the logs at startup. If the bot is not in the server
  (`GUILD_ID`) or the role (`ALLOWED_ROLE_ID`) doesn't exist, an error is logged.
- **"Access denied" for one user**: the logs say why (not in the server, or which roles they have).
- **Check the configuration**: `python -m fridge.check [YOUR_USER_ID]` (with Docker:
  `docker compose exec fridge python -m fridge.check [YOUR_USER_ID]`) prints the servers the bot is in,
  whether the channel and role are found, who has the role and what roles a user has.
- **`PrivilegedIntentsRequired`**: enable **Server Members Intent** in the Bot tab.

## Backup

The whole schedule lives in `data/fridge.db`: just copy that file.

## License

[MIT](LICENSE)
