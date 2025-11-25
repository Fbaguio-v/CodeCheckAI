document.addEventListener("DOMContentLoaded", () => {
    const toggleBtn = document.getElementById("toggle-sidebar");
    const sidebar = document.getElementById("sidebar");
    const layout = document.getElementById("layout");

    // below is for register html
    const registerToggle1 = document.getElementById('id-for-password');
    const registerToggle2 = document.getElementById('id-for-confirm');
    const registerInput1 = document.getElementById('id_password1');
    const registerInput2 = document.getElementById('id_password2');

    // below is for register html but for terms and condition
    const terms = document.getElementById("terms");
    const privacy = document.getElementById("privacy");
    const termsDialog = document.getElementById("myTerms");
    const privacyDialog = document.getElementById("myPrivacy");

    // below is for login html
    const loginToggle = document.getElementById('id_for_login_toggle');
    const loginInput = document.getElementById('id_password');

    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function showPassword(input, type, toggle) {
        if(type === "password") {
            input.type = "text";
            toggle.textContent = "Hide";
        } else{
            input.type = "password";
            toggle.textContent = "Show";
        }
    }

    function setSidebarState(isHidden) {
        if (isHidden) {
            sidebar.classList.add("hidden");
            layout.classList.remove("grid-cols-[200px_1fr]");
            layout.classList.add("grid-cols-1");
        } else {
            sidebar.classList.remove("hidden");
            layout.classList.remove("grid-cols-1");
            layout.classList.add("grid-cols-[200px_1fr]");
        }
    }

    if (toggleBtn && sidebar && layout) {
        const savedState = localStorage.getItem("sidebarHidden");
        if (savedState !== null) {
            setSidebarState(savedState === "true");
        }

        toggleBtn.addEventListener("click", () => {
            const isHidden = sidebar.classList.toggle("hidden");
            setSidebarState(isHidden);

            localStorage.setItem("sidebarHidden", isHidden);
        });
    }

    // put if condition so that it does not return an error
    if(registerToggle1 && registerInput1 && registerToggle2 && registerInput2) {
        registerToggle1.addEventListener("click", () => {
            showPassword(registerInput1, registerInput1.type, registerToggle1);
        });

        registerToggle2.addEventListener("click", () => {
            showPassword(registerInput2, registerInput2.type, registerToggle2);
        });
    }

    if(loginToggle && loginInput) {
        loginToggle.addEventListener("click", () => {
            showPassword(loginInput, loginInput.type, loginToggle);
        });
    }

    // below is for dialog
    if(terms && privacy) {
        terms.addEventListener("click", () => {
            termsDialog.showModal();
        });

        privacy.addEventListener("click", () => {
            privacyDialog.showModal();
        });
    }
});