"use strict";

(() => {
    const CONFIG_MESSAGE = "Supabase chưa được cấu hình. Vui lòng thiết lập Project URL và Publishable/Anon Key.";
    const NETWORK_MESSAGE = "Không thể kết nối. Vui lòng kiểm tra mạng và thử lại.";
    const RECOVERY_MESSAGE = "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn. Vui lòng yêu cầu một liên kết mới.";
    const FORGOT_MESSAGE = "Nếu email này được liên kết với một tài khoản, bạn sẽ nhận được hướng dẫn đặt lại mật khẩu.";
    const SDK_URL = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.2/dist/umd/supabase.js";
    const root = new URL("./", document.baseURI);
    const publicPages = ["index.html", "data-analyzer.html", "health-prediction.html"];
    const form = document.getElementById("authForm");
    const mode = form?.dataset.authForm;
    const fields = document.getElementById("authFields");
    const submitButton = form?.querySelector('[type="submit"]');
    const submitLabel = submitButton?.textContent;
    let client = null;
    let session = null;
    let status = "loading";
    let pending = false;
    let signingOut = false;
    let recoveryUserId = null;
    let passwordUpdated = false;

    function safeReturnPath(value) {
        const fallback = new URL("index.html", root).pathname;
        if (!value || /[\\\u0000-\u0020]/.test(value)) return fallback;
        try {
            const target = new URL(value, root);
            if (target.origin !== location.origin || target.username || target.password ||
                !publicPages.some(page => target.pathname === new URL(page, root).pathname)) return fallback;
            return target.pathname + target.search + target.hash;
        } catch {
            return fallback;
        }
    }

    const returnPath = safeReturnPath(new URL(location.href).searchParams.get("return"));

    function authPageUrl(page, destination = returnPath) {
        const url = new URL(page, root);
        url.searchParams.set("return", safeReturnPath(destination));
        return url;
    }

    function publicUser() {
        return session?.user ? Object.freeze({ id: session.user.id, email: session.user.email || "" }) : null;
    }

    function message(text, kind = "info") {
        const element = document.getElementById("authMessage");
        if (!element) return;
        element.textContent = text;
        element.dataset.kind = kind;
        element.hidden = !text;
        element.setAttribute("role", kind === "error" ? "alert" : "status");
    }

    function showEmailConfirmationNotice() {
        if (mode !== "login") return;
        const url = new URL(location.href);
        const banner = document.getElementById("authConfirmedMessage");
        if (url.searchParams.get("confirmed") !== "1" || !banner) return;
        // This flag only controls the notice; sessions still come from Supabase.
        banner.hidden = false;
        url.searchParams.delete("confirmed");
        history.replaceState(history.state, "", url.href);
    }

    function authStatus(text) {
        const element = document.getElementById("authStatus");
        if (element) element.textContent = text;
    }

    function navbarMessage(text) {
        document.querySelectorAll("[data-auth-nav-message]").forEach(element => {
            element.textContent = text;
            element.hidden = !text;
        });
    }

    function updateAvailability() {
        const available = status === "ready" && (mode !== "reset" ||
            (recoveryUserId && session?.user?.id === recoveryUserId && !passwordUpdated));
        if (fields) fields.disabled = !available || pending;
        if (submitButton) {
            submitButton.disabled = !available || pending;
            submitButton.textContent = pending ? "Đang xử lý…" : submitLabel;
        }
        if (form) form.setAttribute("aria-busy", String(pending));
    }

    function renderNavbar() {
        const user = publicUser();
        const continueLink = document.getElementById("authContinue");
        if (continueLink) { continueLink.hidden = !user; continueLink.href = returnPath; }
        document.querySelectorAll("[data-auth-guest]").forEach(element => { element.hidden = Boolean(user); });
        document.querySelectorAll("[data-auth-user]").forEach(element => { element.hidden = !user; });
        document.querySelectorAll("[data-auth-email]").forEach(element => {
            element.textContent = user?.email || "";
            element.title = user?.email || "";
        });
        document.querySelectorAll("[data-auth-logout]").forEach(button => {
            button.disabled = signingOut;
            button.textContent = signingOut ? "Đang đăng xuất…" : "Đăng xuất";
        });
    }

    function applySession(nextSession) {
        session = nextSession?.user?.id ? nextSession : null;
        if (!session || (recoveryUserId && session.user.id !== recoveryUserId)) recoveryUserId = null;
        if (status === "ready" && !session) {
            if (mode === "login") authStatus("Hệ thống tài khoản đã sẵn sàng.");
            if (mode === "reset" && !passwordUpdated) authStatus(RECOVERY_MESSAGE);
        }
        renderNavbar();
        updateAvailability();
        window.dispatchEvent(new CustomEvent("portfolio:authchange", { detail: {
            user: publicUser(), loggedIn: Boolean(session), status
        } }));
    }

    function isPublicConfig(config) {
        if (!config?.url || !config?.key || config.url.includes("YOUR_") || config.key.includes("YOUR_")) return false;
        try {
            const url = new URL(config.url);
            if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash || url.pathname !== "/") return false;
            if (/^sb_publishable_[A-Za-z0-9_-]+$/.test(config.key)) return true;
            // Legacy public JWTs must have the anon role; privileged keys are rejected.
            const payload = config.key.split(".")[1];
            if (!payload) return false;
            const decoded = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
            return decoded.role === "anon";
        } catch {
            return false;
        }
    }

    function loadSdk() {
        if (window.supabase?.createClient) return Promise.resolve(window.supabase);
        return new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = SDK_URL;
            script.async = true;
            script.referrerPolicy = "no-referrer";
            const timer = setTimeout(() => { script.remove(); reject(new Error("sdk_unavailable")); }, 15000);
            script.onload = () => {
                clearTimeout(timer);
                if (window.supabase?.createClient) resolve(window.supabase);
                else reject(new Error("sdk_unavailable"));
            };
            script.onerror = () => { clearTimeout(timer); script.remove(); reject(new Error("sdk_unavailable")); };
            document.head.appendChild(script);
        });
    }

    function friendlyError(error, operation) {
        const code = error?.code;
        if (["AuthRetryableFetchError", "TypeError", "AbortError"].includes(error?.name) ||
            error?.status === 0 || ["request_timeout", "fetch_error"].includes(code)) return NETWORK_MESSAGE;
        if (["over_request_rate_limit", "over_email_send_rate_limit"].includes(code) || error?.status === 429) {
            return "Bạn đã gửi nhiều yêu cầu. Vui lòng chờ một chút rồi thử lại.";
        }
        if (code === "email_address_invalid") return "Email không đúng định dạng.";
        if (operation === "login") {
            if (["invalid_credentials", "user_not_found"].includes(code)) return "Email hoặc mật khẩu không chính xác.";
            if (code === "email_not_confirmed") return "Bạn cần xác nhận email trước khi đăng nhập. Hãy kiểm tra hộp thư.";
            return "Đăng nhập không thành công. Vui lòng thử lại.";
        }
        if (operation === "register") {
            if (["user_already_exists", "email_exists"].includes(code)) return "Tài khoản này đã được đăng ký. Hãy thử đăng nhập.";
            if (code === "weak_password") return "Mật khẩu chưa đáp ứng yêu cầu bảo mật của dự án. Hãy dùng mật khẩu mạnh hơn.";
            return "Đăng ký không thành công. Vui lòng thử lại.";
        }
        if (operation === "forgot") {
            if (["user_not_found", "invalid_credentials"].includes(code)) return FORGOT_MESSAGE;
            return "Chưa thể gửi yêu cầu đặt lại mật khẩu. Vui lòng thử lại.";
        }
        if (operation === "reset") {
            if (error?.name === "AuthSessionMissingError") return RECOVERY_MESSAGE;
            if (["session_not_found", "session_expired", "refresh_token_not_found", "otp_expired", "bad_jwt"].includes(code) || error?.status === 401 || error?.status === 403) return RECOVERY_MESSAGE;
            if (code === "same_password") return "Vui lòng chọn mật khẩu khác mật khẩu hiện tại.";
            if (code === "weak_password") return "Mật khẩu chưa đáp ứng yêu cầu bảo mật của dự án. Hãy dùng mật khẩu mạnh hơn.";
            return "Chưa thể cập nhật mật khẩu. Vui lòng thử lại.";
        }
        return "Đăng xuất không thành công. Vui lòng thử lại.";
    }

    function fieldError(field, text) {
        const error = document.getElementById(`${field.id}-error`);
        if (error) { error.textContent = text; error.hidden = !text; }
        if (text) field.setAttribute("aria-invalid", "true");
        else field.removeAttribute("aria-invalid");
    }

    function validateField(field) {
        let text = "";
        if (field.name === "email") {
            if (!field.value.trim()) text = "Vui lòng nhập email.";
            else if (field.validity.typeMismatch || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(field.value.trim())) text = "Email không đúng định dạng.";
        } else if (field.name === "password") {
            if (!field.value) text = "Vui lòng nhập mật khẩu.";
            else if (mode !== "login" && field.value.length < 8) text = "Mật khẩu phải có ít nhất 8 ký tự.";
        } else if (field.name === "confirmPassword") {
            if (!field.value) text = "Vui lòng nhập lại mật khẩu.";
            else if (field.value !== form.elements.namedItem("password").value) text = "Mật khẩu nhập lại không khớp.";
        }
        fieldError(field, text);
        return !text;
    }

    async function signOut() {
        if (!client || signingOut) return false;
        signingOut = true;
        navbarMessage("");
        renderNavbar();
        try {
            const { error } = await client.auth.signOut({ scope: "local" });
            if (error) { navbarMessage(friendlyError(error, "logout")); return false; }
            recoveryUserId = null;
            applySession(null);
            return true;
        } catch (error) {
            navbarMessage(friendlyError(error, "logout"));
            return false;
        } finally {
            signingOut = false;
            renderNavbar();
        }
    }

    async function submit(event) {
        event.preventDefault();
        if (pending) return;
        message("");
        const invalid = [...form.querySelectorAll("input[name]")].filter(field => !validateField(field));
        if (invalid.length) { invalid[0].focus(); return; }
        if (!client || status !== "ready") { message(status === "unconfigured" ? CONFIG_MESSAGE : NETWORK_MESSAGE, "error"); return; }
        if (mode === "reset" && (!recoveryUserId || session?.user?.id !== recoveryUserId || passwordUpdated)) { message(RECOVERY_MESSAGE, "error"); return; }
        pending = true;
        updateAvailability();
        const email = form.elements.namedItem("email")?.value.trim();
        const password = form.elements.namedItem("password")?.value;
        try {
            if (mode === "login") {
                const { data, error } = await client.auth.signInWithPassword({ email, password });
                if (error) { message(friendlyError(error, mode), "error"); return; }
                if (!data?.session?.user?.id) { message("Đăng nhập không thành công. Vui lòng thử lại.", "error"); return; }
                applySession(data.session);
                clearPasswords();
                location.assign(returnPath);
            } else if (mode === "register") {
                const { data, error } = await client.auth.signUp({ email, password, options: {
                    emailRedirectTo: "https://data-science-portfolio-steel.vercel.app/login.html?confirmed=1"
                } });
                if (error) { message(friendlyError(error, mode), "error"); return; }
                clearPasswords();
                if (data?.session?.user?.id) {
                    applySession(data.session);
                    location.assign(returnPath);
                } else {
                    const neutral = !data?.user || (Array.isArray(data.user.identities) && !data.user.identities.length);
                    message(neutral ? "Yêu cầu đăng ký đã được tiếp nhận. Nếu email được chấp nhận, bạn sẽ nhận được email xác nhận. Bạn cũng có thể thử đăng nhập."
                        : "Đăng ký thành công. Hãy kiểm tra email để xác nhận tài khoản.", "success");
                }
            } else if (mode === "forgot") {
                const { error } = await client.auth.resetPasswordForEmail(email, {
                    redirectTo: "https://data-science-portfolio-steel.vercel.app/reset-password.html"
                });
                if (error) {
                    const text = friendlyError(error, mode);
                    message(text, text === FORGOT_MESSAGE ? "success" : "error");
                } else message(FORGOT_MESSAGE, "success");
            } else if (mode === "reset") {
                const { data: verified, error: verificationError } = await client.auth.getUser();
                if (verificationError) { message(friendlyError(verificationError, "reset"), "error"); return; }
                if (verified?.user?.id !== recoveryUserId) { recoveryUserId = null; message(RECOVERY_MESSAGE, "error"); return; }
                const { error } = await client.auth.updateUser({ password });
                if (error) { message(friendlyError(error, mode), "error"); return; }
                passwordUpdated = true;
                recoveryUserId = null;
                clearPasswords();
                await signOut();
                message("Mật khẩu đã được cập nhật thành công.", "success");
                const next = document.getElementById("authResetSuccess");
                if (next) next.hidden = false;
            }
        } catch (error) {
            message(friendlyError(error, mode), "error");
        } finally {
            pending = false;
            updateAvailability();
        }
    }

    function clearPasswords() {
        form?.querySelectorAll('input[name="password"], input[name="confirmPassword"]').forEach(input => {
            input.value = "";
            input.type = "password";
        });
        form?.querySelectorAll("[data-password-toggle]").forEach(button => {
            button.textContent = "Hiện";
            button.setAttribute("aria-pressed", "false");
        });
    }

    document.querySelectorAll("[data-auth-link]").forEach(link => {
        const destination = mode ? returnPath : safeReturnPath(location.pathname + location.search + location.hash);
        link.href = authPageUrl(link.dataset.authLink, destination).href;
    });
    document.querySelectorAll("[data-auth-logout]").forEach(button => button.addEventListener("click", signOut));
    form?.addEventListener("submit", submit);
    form?.querySelectorAll("input[name]").forEach(field => {
        field.addEventListener("blur", () => validateField(field));
        field.addEventListener("input", () => {
            message("");
            validateField(field);
            const confirm = form.elements.namedItem("confirmPassword");
            if (field.name === "password" && confirm?.value) validateField(confirm);
        });
    });
    document.querySelectorAll("[data-password-toggle]").forEach(button => button.addEventListener("click", () => {
        const input = document.getElementById(button.dataset.passwordToggle);
        if (!input) return;
        const show = input.type === "password";
        input.type = show ? "text" : "password";
        button.textContent = show ? "Ẩn" : "Hiện";
        button.setAttribute("aria-pressed", String(show));
    }));

    async function initialize() {
        renderNavbar();
        updateAvailability();
        const config = window.PORTFOLIO_SUPABASE_CONFIG;
        if (!isPublicConfig(config)) {
            status = "unconfigured";
            authStatus(CONFIG_MESSAGE);
            // Allow typing/validation while leaving network submit disabled.
            if (fields && mode !== "reset") fields.disabled = false;
            if (submitButton) submitButton.disabled = true;
            return;
        }
        try {
            const sdk = await loadSdk();
            client = sdk.createClient(config.url, config.key, { auth: {
                persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: "implicit"
            } });
            // Keep callback synchronous: do not call/await other Auth methods here.
            client.auth.onAuthStateChange((event, nextSession) => {
                if (event === "PASSWORD_RECOVERY" && nextSession?.user?.id) {
                    recoveryUserId = nextSession.user.id;
                    if (mode === "reset") authStatus("Liên kết hợp lệ. Bạn có thể đặt mật khẩu mới.");
                }
                applySession(nextSession);
            });
            const { data, error } = await client.auth.getSession();
            status = "ready";
            applySession(error ? null : data?.session);
            if (mode === "reset") {
                authStatus(recoveryUserId ? "Liên kết hợp lệ. Bạn có thể đặt mật khẩu mới." : RECOVERY_MESSAGE);
            } else authStatus(error ? "Chưa thể khôi phục phiên. Bạn có thể đăng nhập lại." : "Hệ thống tài khoản đã sẵn sàng.");
            const continueLink = document.getElementById("authContinue");
            if (continueLink && session && mode === "login") {
                continueLink.href = returnPath;
                continueLink.hidden = false;
                authStatus("Bạn đã đăng nhập. Có thể tiếp tục về trang trước.");
            }
        } catch {
            status = "unavailable";
            applySession(null);
            authStatus(NETWORK_MESSAGE);
        }
    }

    showEmailConfirmationNotice();
    const ready = initialize();
    window.PortfolioAuth = Object.freeze({
        ready,
        getUser: publicUser,
        getSession: () => session,
        getStatus: () => status,
        signOut
    });
})();
