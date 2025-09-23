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

#### Two-Step Flow (Recommended)

Gmail Unsubscriber now offers a safer two-step process:

1. **Preview Step**:
   - Click the action button (blue circle with play icon) in the bottom right corner
   - Configure your search parameters:
     - **Search Query**: The query used to find subscription emails
     - **Maximum Emails to Process**: Limit the number of emails to analyze
   - Click "Preview" to scan emails without making changes

2. **Review Candidates**:
   - A preview modal will show all detected subscription emails
   - Each email shows:
     - Sender information
     - Subject line
     - Recommended action (RFC 8058 one-click unsubscribe or label+archive)
   - Select/deselect emails using checkboxes
   - Option to create Gmail filters for auto-archiving future emails

3. **Apply Actions**:
   - Click "Apply Actions" to execute selected unsubscriptions
   - RFC 8058 compliant emails will be unsubscribed via one-click
   - Other emails will be labeled and archived
   - An undo toast appears for reversing label/archive changes

#### Legacy Flow

You can still use the original one-step process by clicking "Start (Legacy)" instead of "Preview"

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

## Undo Functionality

### How Undo Works

After applying unsubscribe actions, you can undo certain changes:

- **Label and Archive Changes**: Can be fully reversed
  - Emails will be moved back to inbox
  - UNSUBSCRIBED label will be removed
  - Created filters will be deleted

- **RFC 8058 One-Click Unsubscribes**: Cannot be undone
  - These are permanent unsubscriptions
  - The system will warn you about this limitation

### Using Undo

1. After applying actions, an undo toast appears
2. Click the "Undo" button within 10 seconds
3. The system will revert all reversible changes
4. A summary will show what was undone

## Privacy & Data Management

### What Data We Store

The application stores minimal data to provide its service:
- Basic statistics (emails scanned, unsubscribed count)
- Recent activity logs (last 50 actions)
- List of domains you've unsubscribed from
- Temporary operation history for undo functionality

### Deleting Your Data

You can delete all app-stored data at any time:
1. This removes all statistics and activity history
2. Your Gmail content is never affected
3. You can continue using the service after deletion

### Data Security

- No email content is permanently stored
- JWT tokens expire automatically
- All data is stored locally in your deployment
- No third-party services receive your data

## Logging Out

To log out of the application:

1. Click the "Logout" button in the top right corner
2. You will be redirected to the login page
3. Your session will be terminated

## Support

If you encounter any issues or have questions, please refer to the documentation or contact support.
