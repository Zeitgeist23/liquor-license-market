(function () {
  "use strict";

  var PUBLISHABLE_KEY = "pk_live_Y2xlcmsubGlxdW9ybGljZW5zZW1hcmtldC5jb20k";
  var FRONTEND_API = "https://clerk.liquorlicensemarket.com";
  var loginSelector = 'a[href="/client-login.html"], a[href$="/client-login.html"]';
  var readyPromise;

  var appearance = {
    variables: {
      colorPrimary: "#eda91a",
      colorBackground: "#071d33",
      colorInputBackground: "#0f2742",
      colorInputText: "#f7f3ea",
      colorText: "#f7f3ea",
      colorTextSecondary: "#c8d0da",
      colorDanger: "#ef6f6c",
      borderRadius: "10px",
      fontFamily: "Arial, Helvetica, sans-serif"
    },
    elements: {
      cardBox: "llm-auth-card-box",
      card: "llm-auth-card",
      headerTitle: "llm-auth-title",
      headerSubtitle: "llm-auth-subtitle",
      formButtonPrimary: "llm-auth-primary",
      footerActionLink: "llm-auth-link"
    }
  };

  function addAuthStyles() {
    if (document.getElementById("llm-clerk-styles")) return;
    var style = document.createElement("style");
    style.id = "llm-clerk-styles";
    style.textContent =
      ".llm-auth-card-box{box-shadow:0 24px 70px rgba(0,0,0,.48)!important}" +
      ".llm-auth-card{border:1px solid rgba(237,169,26,.72)!important;background:#071d33!important}" +
      ".llm-auth-title{font-family:Georgia,'Times New Roman',serif!important}" +
      ".llm-auth-primary{font-weight:800!important;color:#071d33!important;box-shadow:0 7px 22px rgba(237,169,26,.24)!important}" +
      ".llm-auth-link{font-weight:700!important}" +
      ".cl-modalBackdrop{background:rgba(1,12,24,.78)!important;backdrop-filter:blur(5px)}";
    document.head.appendChild(style);
  }

  function loadScript(src, attributes) {
    return new Promise(function (resolve, reject) {
      var existing = document.querySelector('script[src="' + src + '"]');
      if (existing) {
        if (existing.dataset.loaded === "true") return resolve();
        existing.addEventListener("load", resolve, { once: true });
        existing.addEventListener("error", reject, { once: true });
        return;
      }
      var script = document.createElement("script");
      script.async = true;
      script.crossOrigin = "anonymous";
      script.src = src;
      Object.keys(attributes || {}).forEach(function (name) {
        script.setAttribute(name, attributes[name]);
      });
      script.addEventListener("load", function () {
        script.dataset.loaded = "true";
        resolve();
      }, { once: true });
      script.addEventListener("error", reject, { once: true });
      document.head.appendChild(script);
    });
  }

  function initializeClerk() {
    if (readyPromise) return readyPromise;
    addAuthStyles();
    readyPromise = loadScript(FRONTEND_API + "/npm/@clerk/ui@1/dist/ui.browser.js")
      .then(function () {
        return loadScript(FRONTEND_API + "/npm/@clerk/clerk-js@6/dist/clerk.browser.js", {
          "data-clerk-publishable-key": PUBLISHABLE_KEY
        });
      })
      .then(function () {
        if (!window.Clerk) throw new Error("Clerk failed to initialize.");
        return window.Clerk.load({
          ui: { ClerkUI: window.__internal_ClerkUICtor }
        });
      })
      .then(function () {
        document.documentElement.classList.add("llm-clerk-ready");
        return window.Clerk;
      })
      .catch(function (error) {
        console.warn("LLM account services are temporarily unavailable.", error);
        readyPromise = null;
        throw error;
      });
    return readyPromise;
  }

  function openAccount() {
    return initializeClerk().then(function (clerk) {
      if (clerk.user && typeof clerk.openUserProfile === "function") {
        clerk.openUserProfile({ appearance: appearance });
        return;
      }
      clerk.openSignIn({
        appearance: appearance,
        fallbackRedirectUrl: window.location.origin + "/",
        signUpFallbackRedirectUrl: window.location.origin + "/"
      });
    });
  }

  document.addEventListener("click", function (event) {
    var link = event.target.closest(loginSelector);
    if (!link) return;
    event.preventDefault();
    openAccount().catch(function () {
      window.location.href = "/client-login.html";
    });
  });

  function mountAccountPage() {
    var mount = document.querySelector("[data-clerk-auth-mount]");
    if (!mount) return;
    initializeClerk().then(function (clerk) {
      var loading = document.querySelector("[data-clerk-auth-loading]");
      if (loading) loading.hidden = true;
      if (clerk.user) {
        mount.innerHTML =
          '<section class="llm-account-welcome"><p class="eyebrow">CLIENT ACCOUNT</p>' +
          '<h1>Welcome back</h1><p>You are securely signed in.</p>' +
          '<button type="button" class="llm-account-button" data-open-profile>Manage account</button></section>';
        mount.querySelector("[data-open-profile]").addEventListener("click", function () {
          clerk.openUserProfile({ appearance: appearance });
        });
      } else {
        clerk.mountSignIn(mount, {
          appearance: appearance,
          fallbackRedirectUrl: window.location.origin + "/",
          signUpFallbackRedirectUrl: window.location.origin + "/"
        });
      }
    }).catch(function () {
      var loading = document.querySelector("[data-clerk-auth-loading]");
      if (loading) {
        loading.hidden = false;
        loading.textContent = "Account services are being connected. Please try again shortly.";
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      mountAccountPage();
      initializeClerk().catch(function () {});
    });
  } else {
    mountAccountPage();
    initializeClerk().catch(function () {});
  }
})();