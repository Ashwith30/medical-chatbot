/**
 * Main Application Script
 * Initializes the medical chatbot interface
 */

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Medical ChatBot Application Loading...');
    
    // Initialize medical lookup system
    const medicalLookup = new MedicalLookup();
    medicalLookup.init();
    
    // Focus on input field
    const userInput = document.getElementById('userInput');
    if (userInput) {
        userInput.focus();
    }
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(event) {
        // Ctrl/Cmd + K to focus search
        if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
            event.preventDefault();
            if (userInput) {
                userInput.focus();
                userInput.select();
            }
        }
        
        // Escape to clear input
        if (event.key === 'Escape') {
            if (userInput && document.activeElement === userInput) {
                userInput.blur();
            }
        }
    });
    
    // Add visual feedback for user interactions
    const sendButton = document.querySelector('.send-btn');
    if (sendButton) {
        sendButton.addEventListener('mousedown', function() {
            this.style.transform = 'scale(0.95)';
        });
        
        sendButton.addEventListener('mouseup', function() {
            this.style.transform = 'scale(1)';
        });
        
        sendButton.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
        });
    }
    
    // Handle window resize for better mobile experience
    window.addEventListener('resize', function() {
        // Ensure chat history scrolls to bottom on resize
        const chatHistory = document.getElementById('chatHistory');
        if (chatHistory) {
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }
    });
    
    console.log('Medical ChatBot Application Ready!');
    
    // Show welcome message animation
    setTimeout(() => {
        const welcomeMessage = document.querySelector('.bot-message p');
        if (welcomeMessage) {
            welcomeMessage.style.opacity = '1';
            welcomeMessage.style.transform = 'translateY(0)';
        }
    }, 500);
});

// Service Worker Registration (for PWA features)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        // Uncomment below to enable service worker
        /*
        navigator.serviceWorker.register('/sw.js')
            .then(function(registration) {
                console.log('ServiceWorker registration successful with scope: ', registration.scope);
            })
            .catch(function(err) {
                console.log('ServiceWorker registration failed: ', err);
            });
        */
    });
}

// Error handling
window.addEventListener('error', function(event) {
    console.error('Application Error:', event.error);
});

// Unhandled promise rejection handler
window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled Promise Rejection:', event.reason);
});