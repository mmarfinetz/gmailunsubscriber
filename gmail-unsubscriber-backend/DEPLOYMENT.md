# Gmail Unsubscriber - Deployment Guide

This guide provides instructions for deploying the Gmail Unsubscriber application to various cloud platforms.

## Prerequisites

- Completed local setup and testing
- Google OAuth credentials
- Account on your chosen cloud platform

## Frontend Deployment

The frontend is a static website that can be deployed to any static hosting service.

### Option 1: Deploy to GitHub Pages

1. Create a GitHub repository
2. Push the frontend code to the repository
3. Enable GitHub Pages in the repository settings
4. Set the source to the branch containing your code

### Option 2: Deploy to Netlify

1. Create a Netlify account
2. Connect your GitHub repository or upload the frontend files
3. Configure the build settings (not required for this static site)
4. Deploy the site

### Option 3: Deploy to Firebase Hosting

1. Install Firebase CLI: `npm install -g firebase-tools`
2. Login to Firebase: `firebase login`
3. Initialize your project: `firebase init`
4. Select "Hosting" and follow the prompts
5. Deploy: `firebase deploy`

## Backend Deployment

The backend is a Flask application that can be deployed to various platforms.

### Option 1: Deploy to Heroku

1. Create a Heroku account
2. Install Heroku CLI
3. Login to Heroku: `heroku login`
4. Create a new Heroku app: `heroku create gmail-unsubscriber-backend`
5. Set environment variables:
   ```
   heroku config:set SECRET_KEY=your_secret_key_here
   heroku config:set GOOGLE_CLIENT_ID=your_google_client_id
   heroku config:set GOOGLE_CLIENT_SECRET=your_google_client_secret
   heroku config:set GOOGLE_PROJECT_ID=your_google_project_id
   heroku config:set REDIRECT_URI=https://your-app-name.herokuapp.com/oauth2callback
   heroku config:set FRONTEND_URL=https://your-frontend-url
   ```
6. Deploy the app:
   ```
   git init
   git add .
   git commit -m "Initial commit"
   git push heroku master
   ```

### Option 2: Deploy to Google App Engine

1. Create a Google Cloud account
2. Install Google Cloud SDK
3. Initialize the SDK: `gcloud init`
4. Update the `app.yaml` file with your environment variables
5. Deploy the app: `gcloud app deploy`

### Option 3: Deploy to AWS Elastic Beanstalk

1. Create an AWS account
2. Install AWS CLI and EB CLI
3. Initialize EB: `eb init`
4. Create an environment: `eb create gmail-unsubscriber-env`
5. Set environment variables:
   ```
   eb setenv SECRET_KEY=your_secret_key_here GOOGLE_CLIENT_ID=your_google_client_id GOOGLE_CLIENT_SECRET=your_google_client_secret GOOGLE_PROJECT_ID=your_google_project_id REDIRECT_URI=https://your-aws-url.elasticbeanstalk.com/oauth2callback FRONTEND_URL=https://your-frontend-url
   ```
6. Deploy: `eb deploy`

## Connecting Frontend to Backend

After deploying both the frontend and backend, you need to update the frontend to connect to the deployed backend:

1. Open the `app.js` file in the frontend code
2. Update the `API_BASE_URL` variable to point to your deployed backend:
   ```javascript
   const API_BASE_URL = 'https://your-backend-url';
   ```
3. Redeploy the frontend

## Updating Google OAuth Credentials

After deployment, you need to update your Google OAuth credentials:

1. Go to the Google Cloud Console
2. Navigate to "APIs & Services" > "Credentials"
3. Edit your OAuth client
4. Add your deployed URLs to the authorized JavaScript origins and redirect URIs:
   - Authorized JavaScript origins: `https://your-frontend-url`
   - Authorized redirect URIs: `https://your-backend-url/oauth2callback`

## Monitoring and Maintenance

- Set up logging and monitoring for your deployed application
- Regularly check for security updates to dependencies
- Monitor usage and scale resources as needed

## Troubleshooting

- If authentication fails, check that your OAuth credentials are correctly configured
- If CORS errors occur, ensure your backend CORS settings include your frontend URL
- If the backend can't connect to Gmail API, check your Google Cloud project settings
