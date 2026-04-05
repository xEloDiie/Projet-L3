document.addEventListener("DOMContentLoaded", () => {
    // ===== Année footer =====
    const year = document.getElementById("year");
    if (year) {
        year.textContent = new Date().getFullYear();
    }

    // ===== Theme =====
    const themeSwitch = document.getElementById('themeSwitch');
    const body = document.body;
    const sun = document.getElementById('sun');
    const moon = document.getElementById('moon');

    if (themeSwitch) {
        if (localStorage.getItem('theme') === 'dark') {
            body.classList.add('dark-theme');
            themeSwitch.checked = true;
            sun?.classList.add('d-none');
            moon?.classList.remove('d-none');
        }

        themeSwitch.addEventListener('change', () => {
            body.classList.toggle('dark-theme');

            if (body.classList.contains('dark-theme')) {
                sun?.classList.add('d-none');
                moon?.classList.remove('d-none');
                localStorage.setItem('theme', 'dark');
            } else {
                sun?.classList.remove('d-none');
                moon?.classList.add('d-none');
                localStorage.setItem('theme', 'light');
            }
        });
    }
});