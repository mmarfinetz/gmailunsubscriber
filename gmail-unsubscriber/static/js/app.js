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
const API_BASE_URL = window.VITE_API_URL || window.NEXT_PUBLIC_API_BASE_URL || 
    (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.hostname === '::1' || window.location.hostname.match(/^\[.*\]$/) ? 
        'http://localhost:5000' : 'https://gmailunsubscriber-production.up.railway.app');

// DOM Elements
const authSection = document.getElementById('auth-section');
const dashboardSection = document.getElementById('dashboard-section');
const userInfo = document.getElementById('user-info');
const userEmail = document.getElementById('user-email');
const authBtn = document.getElementById('auth-btn');
const logoutBtn = document.getElementById('logout-btn');
const actionButton = document.getElementById('action-button');
const runModal = document.getElementById('run-modal');
const modalClose = document.getElementById('modal-close');
const cancelRunBtn = document.getElementById('cancel-run');
const startRunBtn = document.getElementById('start-run');
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

// State variables
let isProcessing = false;
let processedEmails = 0;
let totalEmailsToProcess = 0;
let statusCheckInterval = null;
let currentProcessingStatus = 'idle';

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
    const token = urlParams.get('token');
    const error = urlParams.get('error');
    const details = urlParams.get('details');

    console.log('=== OAuth Callback Check ===');

    if (authStatus === 'error') {
        console.error('OAuth authentication failed:', error, details);
        alert(`Authentication failed: ${error}\n${details ? `Details: ${details}` : ''}`);
        return;
    }

    if (authStatus === 'success' && email && token) {
        console.log('OAuth authentication successful');
        console.log('Email:', email);
        console.log('Token length:', token.length);
        
        // Clear URL parameters
        window.history.replaceState({}, document.title, window.location.pathname);

        // Update UI
        userEmail.textContent = email;
        localStorage.setItem('auth_token', token);
        console.log('Token stored in localStorage');
        
        showDashboard();

        // Load user data
        loadUserData();
        
        // Debug auth state after successful login
        debugAuthState();
    }
}

// Check if user is authenticated
function checkAuthStatus() {
    console.log('=== Checking Auth Status ===');
    const token = localStorage.getItem('auth_token');
    console.log('Token present:', !!token);
    
    fetch(`${API_BASE_URL}/api/auth/status`, {
        method: 'GET',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        credentials: 'include'
    })
    .then(response => {
        console.log('Auth check response status:', response.status);
        return response.json();
    })
    .then(data => {
        if (data.authenticated) {
            userEmail.textContent = data.email;
            showDashboard();
            loadUserData();
        } else {
            console.log('User not authenticated, showing auth screen');
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
}


// Handle authentication with Google
function handleAuth() {
    // Show a loading state
    authBtn.innerHTML = '<div class="spinner" style="width: 20px; height: 20px; margin: 0;"></div>';
    authBtn.disabled = true;
    
    // Get auth URL from backend
    fetch(`${API_BASE_URL}/api/auth/login`, {
        credentials: 'include',  // Important: Include cookies for session management
        headers: {
            'Content-Type': 'application/json'
        }
    })
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
    const token = localStorage.getItem('auth_token');
    fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: 'POST',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        credentials: 'include'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            localStorage.removeItem('auth_token');
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
    const token = localStorage.getItem('auth_token');
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
    fetch(`${API_BASE_URL}/api/stats`, {
        method: 'GET',
        headers,
        credentials: 'include'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        updateStatsUI(data);
    })
    .catch(error => {
        console.error('Error loading stats:', error);
        // Show default stats on error
        updateStatsUI({
            total_scanned: 0,
            total_unsubscribed: 0,
            time_saved: 0
        });
    });
    
    // Load activities
    fetch(`${API_BASE_URL}/api/activities`, {
        method: 'GET',
        headers,
        credentials: 'include'
    })
    .then(response => response.json())
    .then(activities => {
        updateActivitiesUI(activities);
    })
    .catch(error => {
        console.error('Error loading activities:', error);
    });
    
    // Load unsubscribed services
    fetch(`${API_BASE_URL}/api/unsubscribed-services`, {
        method: 'GET',
        headers,
        credentials: 'include'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(services => {
        console.log('Services data:', services);
        updateServicesUI(services);
    })
    .catch(error => {
        console.error('Error loading unsubscribed services:', error);
        // Show empty services on error
        updateServicesUI([]);
    });
}

// Update stats UI
function updateStatsUI(stats) {
    totalScanned.textContent = stats.total_scanned || 0;
    totalUnsubscribed.textContent = stats.total_unsubscribed || 0;
    timeSaved.textContent = stats.time_saved || 0;
    
    // Update progress bar based on processing state
    let progress = 0;
    if (isProcessing && totalEmailsToProcess > 0) {
        // During processing, show progress based on emails processed vs total to process
        progress = Math.round(((stats.total_scanned || 0) / totalEmailsToProcess) * 100);
    } else if (stats.total_scanned > 0) {
        // When not processing, show unsubscribe success rate
        progress = Math.round((stats.total_unsubscribed / stats.total_scanned) * 100);
    }
    
    progressBar.style.width = `${Math.min(progress, 100)}%`;
    progressPercentage.textContent = `${Math.min(progress, 100)}%`;
    
    // Update emails processed/remaining
    if (isProcessing && totalEmailsToProcess > 0) {
        const remaining = Math.max(0, totalEmailsToProcess - (stats.total_scanned || 0));
        emailsProcessed.textContent = `${stats.total_scanned || 0} processed`;
        emailsRemaining.textContent = `${remaining} remaining`;
        
        // Update processing status in progress header
        const progressHeader = document.querySelector('.progress-header h3');
        if (progressHeader) {
            progressHeader.textContent = `Processing Progress - ${currentProcessingStatus}`;
        }
    } else {
        emailsProcessed.textContent = `${stats.total_scanned || 0} processed`;
        emailsRemaining.textContent = `0 remaining`;
        
        // Reset progress header
        const progressHeader = document.querySelector('.progress-header h3');
        if (progressHeader) {
            progressHeader.textContent = 'Unsubscription Progress';
        }
    }
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
    
    // Track failed unsubscribe attempts
    const failedServices = [];
    
    // Add activities to the list
    activities.forEach(activity => {
        const activityItem = createActivityElement(activity);
        activityList.appendChild(activityItem);
        
        // Check if this is a failed unsubscribe attempt
        if (activity.type === 'error' && 
            (activity.message.includes('Failed to unsubscribe from') || 
             activity.message.includes('Non-200 status') ||
             activity.message.includes('No unsubscribe links found'))) {
            
            // Extract service information from the message
            let serviceName = '';
            
            // Try to extract service name from different message formats
            if (activity.message.includes('Failed to unsubscribe from')) {
                const match = activity.message.match(/Failed to unsubscribe from (.+?) \(/);
                serviceName = match ? match[1] : '';
            } else if (activity.message.includes('from email')) {
                // Handle "No unsubscribe links found in email X/Y from ServiceName"
                const match = activity.message.match(/from (.+)$/);
                serviceName = match ? match[1] : '';
            }
            
            // If we still don't have a service name, try to extract domain from metadata
            if (!serviceName && activity.metadata && activity.metadata.domain) {
                serviceName = activity.metadata.domain;
            }
            
            if (serviceName) {
                failedServices.push({
                    service: serviceName,
                    message: activity.message,
                    time: activity.time
                });
            }
        }
    });
    
    // Store failed services in localStorage for the manual unsubscribe page
    localStorage.setItem('failedUnsubscribeServices', JSON.stringify(failedServices));
    
    // Update the manual unsubscribe link visibility
    updateManualUnsubscribeVisibility(failedServices.length > 0);
}

// Update manual unsubscribe section visibility
function updateManualUnsubscribeVisibility(hasFailedServices) {
    const manualUnsubscribeSection = document.querySelector('.manual-unsubscribe-section');
    if (manualUnsubscribeSection) {
        if (hasFailedServices) {
            manualUnsubscribeSection.style.display = 'block';
            
            // Update the count in the message
            const failedCount = JSON.parse(localStorage.getItem('failedUnsubscribeServices') || '[]').length;
            const messageElement = manualUnsubscribeSection.querySelector('.info-content p');
            if (messageElement) {
                messageElement.innerHTML = `Some services (${failedCount}) require manual unsubscription. Visit our <a href="manual_unsubscribe.html" target="_blank">manual unsubscribe guide</a> to complete the process.`;
            }
        } else {
            manualUnsubscribeSection.style.display = 'none';
        }
    }
}

// Update unsubscribed services UI
function updateServicesUI(services) {
    console.log('=== updateServicesUI called ===');
    console.log('Services data:', services);
    
    const servicesSection = document.getElementById('services-section');
    const servicesGrid = document.getElementById('services-grid');
    const servicesCount = document.getElementById('services-count');
    
    // Ensure we have the DOM elements
    if (!servicesSection || !servicesGrid || !servicesCount) {
        console.error('Missing DOM elements for services section');
        return;
    }
    
    console.log('DOM elements found successfully');
    
    // Force clear any existing content that might be causing issues
    servicesGrid.innerHTML = '';
    
    // Also clear the entire services section and rebuild it to ensure no interference
    const servicesContainer = servicesSection.parentElement;
    const newServicesSection = document.createElement('div');
    newServicesSection.className = 'services-section';
    newServicesSection.id = 'services-section';
    newServicesSection.style.display = 'block';
    
    // Show section if we have services
    if (services && services.length > 0) {
        console.log('Processing', services.length, 'services');
        
        // Create the section header
        const header = document.createElement('div');
        header.className = 'services-header';
        header.innerHTML = `
            <h3>Unsubscribed Services</h3>
            <span class="services-count">${services.length} service${services.length !== 1 ? 's' : ''}</span>
        `;
        newServicesSection.appendChild(header);
        
        // Create the grid container
        const grid = document.createElement('div');
        grid.className = 'services-grid';
        grid.id = 'services-grid';
        
        // Add service cards
        services.forEach((service, index) => {
            console.log(`Creating service card ${index}:`, service);
            const serviceCard = createServiceCard(service);
            console.log('Service card HTML:', serviceCard.outerHTML);
            grid.appendChild(serviceCard);
        });
        
        newServicesSection.appendChild(grid);
        
        // Replace the old section with the new one
        servicesContainer.replaceChild(newServicesSection, servicesSection);
        
        console.log('Services section rebuilt successfully');
    } else {
        console.log('No services to display, hiding section');
        newServicesSection.style.display = 'none';
    }
}

// Create a service card element
function createServiceCard(service) {
    console.log('Creating service card for:', service);
    
    // Validate service data
    if (!service || typeof service !== 'object') {
        console.error('Invalid service data:', service);
        return document.createElement('div');
    }
    
    const card = document.createElement('div');
    card.className = 'service-card';
    
    // Get first letter of domain for icon
    const senderName = service.sender_name || service.domain || 'Unknown';
    const domain = service.domain || 'unknown.com';
    const firstLetter = senderName.charAt(0).toUpperCase();
    
    // Format email list
    const emails = service.emails || [];
    const emailsList = emails.length > 0 ? 
        emails.slice(0, 3).map(email => 
            `<div class="service-email">${email}</div>`
        ).join('') : '<div class="service-email">No emails available</div>';
    
    const moreEmails = emails.length > 3 ? 
        `<div class="service-email-more">+${emails.length - 3} more</div>` : '';
    
    const count = service.count || 0;
    
    card.innerHTML = `
        <div class="service-icon">${firstLetter}</div>
        <div class="service-info">
            <div class="service-name">${senderName}</div>
            <div class="service-domain">${domain}</div>
            <div class="service-emails">
                ${emailsList}
                ${moreEmails}
            </div>
            <div class="service-stats">
                <span class="service-count">${count} email${count !== 1 ? 's' : ''}</span>
            </div>
        </div>
    `;
    
    console.log('Service card created successfully');
    return card;
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
    
    // Check if we have metadata for enhanced display
    let messageContent = activity.message;
    let domainBadge = '';
    
    if (activity.metadata && activity.metadata.domain) {
        // Create a domain badge
        domainBadge = `<span class="domain-badge">${activity.metadata.domain}</span>`;
    }
    
    // Create HTML
    activityItem.innerHTML = `
        <div class="activity-icon ${iconColorClass}">
            <i class="${iconClass}"></i>
        </div>
        <div class="activity-details">
            <div class="activity-message">
                ${messageContent}
                ${domainBadge}
            </div>
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
    
    // Clear previous failed services when starting new process
    localStorage.removeItem('failedUnsubscribeServices');
    updateManualUnsubscribeVisibility(false);
    
    // Close run modal
    runModal.classList.remove('active');
    
    // Set processing state
    isProcessing = true;
    processedEmails = 0;
    totalEmailsToProcess = maxEmails;
    currentProcessingStatus = 'Starting unsubscription process...';
    
    // Update dashboard immediately to show processing state
    updateStatsUI({
        total_scanned: 0,
        total_unsubscribed: 0,
        time_saved: 0
    });
    
    // Start polling immediately since backend is now async
    startStatusPolling();
    
    // Call backend API
    const token = localStorage.getItem('auth_token');
    fetch(`${API_BASE_URL}/api/unsubscribe/start`, {
        method: 'POST',
        headers: Object.assign({
            'Content-Type': 'application/json'
        }, token ? { 'Authorization': `Bearer ${token}` } : {}),
        credentials: 'include',
        body: JSON.stringify({
            search_query: searchQuery,
            max_emails: maxEmails
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Unsubscription process started successfully');
            // Polling already started above
            
            // If stats are included in response, update immediately
            if (data.stats) {
                console.log('Updating stats from response:', data.stats);
                updateStatsUI(data.stats);
            }
            
            // Also do a full data refresh to get activities and services
            console.log('Refreshing all user data after process completion');
            loadUserData();
        } else {
            throw new Error(data.error || 'Failed to start unsubscription process');
        }
    })
    .catch(error => {
        console.error('Error starting unsubscription process:', error);
        currentProcessingStatus = `Error: ${error.message}`;
        
        // Update dashboard to show error
        updateStatsUI({
            total_scanned: 0,
            total_unsubscribed: 0,
            time_saved: 0
        });
        
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
        const token = localStorage.getItem('auth_token');
        fetch(`${API_BASE_URL}/api/unsubscribe/status`, {
            method: 'GET',
            headers: token ? { 'Authorization': `Bearer ${token}` } : {},
            credentials: 'include'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Update stats
            updateStatsUI(data.stats);
            
            // Update activities
            updateActivitiesUI(data.activities);
            
            // Update unsubscribed services
            fetch(`${API_BASE_URL}/api/unsubscribed-services`, {
                method: 'GET',
                headers: token ? { 'Authorization': `Bearer ${token}` } : {},
                credentials: 'include'
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(services => {
                console.log('Services data during polling:', services);
                updateServicesUI(services);
            })
            .catch(error => {
                console.error('Error loading unsubscribed services during polling:', error);
            });
            
            // Update progress with real-time data
            const processed = data.stats.total_scanned || 0;
            processedEmails = processed;
            
            // Handle real-time processing updates
            if (data.processing) {
                const progress = data.processing.progress;
                const currentEmailInfo = progress.current_email_info;
                
                // Update status with current email info
                if (currentEmailInfo) {
                    currentProcessingStatus = currentEmailInfo.message || 
                        `Processing ${currentEmailInfo.sender || 'email'}...`;
                } else {
                    currentProcessingStatus = `Processing emails... (${processed}/${totalEmailsToProcess})`;
                }
                
                // Check if process is complete
                if (data.processing.status === 'completed') {
                    finishUnsubscriptionProcess();
                }
            } else {
                // Update status based on current progress
                currentProcessingStatus = `Processing emails... (${processed}/${totalEmailsToProcess})`;
                
                // Check if process is complete
                if (processed >= totalEmailsToProcess) {
                    finishUnsubscriptionProcess();
                }
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
    currentProcessingStatus = 'idle';
    
    // Clear polling interval
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        statusCheckInterval = null;
    }
    
    // Update dashboard to show stopped state
    loadUserData();
}

// Finish the unsubscription process
function finishUnsubscriptionProcess() {
    // Set processing state
    isProcessing = false;
    currentProcessingStatus = 'idle';
    
    // Clear polling interval
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        statusCheckInterval = null;
    }
    
    // Reload user data to ensure we have the latest stats
    loadUserData();
    
    // Add a small delay then force reload to ensure backend has completely finished
    // This handles any edge cases where the backend might still be finalizing
    setTimeout(() => {
        console.log('Performing final stats refresh after delay');
        loadUserData();
    }, 500);
    
    // Show completion message
    const token = localStorage.getItem('auth_token');
    fetch(`${API_BASE_URL}/api/stats`, {
        method: 'GET',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
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

// Debug authentication state
function debugAuthState() {
    console.log('=== Auth State Debug ===');
    console.log('localStorage token:', localStorage.getItem('auth_token'));
    console.log('sessionStorage token:', sessionStorage.getItem('auth_token'));
    console.log('Current URL:', window.location.href);
    console.log('URL params:', new URLSearchParams(window.location.search).toString());
    
    // Test auth status endpoint
    const token = localStorage.getItem('auth_token');
    fetch(`${API_BASE_URL}/api/auth/status`, {
        method: 'GET',
        credentials: 'include',
        headers: {
            'Authorization': token ? `Bearer ${token}` : '',
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        console.log('Auth status response:', response.status);
        console.log('Response headers:', response.headers);
        return response.json();
    })
    .then(data => {
        if (data.authenticated) {
            console.log('✓ User is authenticated');
        } else {
            console.log('✗ User is not authenticated');
        }
    })
    .catch(error => {
        console.error('Auth status error:', error);
    });
}

// Initialize the app when the DOM is loaded
document.addEventListener('DOMContentLoaded', initApp);
