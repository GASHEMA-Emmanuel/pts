/* ============================================
   RBC Procurement Tracking System - Main JS
   ============================================ */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all components
    initSidebar();
    initTooltips();
    initDropdowns();
    initAlerts();
});

/* ============================================
   Sidebar Toggle
   ============================================ */
function initSidebar() {
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    const contentWrapper = document.querySelector('.content-wrapper');
    
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('show');
            
            // Add overlay for mobile
            let overlay = document.querySelector('.sidebar-overlay');
            if (!overlay) {
                overlay = document.createElement('div');
                overlay.className = 'sidebar-overlay';
                overlay.style.cssText = `
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0,0,0,0.5);
                    z-index: 999;
                    display: none;
                `;
                document.body.appendChild(overlay);
                
                overlay.addEventListener('click', function() {
                    sidebar.classList.remove('show');
                    overlay.style.display = 'none';
                });
            }
            
            if (sidebar.classList.contains('show')) {
                overlay.style.display = 'block';
            } else {
                overlay.style.display = 'none';
            }
        });
    }
    
    // Close sidebar on window resize (desktop)
    window.addEventListener('resize', function() {
        if (window.innerWidth >= 992 && sidebar) {
            sidebar.classList.remove('show');
            const overlay = document.querySelector('.sidebar-overlay');
            if (overlay) {
                overlay.style.display = 'none';
            }
        }
    });
}

/* ============================================
   Bootstrap Tooltips
   ============================================ */
function initTooltips() {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/* ============================================
   Dropdowns Enhancement
   ============================================ */
function initDropdowns() {
    // Close dropdowns when clicking outside
    document.addEventListener('click', function(event) {
        const dropdowns = document.querySelectorAll('.dropdown-menu.show');
        dropdowns.forEach(function(dropdown) {
            if (!dropdown.contains(event.target) && 
                !dropdown.previousElementSibling.contains(event.target)) {
                dropdown.classList.remove('show');
            }
        });
    });
}

/* ============================================
   Auto-dismiss Alerts
   ============================================ */
function initAlerts() {
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 5000); // Auto-dismiss after 5 seconds
    });
}

/* ============================================
   Form Validation Helpers
   ============================================ */
function validateForm(formElement) {
    const requiredFields = formElement.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(function(field) {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

/* ============================================
   API Helper Functions
   ============================================ */
const API = {
    baseUrl: '/api/v1',
    
    async get(endpoint) {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            credentials: 'same-origin'
        });
        return response.json();
    },
    
    async post(endpoint, data) {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            credentials: 'same-origin',
            body: JSON.stringify(data)
        });
        return response.json();
    },
    
    getCsrfToken() {
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        return cookieValue || '';
    }
};

/* ============================================
   Notification Helpers
   ============================================ */
function showNotification(message, type = 'info') {
    const container = document.querySelector('.messages-container') || document.querySelector('.main-content');
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.setAttribute('role', 'alert');
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    container.insertBefore(alert, container.firstChild);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
        bsAlert.close();
    }, 5000);
}

/* ============================================
   Date Formatting
   ============================================ */
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return new Date(dateString).toLocaleDateString('en-US', options);
}

function formatDateTime(dateString) {
    const options = { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    return new Date(dateString).toLocaleDateString('en-US', options);
}

function timeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    
    const intervals = {
        year: 31536000,
        month: 2592000,
        week: 604800,
        day: 86400,
        hour: 3600,
        minute: 60
    };
    
    for (const [unit, secondsInUnit] of Object.entries(intervals)) {
        const interval = Math.floor(seconds / secondsInUnit);
        if (interval >= 1) {
            return interval === 1 ? `1 ${unit} ago` : `${interval} ${unit}s ago`;
        }
    }
    
    return 'Just now';
}

/* ============================================
   Number Formatting
   ============================================ */
function formatCurrency(amount, currency = 'RWF') {
    return new Intl.NumberFormat('en-RW', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 0
    }).format(amount);
}

function formatNumber(number) {
    return new Intl.NumberFormat('en-RW').format(number);
}

/* ============================================
   Loading States
   ============================================ */
function showLoading(element) {
    element.classList.add('loading');
    element.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div>';
}

function hideLoading(element, content) {
    element.classList.remove('loading');
    element.innerHTML = content;
}

/* ============================================
   Confirmation Dialog
   ============================================ */
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

/* ============================================
   Export for global use
   ============================================ */
window.PTS = {
    API,
    showNotification,
    formatDate,
    formatDateTime,
    timeAgo,
    formatCurrency,
    formatNumber,
    showLoading,
    hideLoading,
    confirmAction,
    validateForm
};
