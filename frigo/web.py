import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

import aiohttp
from aiohttp import web

from .bot import FrigoBot

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
SESSION_COOKIE = "frigo_session"
STATE_COOKIE = "frigo_oauth_state"
SESSION_MAX_AGE = 30 * 24 * 3600
DISCORD_API = "https://discord.com/api/v10"

BOT_KEY = web.AppKey("bot", FrigoBot)


# --- Signed session cookie -------------------------------------------------

def _sign(secret: bytes, payload: bytes) -> str:
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def make_session(secret: bytes, user_id: int) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"uid": user_id, "exp": int(time.time()) + SESSION_MAX_AGE}).encode()
    )
    return f"{payload.decode()}.{_sign(secret, payload)}"


def read_session(secret: bytes, value: str | None) -> int | None:
    if not value or "." not in value:
        return None
    payload, signature = value.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(secret, payload.encode())):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload))
    except ValueError:
        return None
    if data.get("exp", 0) < time.time():
        return None
    return int(data["uid"])


def current_user(request: web.Request) -> int | None:
    bot = request.app[BOT_KEY]
    user_id = read_session(bot.config.session_secret, request.cookies.get(SESSION_COOKIE))
    # Role is re-checked on every request so removing @ADMIN_BDE revokes access immediately.
    if user_id is None or not bot.is_allowed(user_id):
        return None
    return user_id


def redirect(location: str) -> web.Response:
    return web.Response(status=302, headers={"Location": location})


def _cookie_opts(bot: FrigoBot) -> dict:
    return {"httponly": True, "samesite": "Lax", "secure": bot.config.base_url.startswith("https")}


# --- Pages & OAuth2 ----------------------------------------------------------

async def index(request: web.Request) -> web.StreamResponse:
    page = "index.html" if current_user(request) else "login.html"
    return web.FileResponse(STATIC_DIR / page)


async def login(request: web.Request) -> web.StreamResponse:
    bot = request.app[BOT_KEY]
    state = secrets.token_urlsafe(24)
    query = urlencode({
        "client_id": bot.config.client_id,
        "redirect_uri": bot.config.redirect_uri,
        "response_type": "code",
        "scope": "identify",
        "state": state,
        "prompt": "none",
    })
    response = redirect(f"https://discord.com/oauth2/authorize?{query}")
    response.set_cookie(STATE_COOKIE, state, max_age=600, **_cookie_opts(bot))
    return response


async def callback(request: web.Request) -> web.StreamResponse:
    bot = request.app[BOT_KEY]
    code = request.query.get("code")
    state = request.query.get("state")
    expected = request.cookies.get(STATE_COOKIE)
    if not code or not state or not expected or not hmac.compare_digest(state, expected):
        return web.Response(status=400, text="Connexion invalide, reessaie depuis la page d'accueil.")

    async with aiohttp.ClientSession() as http:
        token_resp = await http.post(f"{DISCORD_API}/oauth2/token", data={
            "client_id": bot.config.client_id,
            "client_secret": bot.config.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": bot.config.redirect_uri,
        })
        if token_resp.status != 200:
            log.warning("Echec OAuth2: %s %s", token_resp.status, await token_resp.text())
            return web.Response(status=502, text="Discord a refuse la connexion.")
        access_token = (await token_resp.json())["access_token"]
        user_resp = await http.get(
            f"{DISCORD_API}/users/@me", headers={"Authorization": f"Bearer {access_token}"}
        )
        user_id = int((await user_resp.json())["id"])

    if not bot.is_allowed(user_id):
        response = web.FileResponse(STATIC_DIR / "forbidden.html", status=403)
        response.del_cookie(STATE_COOKIE)
        return response

    response = redirect("/")
    response.set_cookie(
        SESSION_COOKIE, make_session(bot.config.session_secret, user_id),
        max_age=SESSION_MAX_AGE, **_cookie_opts(bot),
    )
    response.del_cookie(STATE_COOKIE)
    return response


async def logout(request: web.Request) -> web.StreamResponse:
    response = redirect("/")
    response.del_cookie(SESSION_COOKIE)
    return response


# --- JSON API ----------------------------------------------------------------

@web.middleware
async def api_auth(request: web.Request, handler):
    if not request.path.startswith("/api/"):
        return await handler(request)
    if request.app[BOT_KEY].guild is None:
        return web.json_response({"error": "Bot pas encore connecte a Discord"}, status=503)
    user_id = current_user(request)
    if user_id is None:
        return web.json_response({"error": "Non connecte"}, status=401)
    if request.method != "GET":
        # CSRF protection: only accept JSON writes coming from our own origin.
        origin = request.headers.get("Origin")
        if request.content_type != "application/json" or (
            origin and origin != request.app[BOT_KEY].config.base_url
        ):
            return web.json_response({"error": "Requete refusee"}, status=403)
    request["user_id"] = user_id
    return await handler(request)


def _member_json(member) -> dict:
    return {"id": str(member.id), "name": member.display_name, "avatar": member.display_avatar.url}


async def api_me(request: web.Request) -> web.Response:
    member = request.app[BOT_KEY].guild.get_member(request["user_id"])
    return web.json_response(_member_json(member))


async def api_members(request: web.Request) -> web.Response:
    members = [m for m in request.app[BOT_KEY].guild.members if not m.bot]
    members.sort(key=lambda m: m.display_name.lower())
    return web.json_response([_member_json(m) for m in members])


def _parse_date(value: str | None) -> date:
    try:
        return date.fromisoformat(value or "")
    except ValueError:
        raise web.HTTPBadRequest(text="Date invalide (format attendu : AAAA-MM-JJ)")


async def api_get_duties(request: web.Request) -> web.Response:
    start = _parse_date(request.query.get("from"))
    end = _parse_date(request.query.get("to"))
    if end < start or end - start > timedelta(days=62):
        raise web.HTTPBadRequest(text="Intervalle invalide")
    duties = request.app[BOT_KEY].store.get_range(start, end)
    return web.json_response(
        {day: [str(uid) for uid in uids] for day, uids in duties.items()}
    )


async def api_set_duty(request: web.Request) -> web.Response:
    bot = request.app[BOT_KEY]
    day = _parse_date(request.match_info["day"])
    try:
        body = await request.json()
        user_ids = {int(uid) for uid in body["user_ids"]}
    except (ValueError, KeyError, TypeError):
        raise web.HTTPBadRequest(text="Corps de requete invalide")

    guild = bot.guild
    unknown = [uid for uid in user_ids if guild.get_member(uid) is None]
    if unknown:
        raise web.HTTPBadRequest(text="Certaines personnes ne sont pas sur le serveur")

    previous = bot.store.get(day)
    bot.store.set(day, user_ids)
    log.info("Planning du %s modifie par %s : %s", day, request["user_id"], sorted(user_ids))

    if day == bot.today():
        await bot.notify_same_day_change(user_ids - previous, previous - user_ids)

    return web.json_response({"day": day.isoformat(), "user_ids": [str(u) for u in user_ids]})


# --- Server ------------------------------------------------------------------

async def start_web(bot: FrigoBot) -> None:
    app = web.Application(middlewares=[api_auth])
    app[BOT_KEY] = bot
    app.add_routes([
        web.get("/", index),
        web.get("/login", login),
        web.get("/callback", callback),
        web.get("/logout", logout),
        web.get("/api/me", api_me),
        web.get("/api/members", api_members),
        web.get("/api/duties", api_get_duties),
        web.put("/api/duties/{day}", api_set_duty),
        web.static("/static", STATIC_DIR),
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, bot.config.web_host, bot.config.web_port).start()
    log.info("Interface web sur http://%s:%s", bot.config.web_host, bot.config.web_port)
