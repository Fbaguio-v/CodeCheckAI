document.addEventListener("DOMContentLoaded", () => {
    const toggleBtn = document.getElementById("toggle-sidebar"),
    sidebar = document.getElementById("sidebar"),
    layout = document.getElementById("layout"),
    registerToggle1 = document.getElementById('id-for-password'),
    registerToggle2 = document.getElementById('id-for-confirm'),
    registerInput1 = document.getElementById('id_password1'),
    registerInput2 = document.getElementById('id_password2'),
    resetPasswordToggle = document.getElementById('id-for-reset-password'),
    resetPasswordInput = document.getElementById('id_new_password1'),
    resetConfirmPasswordToggle = document.getElementById('id-for-reset-password-confirm'),
    resetConfirmPasswordInput = document.getElementById('id_new_password2'),
    terms = document.getElementById("terms"),
    privacy = document.getElementById("privacy"),
    termsDialog = document.getElementById("myTerms"),
    privacyDialog = document.getElementById("myPrivacy"),
    loginToggle = document.getElementById('id_for_login_toggle'),
    loginInput = document.getElementById('id_password'),
    joinClassButton = document.getElementById("join-class"),
    compiler = document.getElementById("compiler"),
    div = document.getElementById("div-number"),
    pageSizeDefault = 10,
    usersContainer = document.getElementById("users-container"),
    prevBtn = document.getElementById("users-prev-btn"),
    nextBtn = document.getElementById("users-next-btn"),
    pageIndicator = document.getElementById("users-page-indicator"),
    searchUser = document.getElementById("search_user");

    // below is for subjects html in admin
    // const tableId = 'subjects-table';
    // const prevBtnSubject = document.getElementById('subjects-prev-btn');
    // const nextBtnSubject = document.getElementById('subjects-next-btn');
    // const pageIndicatorSubject = document.getElementById('subjects-page-indicator');
    // const searchInput = document.getElementById('subjects-search');

    if(usersContainer && prevBtn && nextBtn && pageIndicator && searchUser) {

        searchUser.addEventListener("keyup", (e) => {
            filterTable("users-table", e.target.value, [1, 2]);
        });

        let state = {
            pageSize: pageSizeDefault,
            currentPage: 1,
            rows: []
        };

        function initPagination() {
            const table = usersContainer.querySelector('#users-table');
            if (!table) return;
            const tbody = table.querySelector('tbody');
            if (!tbody) return;

            state.rows = Array.from(tbody.querySelectorAll('tr'));
            // mark all rows as matching initially
            state.rows.forEach(r => r.dataset.matches = '1');
            state.currentPage = 1;
            renderPage();

            // wire buttons
            prevBtn.onclick = () => { if (state.currentPage > 1) { state.currentPage--; renderPage(); } };
            nextBtn.onclick = () => { const totalPages = Math.max(1, Math.ceil(getMatchedRows().length / state.pageSize)); if (state.currentPage < totalPages) { state.currentPage++; renderPage(); } };
        }

        function getMatchedRows() {
            return state.rows.filter(r => r.dataset.matches !== '0');
        }

        function renderPage() {
            const matched = getMatchedRows();
            const totalPages = Math.max(1, Math.ceil(matched.length / state.pageSize));
            if (state.currentPage > totalPages) state.currentPage = totalPages;

            // hide all rows
            state.rows.forEach(r => r.style.display = 'none');

            // show current page slice
            const start = (state.currentPage - 1) * state.pageSize;
            const end = start + state.pageSize;
            const pageRows = matched.slice(start, end);
            pageRows.forEach(r => r.style.display = '');

            // update controls
            pageIndicator.textContent = `Page ${state.currentPage} of ${totalPages}`;
            prevBtn.disabled = state.currentPage <= 1;
            nextBtn.disabled = state.currentPage >= totalPages;
            prevBtn.classList.toggle('opacity-50', prevBtn.disabled);
            nextBtn.classList.toggle('opacity-50', nextBtn.disabled);
            prevBtn.classList.toggle('cursor-not-allowed', prevBtn.disabled);
            nextBtn.classList.toggle('cursor-not-allowed', nextBtn.disabled);
        }

        window.filterTable = function(tableId, searchText, searchColumns) {
            const table = document.getElementById(tableId);
            if (!table) return;
            const tbody = table.getElementsByTagName('tbody')[0];
            const rows = Array.from(tbody.getElementsByTagName('tr'));
            const searchLower = (searchText || '').toLowerCase();

            rows.forEach(row => {
                if (!searchLower) {
                    row.dataset.matches = '1';
                } else {
                    let found = false;
                    for (let colIndex of searchColumns) {
                        const cell = row.cells[colIndex];
                        if (cell && cell.textContent.toLowerCase().includes(searchLower)) {
                            found = true;
                            break;
                        }
                    }
                    row.dataset.matches = found ? '1' : '0';
                }
            });

            // reset to first page on new filter
            state.currentPage = 1;
            renderPage();
        };

        if (usersContainer) {
            const observer = new MutationObserver((mutationsList) => {
                for (const m of mutationsList) {
                    if (m.type === 'childList') {
                        // small timeout to allow HTMX to finish inserting nodes
                        setTimeout(initPagination, 50);
                        break;
                    }
                }
            });
            observer.observe(usersContainer, { childList: true, subtree: true });
        }
    }


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

    const updateLineNumbers = () => {
        const lines = compiler.value.split("\n").length;
        let lineNumbers = "";
        for (let i = 1; i <= lines; i++) {
            lineNumbers += `${i}\n`;
        }
        div.textContent = lineNumbers;
    };

    async function joinClass() {
		let subject_id = document.getElementById("id_subject_id");
		const response = await fetch("/e/", {
			method : "POST",
			headers : {
				"Content-Type" : "application/json",
				"X-CSRFToken" : getCookie("csrftoken")
			},
			body : JSON.stringify({
				"subject_id" : subject_id.value
			})
		});

		if(response.ok) {
			const data = await response.json()
			subject_id.value = "";

			if (data.redirect_url) {
		        window.location.href = data.redirect_url;
		    }
		}
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

    if(resetPasswordToggle && resetPasswordInput && resetConfirmPasswordToggle && resetConfirmPasswordInput) {
        resetPasswordToggle.addEventListener("click", () => {
            showPassword(resetPasswordInput, resetPasswordInput.type, resetPasswordToggle);
        });

        resetConfirmPasswordToggle.addEventListener("click", () => {
            showPassword(resetConfirmPasswordInput, resetConfirmPasswordInput.type, resetConfirmPasswordToggle);
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

    if(joinClassButton) {
        joinClassButton.addEventListener("click", () => {
            joinClass();
        });
    }

    if (compiler && div) {
        updateLineNumbers();

        compiler.addEventListener("input", updateLineNumbers);

        compiler.addEventListener("scroll", () => {
            div.scrollTop = compiler.scrollTop;
        });

        compiler.addEventListener("keydown", (e) => {
            if (e.key === "Tab") {
                e.preventDefault();
                const start = compiler.selectionStart;
                const end = compiler.selectionEnd;
                const indent = "    ";
                compiler.value = compiler.value.substring(0, start) + indent + compiler.value.substring(end);
                compiler.selectionStart = compiler.selectionEnd = start + indent.length;
                updateLineNumbers();
            }
        });
    }

    function checkActivityAvailability() {
        const serverTime = new Date("{{ server_time }}");
        const dueAt = new Date("{{ activity.due_at|date:'c' }}");
        
        if (!dueAt) return; // No due date set
        
        const now = new Date(serverTime.getTime() + (Date.now() - new Date("{{ server_time }}").getTime()));
        
        if (now > dueAt) {
            document.querySelectorAll('button[name="action"], #language_id, select').forEach(element => {
                if (element.name === "action" || element.id === "language_id") {
                    element.disabled = true;
                    element.classList.add('bg-gray-500', 'cursor-not-allowed', 'opacity-60');
                    element.classList.remove('bg-black', 'hover:bg-gray-500', 'hover:bg-blue-700');
                }
            });
        }
    }
    
    setInterval(checkActivityAvailability, 30000);
    checkActivityAvailability();
    setTimeout(initPagination, 100);
});