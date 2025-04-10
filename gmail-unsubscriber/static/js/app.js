/**
 * Gmail Unsubscriber - Main Application JavaScript
 * 
 * This script handles:
 * 1. Authentication with Google OAuth
 * 2. Dashboard UI interactions
 * 3. Communication with the backend Python script
 * 4. Real-time progress updates
 */

// Configuration
const API_BASE_URL = 'https://gmail-unsubscriber-backend.vercel.app';

// DOM Elements
const authSection = document.getElementById('auth-section');
const dashboardSection = document.getElementById('dashboard-section');
const userInfo = document.getElementById('user-info');
const userEmail = document.getElementById('user-email');
const authBtn = document.getElementById('auth-btn');
const logoutBtn = document.getElementById('logout-btn');
const actionButton = document.getElementById('action-button');
const runModal = document.getElementById('run-modal');
const processingModal = document.getElementById('processing-modal');
const modalClose = document.getElementById('modal-close');
const cancelRunBtn = document.getElementById('cancel-run');
const startRunBtn = document.getElementById('start-run');
const stopProcessingBtn = document.getElementById('stop-processing');
const activityList = document.getElementById('activity-list');
const activityPlaceholder = document.getElementById('activity-placeholder');

// Dashboard Stats Elements
const totalScanned = document.getElementById('total-scanned');
const totalUnsubscribed = document.getElementById('total-unsubscribed');
const timeSaved = document.getElementById('time-saved');
const progressBar = document.getElementById('progress-bar');
const progressPercentage = document.getElementById('progress-percentage');
const emailsProcessed = document.getElementById('emails-processed');
const emailsRemaining = document.getElementById('emails-remaining');
const processingProgressBar = document.getElementById('processing-progress-bar');
const processingStatus = document.getElementById('processing-status');
const processingCount = document.getElementById('processing-count');

// State variables
let isProcessing = false;
let processedEmails = 0;
let totalEmailsToProcess = 0;
let statusCheckInterval = null;

// Initialize the application
function initApp() {
    // Check if user is already authenticated
    checkAuthStatus();
    
    // Set up event listeners
    setupEventListeners();
    
    // Check for auth callback
    checkAuthCallback();
}

// Check if this is a callback from authentication
function checkAuthCallback() {
    const urlParams = new URLSearchParams(window.location.search);
    const authStatus = urlParams.get('auth');
    const email = urlParams.get('email');
    
    if (authStatus === 'success' && email) {
        // Clear URL parameters
        window.history.replaceState({}, document.title, window.location.pathname);
        
        // Update UI
        userEmail.textContent = email;
        showDashboard();
        
        // Load user data
        loadUserData();
    }
}

// Check if user is authenticated
function checkAuthStatus() {
    fetch(`${API_BASE_URL}/api/auth/status`, {
        method: 'GET',
        credentials: 'include'
    })
    .then(response => response.json())
    .then(data => {
        if (data.authenticated) {
            userEmail.textContent = data.email;
            showDashboard();
            loadUserData();
        } else {
            showAuthScreen();
        }
    })
    .catch(error => {
        console.error('Error checking auth status:', error);
        showAuthScreen();
    });
}

// Set up all event listeners
function setupEventListeners() {
    // Auth button click
    authBtn.addEventListener('click', handleAuth);
    
    // Logout button click
    logoutBtn.addEventListener('click', handleLogout);
    
    // Action button click (to open run modal)
    actionButton.addEventListener('click', () => {
        runModal.classList.add('active');
    });
    
    // Modal close button
    modalClose.addEventListener('click', () => {
        runModal.classList.remove('active');
    });
    
    // Cancel run button
    cancelRunBtn.addEventListener('click', () => {
        runModal.classList.remove('active');
    });
    
    // Start run button
    startRunBtn.addEventListener('click', startUnsubscriptionProcess);
    
    // Stop processing button
    stopProcessingBtn.addEventListener('click', stopUnsubscriptionProcess);
}

// Handle authentication with Google
function handleAuth() {
    // Show a loading state
    authBtn.innerHTML = '<div class="spinner" style="width: 20px; height: 20px; margin: 0;"></div>';
    authBtn.disabled = true;
    
    // Get auth URL from backend
    fetch(`${API_BASE_URL}/api/auth/login`)
        .then(response => response.json())
        .then(data => {
            // Redirect to Google OAuth
            window.location.href = data.auth_url;
        })
        .catch(error => {
            console.error('Error starting authentication:', error);
            
            // Reset auth button
            authBtn.innerHTML = '<img src="https://upload.wikimedia.org/wikipedia/commons/5/53/Google_%22G%22_Logo.svg" alt="Google Logo"> Sign in with Google';
            authBtn.disabled = false;
            
            alert('Failed to start authentication. Please try again.');
        });
}

// Handle user logout
function handleLogout() {
    fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: 'POST',
        credentials: 'include'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAuthScreen();
        }
    })
    .catch(error => {
        console.error('Error logging out:', error);
    });
}

// Show the dashboard
function showDashboard() {
    authSection.classList.add('hidden');
    dashboardSection.classList.remove('hidden');
    userInfo.classList.remove('hidden');
    actionButton.classList.remove('hidden');
}

// Show the auth screen
function showAuthScreen() {
    dashboardSection.classList.add('hidden');
    userInfo.classList.add('hidden');
    actionButton.classList.add('hidden');
    authSection.classList.remove('hidden');
}

// Load user data (stats and activities)
function loadUserData() {
    // Load stats
    fetch(`${API_BASE_URL}/api/stats`, {
        method: 'GET',
        credentials: 'include'
    })
    .then(response => response.json())
    .then(data => {
        updateStatsUI(data);
    })
    .catch(error => {
        console.error('Error loading stats:', error);
    });
    
    // Load activities
    fetch(`${API_BASE_URL}/api/activities`, {
        method: 'GET',
        credentials: 'include'
    })
    .then(response => response.json())
    .then(activities => {
        updateActivitiesUI(activities);
    })
    .catch(error => {
        console.error('Error loading activities:', error);
    });
}

// Update stats UI
function updateStatsUI(stats) {
    totalScanned.textContent = stats.total_scanned || 0;
    totalUnsubscribed.textContent = stats.total_unsubscribed || 0;
    timeSaved.textContent = stats.time_saved || 0;
    
    // Update progress bar
    const progress = stats.total_scanned > 0 
        ? Math.round((stats.total_unsubscribed / stats.total_scanned) * 100) 
        : 0;
    
    progressBar.style.width = `${progress}%`;
    progressPercentage.textContent = `${progress}%`;
    
    // Update emails processed/remaining
    emailsProcessed.textContent = `${stats.total_scanned || 0} processed`;
    emailsRemaining.textContent = `${Math.max(0, processedEmails - (stats.total_scanned || 0))} remaining`;
}

// Update activities UI
function updateActivitiesUI(activities) {
    // Clear existing activities except placeholder
    if (activityPlaceholder) {
        activityPlaceholder.remove();
    }
    
    // Clear existing activities
    while (activityList.firstChild) {
        activityList.removeChild(activityList.firstChild);
    }
    
    // Add activities to the list
    activities.forEach(activity => {
        const activityItem = createActivityElement(activity);
        activityList.appendChild(activityItem);
    });
}

// Create an activity element
function createActivityElement(activity) {
    const activityItem = document.createElement('div');
    activityItem.className = 'activity-item';
    
    // Determine icon class based on activity type
    let iconClass = 'fas fa-info-circle';
    let iconColorClass = '';
    
    switch (activity.type) {
        case 'success':
            iconClass = 'fas fa-check-circle';
            iconColorClass = 'success';
            break;
        case 'warning':
            iconClass = 'fas fa-exclamation-triangle';
            iconColorClass = 'warning';
            break;
        case 'error':
            iconClass = 'fas fa-times-circle';
            iconColorClass = 'error';
            break;
    }
    
    // Format time
    const timeString = formatTime(new Date(activity.time));
    
    // Create HTML
    activityItem.innerHTML = `
        <div class="activity-icon ${iconColorClass}">
            <i class="${iconClass}"></i>
        </div>
        <div class="activity-details">
            <div class="activity-message">${activity.message}</div>
            <div class="activity-time">${timeString}</div>
        </div>
    `;
    
    return activityItem;
}

// Format time for activity display
function formatTime(time) {
    const date = new Date(time);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.round(diffMs / 1000);
    const diffMin = Math.round(diffSec / 60);
    const diffHour = Math.round(diffMin / 60);
    
    if (diffSec < 60) {
        return 'Just now';
    } else if (diffMin < 60) {
        return `${diffMin} minute${diffMin !== 1 ? 's' : ''} ago`;
    } else if (diffHour < 24) {
        return `${diffHour} hour${diffHour !== 1 ? 's' : ''} ago`;
    } else {
        return date.toLocaleString();
    }
}

// Start the unsubscription process
function startUnsubscriptionProcess() {
    // Get values from form
    const searchQuery = document.getElementById('search-query').value;
    const maxEmails = parseInt(document.getElementById('max-emails').value, 10);
    
    // Validate
    if (!searchQuery || isNaN(maxEmails) || maxEmails < 1) {
        alert('Please enter valid values for all fields.');
        return;
    }
    
    // Close run modal and show processing modal
    runModal.classList.remove('active');
    processingModal.classList.add('active');
    
    // Set processing state
    isProcessing = true;
    processedEmails = 0;
    totalEmailsToProcess = maxEmails;
    
    // Update UI
    processingStatus.textContent = 'Starting unsubscription process...';
    processingCount.textContent = `Processed: 0 / ${maxEmails}`;
    processingProgressBar.style.width = '0%';
    
    // Call backend API
    fetch(`${API_BASE_URL}/api/unsubscribe/start`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
            search_query: searchQuery,
            max_emails: maxEmails
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Start polling for status updates
            startStatusPolling();
        } else {
            throw new Error(data.error || 'Failed to start unsubscription process');
        }
    })
    .catch(error => {
        console.error('Error starting unsubscription process:', error);
        processingStatus.textContent = `Error: ${error.message}`;
        
        // Stop processing after a delay
        setTimeout(() => {
            stopUnsubscriptionProcess();
        }, 3000);
    });
}

// Start polling for status updates
function startStatusPolling() {
    // Clear any existing interval
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }
    
    // Set up polling interval
    statusCheckInterval = setInterval(() => {
        if (!isProcessing) {
            clearInterval(statusCheckInterval);
            return;
        }
        
        // Call status API
        fetch(`${API_BASE_URL}/api/unsubscribe/status`, {
            method: 'GET',
            credentials: 'include'
        })
        .then(response => response.json())
        .then(data => {
            // Update stats
            updateStatsUI(data.stats);
            
            // Update activities
            updateActivitiesUI(data.activities);
            
            // Update progress
            const processed = data.stats.total_scanned || 0;
            processedEmails = processed;
            
            // Calculate progress percentage
            const progress = totalEmailsToProcess > 0 
                ? Math.round((processed / totalEmailsToProcess) * 100) 
                : 0;
            
            processingProgressBar.style.width = `${Math.min(progress, 100)}%`;
            processingCount.textContent = `Processed: ${processed} / ${totalEmailsToProcess}`;
            
            // Check if process is complete
            if (data.status === 'completed' || processed >= totalEmailsToProcess) {
                finishUnsubscriptionProcess();
            }
        })
        .catch(error => {
            console.error('Error checking status:', error);
        });
    }, 2000); // Poll every 2 seconds
}

// Stop the unsubscription process
function stopUnsubscriptionProcess() {
    if (!isProcessing) return;
    
    // Set processing state
    isProcessing = false;
    
    // Clear polling interval
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        statusCheckInterval = null;
    }
    
    // Close processing modal
    processingModal.classList.remove('active');
}

// Finish the unsubscription process
function finishUnsubscriptionProcess() {
    // Set processing state
    isProcessing = false;
    
    // Clear polling interval
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        statusCheckInterval = null;
    }
    
    // Close processing modal
    processingModal.classList.remove('active');
    
    // Reload user data to ensure we have the latest stats
    loadUserData();
    
    // Show completion message
    fetch(`${API_BASE_URL}/api/stats`, {
        method: 'GET',
        credentials: 'include'
    })
    .then(response => response.json())
    .then(stats => {
        alert(`Unsubscription process completed!\n\nProcessed: ${stats.total_scanned || 0} emails\nUnsubscribed: ${stats.total_unsubscribed || 0} emails\nTime saved: ${stats.time_saved || 0} minutes`);
    })
    .catch(error => {
        console.error('Error loading final stats:', error);
        alert('Unsubscription process completed!');
    });
}

// Initialize the app when the DOM is loaded
document.addEventListener('DOMContentLoaded', initApp);
