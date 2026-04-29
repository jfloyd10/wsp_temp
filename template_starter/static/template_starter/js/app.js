// Renders feather icons and wires up sidebar / topbar interactions.
(function () {
    if (window.feather) feather.replace();

    // Mobile sidebar toggle
    const sidebar = document.querySelector('.sidebar');
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    function closeMobileSidebar() {
        sidebar && sidebar.classList.remove('sidebar-mobile-open');
        sidebarOverlay && sidebarOverlay.classList.remove('active');
    }

    if (mobileMenuBtn && sidebar && sidebarOverlay) {
        mobileMenuBtn.addEventListener('click', () => {
            sidebar.classList.add('sidebar-mobile-open');
            sidebarOverlay.classList.add('active');
        });
        sidebarOverlay.addEventListener('click', closeMobileSidebar);
        document.querySelectorAll('.sidebar-link').forEach((link) => {
            link.addEventListener('click', () => {
                if (window.innerWidth < 1024) closeMobileSidebar();
            });
        });
    }

    // Topbar user dropdown
    const topbarUserBtn = document.getElementById('topbarUserBtn');
    const topbarUserDropdown = document.getElementById('topbarUserDropdown');
    if (topbarUserBtn && topbarUserDropdown) {
        topbarUserBtn.style.cursor = 'pointer';
        topbarUserBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            topbarUserDropdown.classList.toggle('show');
            const notif = document.getElementById('notificationDropdown');
            if (notif) notif.classList.add('hidden');
        });
        document.addEventListener('click', () => topbarUserDropdown.classList.remove('show'));
    }

    // Notification dropdown
    const notifBtn = document.getElementById('notificationBtn');
    const notifDropdown = document.getElementById('notificationDropdown');
    if (notifBtn && notifDropdown) {
        notifBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            notifDropdown.classList.toggle('hidden');
            if (topbarUserDropdown) topbarUserDropdown.classList.remove('show');
            if (window.feather) feather.replace();
        });
        document.addEventListener('click', (e) => {
            if (!notifDropdown.contains(e.target)) notifDropdown.classList.add('hidden');
        });
    }

    // Loading overlay fade-out
    window.addEventListener('load', () => {
        const lo = document.getElementById('loadingOverlay');
        if (lo) {
            lo.style.opacity = '0';
            setTimeout(() => (lo.style.display = 'none'), 300);
        }
    });
})();
