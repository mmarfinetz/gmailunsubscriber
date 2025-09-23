# Gmail Unsubscriber

Gmail Unsubscriber helps you automatically unsubscribe from unwanted emails using Google OAuth and the Gmail API.

## Features
* Sign in with Google and revoke access at any time
* Two-step unsubscribe flow: Preview candidates, then apply actions
* RFC 8058 one-click unsubscribe support for compatible senders
* Automatic labeling and archiving as fallback
* Create Gmail filters to auto-archive future emails from unsubscribed senders
* Undo functionality for label/archive changes
* Dashboard showing progress and recent activity
* Stateless authentication using JWT tokens
* Privacy-focused: Delete all app-stored data at any time

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

### Basic Setup
1. Create a project in the [Google Cloud Console](https://console.cloud.google.com/).
2. Enable the Gmail API and configure the OAuth consent screen.
3. Create OAuth client credentials for a web application.
4. Set the redirect URI to `http://localhost:5000/oauth2callback` for local development.
5. Fill the values in `.env`.

### OAuth Scopes (Least Privilege)
This application requests only the minimum scopes necessary:
- `https://www.googleapis.com/auth/gmail.modify` - To read emails and modify labels
- `https://www.googleapis.com/auth/gmail.settings.basic` - To create filters for auto-archiving
- `https://www.googleapis.com/auth/userinfo.email` - To identify the user

### OAuth Verification (Production)
To remove the "This app isn't verified" warning and serve more than 100 users:
1. Fill out the [OAuth Verification Form](https://support.google.com/cloud/answer/7454865)
2. Provide your privacy policy URL
3. Explain how each scope is used (see above)
4. Submit for Google's review (typically 3-5 business days)
5. Once approved, the warning will be removed for all users

Note: Verification is only needed for production deployments serving external users.

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
- `POST /api/unsubscribe/preview` – preview candidates without changes
- `POST /api/unsubscribe/apply` – apply selected actions
- `POST /api/unsubscribe/undo` – undo label/archive changes
- `DELETE /api/user/data` – delete all app-stored data
- `POST /api/unsubscribe/start` – begin scanning (legacy)
- `GET /api/unsubscribe/status` – polling endpoint

For detailed API documentation, see [API_DOCS.md](gmail-unsubscriber-backend/API_DOCS.md).

## Privacy & Data Deletion

### What We Store
The application stores minimal data locally:
- **User Statistics**: Total emails scanned, unsubscribed count, time saved
- **Activity Logs**: Recent actions performed (last 50 entries)
- **Domain Data**: List of domains you've unsubscribed from
- **Operations History**: For undo functionality (temporary)

### What We DON'T Store
- Email content or attachments
- Personal information beyond your email address
- Passwords or authentication tokens (JWT tokens expire)
- Any data on external servers

### Data Deletion
You can delete all app-stored data at any time:
1. Use the API endpoint: `DELETE /api/user/data`
2. Or implement a "Delete My Data" button in the UI
3. This removes all statistics, activities, and operation history
4. Note: This does NOT affect your Gmail content

## Troubleshooting
If authentication fails check your OAuth credentials and redirect URIs. For CORS errors ensure the correct backend URL is configured in the frontend.

## License
This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
