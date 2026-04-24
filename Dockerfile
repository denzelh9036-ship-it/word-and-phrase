FROM python:3.12-slim

WORKDIR /app

# Server uses stdlib only — no pip install needed.
# (Pillow / pyinstaller are dev deps for the Mac Tk app, not the server.)

COPY main.py db.py auth.py dictionary.py srs.py ./
COPY static ./static

# DB goes on a mounted persistent volume at /data
ENV WORDPHRASE_DB_DIR=/data
ENV HOST=0.0.0.0
ENV OPEN_BROWSER=0
ENV COOKIE_SECURE=1

# PORT is set by the hosting platform (Render / Fly / Railway).
# Falls back to 8765 locally.
ENV PORT=8765

EXPOSE 8765

CMD ["python", "-u", "main.py"]
