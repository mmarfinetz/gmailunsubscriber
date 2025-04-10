# Gmail Unsubscriber - User Guide

Welcome to Gmail Unsubscriber, an application that helps you automatically unsubscribe from unwanted emails in your Gmail inbox.

## Overview

Gmail Unsubscriber scans your inbox for subscription emails and automatically processes unsubscription links, saving you time and keeping your inbox clean.

## Getting Started

### Installation

Follow the installation instructions in the README.md file to set up the application.

### Authentication

1. Open the application in your web browser
2. Click the "Sign in with Google" button
3. You will be redirected to Google's authentication page
4. Grant the necessary permissions to allow the application to access your Gmail account
5. After successful authentication, you will be redirected to the dashboard

## Using the Dashboard

### Dashboard Overview

The dashboard provides an overview of your unsubscription progress and statistics:

- **Total Emails Scanned**: The number of emails that have been analyzed
- **Successfully Unsubscribed**: The number of emails you've successfully unsubscribed from
- **Time Saved**: An estimate of the time saved by using the automated process

### Starting the Unsubscription Process

1. Click the action button (blue circle with play icon) in the bottom right corner
2. Configure the unsubscription process:
   - **Search Query**: The query used to find subscription emails (default should work for most users)
   - **Maximum Emails to Process**: Limit the number of emails to process in one run
3. Click "Start" to begin the process

### Monitoring Progress

During the unsubscription process:

1. A progress modal will show the current status
2. The progress bar indicates the percentage of emails processed
3. You can stop the process at any time by clicking "Stop"
4. The dashboard will update in real-time with statistics and activities

### Activity Log

The activity log shows recent actions taken by the application:

- Green checkmarks indicate successful unsubscriptions
- Yellow triangles indicate warnings
- Red circles indicate errors or failed unsubscription attempts

## Privacy and Security

- The application only accesses emails matching your search query
- It only performs unsubscription actions on links explicitly labeled as unsubscribe links
- Your credentials are stored securely and not shared with any third parties
- The application uses OAuth2 for secure authentication with Google

## Best Practices

- Start with a small batch of emails (20-50) to test the process
- Review the activity log to see which unsubscriptions were successful
- Run the process periodically to keep your inbox clean
- Adjust the search query if you're not finding specific subscription emails

## Troubleshooting

### Authentication Issues

- If you encounter authentication errors, try signing out and signing in again
- Ensure you've granted all the necessary permissions
- Check that your Google account doesn't have any security restrictions

### No Emails Found

- Try adjusting the search query to be more inclusive
- Check your Gmail filters to ensure subscription emails aren't being automatically archived

### Failed Unsubscriptions

Some emails may fail to unsubscribe for various reasons:

- The email doesn't contain a standard unsubscribe link
- The unsubscribe process requires additional steps (like filling out a form)
- The unsubscribe link has expired

For these cases, you may need to manually unsubscribe.

## Logging Out

To log out of the application:

1. Click the "Logout" button in the top right corner
2. You will be redirected to the login page
3. Your session will be terminated

## Support

If you encounter any issues or have questions, please refer to the documentation or contact support.
