// Fonction pour afficher ou cacher le mot de passe
function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    if (input) {
        input.type = input.type === "password" ? "text" : "password";
    }
}

// Fonction pour vérifier la force du mot de passe
function initPasswordStrength(inputId, helpId) {
    const passwordInput = document.getElementById(inputId);
    const help = document.getElementById(helpId);

    if (!passwordInput || !help) return;

    passwordInput.addEventListener("input", () => {
        const value = passwordInput.value;

        const strong = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,}$/;

        if (strong.test(value)) {
            help.textContent = "Mot de passe fort ✅";
            help.style.color = "green";
        } else {
            help.textContent = "Mot de passe trop faible ❌";
            help.style.color = "red";
        }
    });
}