# Swami Vivekanand School

A responsive Flask school website with a public admission inquiry form, an admissions inbox, a school photo gallery, and principal-only student and staff management.

## Run locally on Windows

Open the project folder in VS Code:

```powershell
cd C:\Users\JAY\Swami_Vivekanand_School_Management_System\Swami_Vivekanand_School_Management_System
code .
```

In VS Code, open **Terminal → New Terminal** and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
python app.py
```

Open http://127.0.0.1:5000. Leave that terminal running while you use the local site. To stop it, press **Ctrl+C**. Closing VS Code stops the local server; a public deployment runs on the hosting provider instead.

The first start creates a principal account. Set `PRINCIPAL_EMAIL` and `PRINCIPAL_PASSWORD` before the first run if you want specific credentials; otherwise, a one-time generated password is printed in the terminal. The known demo password in an existing database is automatically replaced on the next start, and its new password is printed once. Save it securely.

## Main pages

- `/` — school homepage
- `/admissions` — public inquiry form
- `/gallery` — public photo gallery; the principal can upload and remove photos after signing in
- `/login` — principal sign-in
- `/dashboard` — school management overview and new inquiry count
- `/inquiries` — principal-only admissions follow-up list
- `/students` and `/staff` — principal-only records

The eight photos attached to the earlier chat were stored in temporary paths that have expired. Sign in, open **Gallery**, and upload the original images when they are available again.

## Publish with a public link

For a free demo, Render can host this Flask app behind a public `onrender.com` address. Push the project to a GitHub repository, create a Render **Web Service**, connect the repository, then set:

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn app:app`
- **Environment variables:** `SECRET_KEY` (a long random secret), `PRINCIPAL_EMAIL`, `PRINCIPAL_PASSWORD`, and `COOKIE_SECURE=1`

For a paid Render service with a persistent disk mounted at `/var/data`, also set `DATABASE_PATH=/var/data/school.db` and `UPLOAD_FOLDER=/var/data/uploads`. Both paths must be on persistent storage so inquiries, records, and gallery uploads survive deploys.

Do not publish the school database or any real student or staff records in a public repository. Create a fresh production database and use a unique, strong principal password. On first startup, the principal credentials are created from the environment variables only if no principal is already present.

### Free-hosting storage limits

Render's free web service sleeps after 15 minutes without traffic and uses an ephemeral filesystem. A free service can provide a public demo link, but `school.db` and gallery uploads can disappear during restarts or deploys. Free Render services do not support persistent disks; its free Postgres database expires after 30 days. This app currently uses SQLite, so persistent hosted operation needs either a paid persistent disk mounted for both the SQLite database and photo uploads, or a code change to use a managed PostgreSQL database plus persistent/object storage for photos. For real school records, use a paid setup with backups and access controls rather than the free demo tier.

The public inquiry form stores parent contact details. Review and protect those records as private information, and configure secure storage/backups before using real inquiries.
