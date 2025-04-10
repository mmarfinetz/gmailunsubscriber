# Gmail Unsubscriber - Setup Guide

This guide will help you set up and run the Gmail Unsubscriber application, which allows you to automatically unsubscribe from unwanted emails.

## Prerequisites

- Python 3.6+
- Google account
- Google Cloud Platform account (for OAuth credentials)

## Setting Up Google OAuth Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Navigate to "APIs & Services" > "OAuth consent screen"
4. Configure the OAuth consent screen:
   - User Type: External
   - App name: Gmail Unsubscriber
   - User support email: Your email
   - Developer contact information: Your email
   - Authorized domains: Your domain (if applicable)
5. Add scopes:
   - `https://www.googleapis.com/auth/gmail.modify`
6. Add test users (your Gmail account)
7. Navigate to "APIs & Services" > "Credentials"
8. Click "Create Credentials" > "OAuth client ID"
9. Application type: Web application
10. Name: Gmail Unsubscriber
11. Authorized JavaScript origins: `http://localhost:5000`
12. Authorized redirect URIs: `http://localhost:5000/oauth2callback`
13. Click "Create"
14. Download the JSON file

## Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install flask flask-cors google-auth google-auth-oauthlib google-api-python-client requests beautifulsoup4 python-dotenv
   ```
3. Create a `.env` file in the project root with the following content:
   ```
   SECRET_KEY=your_secret_key_here
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   GOOGLE_PROJECT_ID=your_google_project_id
   REDIRECT_URI=http://localhost:5000/oauth2callback
   FRONTEND_URL=http://localhost:8000
   ```
4. Replace the placeholder values with your actual Google OAuth credentials

## Running the Application

1. Start the backend server:
   ```
   cd gmail-unsubscriber-backend
   python app.py
   ```
2. Start the frontend server:
   ```
   cd gmail-unsubscriber
   python -m http.server 8000
   ```
3. Open your browser and navigate to `http://localhost:8000`

## Usage

1. Click "Sign in with Google" to authenticate with your Gmail account
2. Once authenticated, you'll see your dashboard
3. Click the action button (bottom right) to start the unsubscription process
4. Configure the search query and maximum emails to process
5. Click "Start" to begin the unsubscription process
6. Monitor the progress in real-time on your dashboard

## Security Considerations

- The application requires access to your Gmail account to function
- It only accesses emails matching the search query
- It only performs unsubscription actions on links explicitly labeled as unsubscribe links
- Your credentials are stored securely and not shared with any third parties

## Troubleshooting

- If authentication fails, ensure your OAuth credentials are correctly configured
- If no emails are found, try adjusting the search query
- If unsubscription fails for specific emails, they may not have standard unsubscribe links

## API Documentation

The backend provides the following API endpoints:

- `GET /api/auth/login`: Initiates the OAuth2 authorization flow
- `GET /oauth2callback`: Handles the OAuth2 callback from Google
- `POST /api/auth/logout`: Logs out the user
- `GET /api/auth/status`: Checks if the user is authenticated
- `GET /api/stats`: Gets the user's unsubscription statistics
- `GET /api/activities`: Gets the user's recent activities
- `POST /api/unsubscribe/start`: Starts the unsubscription process
- `GET /api/unsubscribe/status`: Gets the status of the unsubscription process
