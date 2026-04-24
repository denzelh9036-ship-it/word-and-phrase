# Deploying Word & Phrase to the Web

After deployment, anyone with the URL opens it in a browser → registers an account → uses it. Each user has their own vocabulary book stored on the server.

Your local `app.py` (Mac Tk app) is unaffected — it keeps running locally with its own `~/Library/Application Support/WordAndPhrase/app.db`.

---

## Option 1 — Render (recommended: easiest, reliable, ~$8/mo)

### 1. Push the code to GitHub

```bash
cd "/Users/huanghuangdingzun/Desktop/Word and Phrase"
git init
git add .
git commit -m "Initial commit"
```

Then on github.com:
- Click **New repository** → name it `word-and-phrase` → **Create** (can be private)
- Copy the two-line push snippet GitHub shows you, run it in Terminal.

### 2. Deploy to Render

- Go to [render.com](https://render.com), sign up with GitHub.
- Dashboard → **New** → **Blueprint** → pick your `word-and-phrase` repo.
- Render reads [render.yaml](render.yaml) and proposes the service. Click **Apply**.
- Wait ~3 minutes. It assigns a URL like `https://word-and-phrase-xxxx.onrender.com`.
- Share that URL with anyone — they register / log in in the browser.

### Free-tier note (if you picked "Free" plan instead of Starter)

Render's free web service plan sleeps after 15 minutes of no traffic and has **no persistent disk** — your SQLite file is wiped every time you deploy. Fine for a beta / demo, **not** for real users.

To make data persistent, change `plan: starter` + `disk:` are already in [render.yaml](render.yaml). That adds up to $7 (web) + $1 (1GB disk) = **$8/mo**.

---

## Option 2 — Fly.io (cheaper: ~$2–3/mo, persistent disk included)

Fly.io is pay-per-use. A tiny VM with 1GB volume typically runs $2–3/mo.

Install flyctl once:

```bash
curl -L https://fly.io/install.sh | sh
fly auth signup     # or: fly auth login
```

In the project folder:

```bash
cd "/Users/huanghuangdingzun/Desktop/Word and Phrase"

# Create a volume for the SQLite DB (the name matches fly.toml's mount source)
fly volumes create wordphrase_data --size 1 --region hkg

# Deploy
fly launch --no-deploy --copy-config      # reads fly.toml, skips generating one
fly deploy
```

After deploy, Fly gives you `https://word-and-phrase.fly.dev` (or pick a different app name). Share it with users.

---

## Option 3 — Any VPS (~$4–6/mo, most flexible)

Rent a small VPS (Vultr / DigitalOcean / Linode / 腾讯云轻量 / 阿里云轻量). SSH in, then:

```bash
# On the VPS
apt install -y python3 git
git clone https://github.com/<you>/word-and-phrase.git
cd word-and-phrase

# Data directory
mkdir -p /var/lib/wordphrase

# systemd service (put this in /etc/systemd/system/wordphrase.service)
cat > /etc/systemd/system/wordphrase.service <<'EOF'
[Unit]
Description=Word & Phrase
After=network.target

[Service]
User=root
WorkingDirectory=/root/word-and-phrase
Environment=HOST=127.0.0.1
Environment=PORT=8765
Environment=OPEN_BROWSER=0
Environment=COOKIE_SECURE=1
Environment=WORDPHRASE_DB_DIR=/var/lib/wordphrase
ExecStart=/usr/bin/python3 main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

systemctl enable --now wordphrase
```

Then put Caddy or Nginx in front for HTTPS:

```bash
# /etc/caddy/Caddyfile
yourdomain.com {
    reverse_proxy 127.0.0.1:8765
}
```

Caddy auto-gets a free Let's Encrypt cert. Visit `https://yourdomain.com` from anywhere.

---

## After deployment — operational notes

- **Dictionary and image sources still require outbound internet from the server.** Every server your users hit must reach `api.dictionaryapi.dev` and `en.wikipedia.org`. These are blocked in some countries — if that's your audience, run the server inside that country (阿里云国内节点 etc.).
- **Backing up the DB**: it's a single file at `$WORDPHRASE_DB_DIR/app.db`. On a VPS, `scp` it periodically. On Render, use "Shell" in the dashboard → `sqlite3 /data/app.db .dump > backup.sql` → download.
- **Sessions last 30 days** (cookie expiry in [auth.py](auth.py)). Users stay logged in for a month.
- **You're not signing passwords, you're hashing them**: PBKDF2-HMAC-SHA256, 200k iterations, 16-byte salt. If the DB leaks, passwords can't be reversed, but move to a managed DB + encrypt at rest if you're storing anything sensitive.

---

## Updating the deployed app

Whichever option you chose, update flow is the same:

```bash
# edit code locally, test with python3 main.py
git commit -am "describe your change"
git push
```

- Render: auto-redeploys on push
- Fly.io: `fly deploy`
- VPS: `ssh vps 'cd word-and-phrase && git pull && systemctl restart wordphrase'`

---

## Which should I pick?

| Users | Budget | Recommendation |
|---|---|---|
| 1–5 friends, beta | Free | Render free tier (accept DB wipes on redeploy) |
| 5–50, real use | $8/mo | **Render Starter + 1GB disk** (render.yaml as-is) |
| Same, cheaper | $2–3/mo | Fly.io with `fly.toml` |
| You want full control | $5/mo | VPS + Caddy |
| You want it to never break | $$+ | Managed Postgres (Supabase/Neon free tier) + Render/Fly for the web server |
