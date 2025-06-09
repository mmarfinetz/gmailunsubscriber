# Gmail Unsubscriber

Gmail Unsubscriber helps you automatically unsubscribe from unwanted emails using Google OAuth and the Gmail API.

## Features
* Sign in with Google and revoke access at any time
* Scan your inbox for newsletters and marketing mail
* Automatically visit unsubscribe links
* Dashboard showing progress and recent activity
* Stateless authentication using JWT tokens

## Screenshots
Screenshots of the dashboard and the unsubscription progress go here.

## Quick Start
```bash
# Clone repo and install dependencies
pip install -r gmail-unsubscriber-backend/requirements.txt

# Copy environment variables
cp .env.example .env

# Run backend and frontend
cd gmail-unsubscriber-backend && python app.py
# in another terminal
cd ../gmail-unsubscriber && python -m http.server 8000
```
Then open `http://localhost:8000` in your browser.

## Google OAuth Setup
1. Create a project in the [Google Cloud Console](https://console.cloud.google.com/).
2. Enable the Gmail API and configure the OAuth consent screen.
3. Create OAuth client credentials for a web application.
4. Set the redirect URI to `http://localhost:5000/oauth2callback` for local development.
5. Fill the values in `.env`.

## Deployment
### Vercel
1. Deploy the `gmail-unsubscriber-backend` directory as a Python serverless function.
2. Set the environment variables from `.env.example` in Vercel settings.
3. Deploy the frontend as a static site and set `VITE_API_URL` to your backend URL.

### Heroku
1. Create a Heroku app and add environment variables.
2. Push the backend code using Git and enable a free Postgres database if desired.
3. Serve the frontend using any static host (Heroku or others).

### Google Cloud Platform
Deploy the backend with Cloud Run or App Engine using the provided `app.yaml`. Set all environment variables via the Cloud console.

### Self‑Hosting
Run the Flask app on any server with Python 3. Install dependencies and configure a reverse proxy like Nginx. Serve the frontend files with any web server.

## API
The backend exposes these endpoints:
- `GET /api/auth/login` – start OAuth flow
- `GET /oauth2callback` – OAuth callback
- `POST /api/auth/logout` – log out
- `GET /api/auth/status` – check token validity
- `GET /api/stats` – current stats
- `GET /api/activities` – recent activities
- `POST /api/unsubscribe/start` – begin scanning
- `GET /api/unsubscribe/status` – polling endpoint

## Troubleshooting
If authentication fails check your OAuth credentials and redirect URIs. For CORS errors ensure the correct backend URL is configured in the frontend.

## License
This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
