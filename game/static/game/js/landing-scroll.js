/**
 * Landing Page Smooth Scroll Handler
 * Handles smooth scrolling to anchor links with proper navbar offset
 * Works across responsive breakpoints
 */

(function() {
    'use strict';

    // Get computed navbar height dynamically
    function getNavbarHeight() {
        const navbar = document.querySelector('.navbar');
        if (!navbar) return 85; // fallback to CSS default
        return navbar.offsetHeight;
    }

    // Get total scroll offset (navbar height + padding)
    function getScrollOffset() {
        const navHeight = getNavbarHeight();
        const padding = 24; // 1.5rem = 24px padding
        return navHeight + padding;
    }

    // Handle smooth scroll on anchor link clicks
    function handleAnchorLinks(e) {
        const href = e.target.getAttribute('href');
        
        // Check if it's an anchor link
        if (href && href.startsWith('#') && href.length > 1) {
            const targetId = href.substring(1);
            const targetElement = document.getElementById(targetId);
            
            // Only handle if target exists and is not the current page
            if (targetElement && !e.target.classList.contains('logo-link')) {
                e.preventDefault();
                
                const offset = getScrollOffset();
                const elementPosition = targetElement.getBoundingClientRect().top + window.scrollY;
                const scrollTarget = elementPosition - offset;
                
                // Smooth scroll to position
                window.scrollTo({
                    top: scrollTarget,
                    behavior: 'smooth'
                });
                
                // Update browser history
                history.pushState(null, null, href);
            }
        }
    }

    // Handle page load with hash (direct navigation or page refresh)
    function handleHashOnLoad() {
        if (window.location.hash) {
            const targetId = window.location.hash.substring(1);
            const targetElement = document.getElementById(targetId);
            
            if (targetElement) {
                // Use requestAnimationFrame to ensure DOM is ready
                requestAnimationFrame(() => {
                    const offset = getScrollOffset();
                    const elementPosition = targetElement.getBoundingClientRect().top + window.scrollY;
                    const scrollTarget = elementPosition - offset;
                    
                    window.scrollTo({
                        top: scrollTarget,
                        behavior: 'auto' // Use auto for initial load to avoid jarring animation
                    });
                });
            }
        }
    }

    // Update scroll offset on window resize (responsive behavior)
    let resizeTimeout;
    function handleWindowResize() {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            // Recalculate offset if needed on resize
            // This ensures proper spacing on orientation changes
        }, 250);
    }

    // Initialize event listeners
    function init() {
        // Handle anchor link clicks throughout the document
        document.addEventListener('click', handleAnchorLinks, true);
        
        // Handle page load with hash
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', handleHashOnLoad);
        } else {
            handleHashOnLoad();
        }
        
        // Handle window resize for responsive behavior
        window.addEventListener('resize', handleWindowResize);
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
