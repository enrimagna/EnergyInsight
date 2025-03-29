// Custom JavaScript for responsive documentation site

document.addEventListener('DOMContentLoaded', function() {
  const menuToggle = document.querySelector('.menu-toggle');
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.querySelector('.overlay');
  const content = document.querySelector('.content');
  
  // Function to check if we're on mobile
  function isMobile() {
    return window.innerWidth <= 768;
  }
  
  // Toggle sidebar on menu button click
  menuToggle.addEventListener('click', function() {
    if (isMobile()) {
      sidebar.classList.toggle('active');
      overlay.classList.toggle('active');
    } else {
      sidebar.classList.toggle('collapsed');
      // Adjust content margin when sidebar collapses on desktop
      if (sidebar.classList.contains('collapsed')) {
        localStorage.setItem('sidebarCollapsed', 'true');
      } else {
        localStorage.setItem('sidebarCollapsed', 'false');
      }
    }
  });
  
  // Close sidebar when clicking overlay (mobile only)
  if (overlay) {
    overlay.addEventListener('click', function() {
      sidebar.classList.remove('active');
      overlay.classList.remove('active');
    });
  }
  
  // Handle window resize
  window.addEventListener('resize', function() {
    if (!isMobile()) {
      // If transitioning from mobile to desktop
      sidebar.classList.remove('active');
      if (overlay) overlay.classList.remove('active');
      
      // Restore collapsed state from localStorage
      const collapsed = localStorage.getItem('sidebarCollapsed') === 'true';
      if (collapsed) {
        sidebar.classList.add('collapsed');
      } else {
        sidebar.classList.remove('collapsed');
      }
    }
  });
  
  // Initialize sidebar state from localStorage
  const savedCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
  if (savedCollapsed && !isMobile()) {
    sidebar.classList.add('collapsed');
  }
  
  // Add active class to current page in navigation
  const currentPath = window.location.pathname;
  const navLinks = document.querySelectorAll('.nav-link');
  
  navLinks.forEach(link => {
    const linkPath = link.getAttribute('href');
    if (currentPath.endsWith(linkPath) || 
        (currentPath.endsWith('/') && linkPath === 'index.html') ||
        (linkPath === 'README.html' && currentPath.endsWith('/'))) {
      link.classList.add('active');
      link.parentElement.classList.add('active');
    }
  });
});
