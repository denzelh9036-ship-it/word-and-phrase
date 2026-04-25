FROM python:3.12-slim

WORKDIR /app

# Server needs psycopg for Postgres (DATABASE_URL).
# Pillow / pyinstaller in requirements.txt are dev deps for the Mac Tk app
# — we install only what the server needs.
COPY requirements.txt ./
RUN pip install --no-cache-dir "psycopg[binary]>=3.2"

COPY main.py db.py auth.py dictionary.py srs.py ./
COPY static ./static

ENV HOST=0.0.0.0
ENV OPEN_BROWSER=0
ENV COOKIE_SECURE=1

# PORT is set by the hosting platform (Render / Fly / Railway).
# Falls back to 8765 locally.
ENV PORT=8765

EXPOSE 8765

CMD ["python", "-u", "main.py"]
