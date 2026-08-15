(function () {
  "use strict";

  var PUBLISHABLE_KEY = "pk_live_Y2xlcmsubGlxdW9ybGljZW5zZW1hcmtldC5jb20k";
  var FRONTEND_API = "https://clerk.liquorlicensemarket.com";
  var loginSelector = 'a[href="/client-login.html"], a[href$="/client-login.html"]';
  var readyPromise;

  var appearance = {
    variables: {
      colorPrimary: "#eda91a",
      colorBackground: "#102d4a",
      colorInputBackground: "#f7f3ea",
      colorInputText: "#071d33",
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
      ".llm-auth-card{border:1px solid rgba(237,169,26,.72)!important;background:#102d4a!important;color:#f7f3ea!important}" +
      ".cl-card,.cl-footer{background:#102d4a!important;color:#f7f3ea!important}" +
      ".cl-headerTitle{color:#eda91a!important}" +
      ".cl-headerSubtitle,.cl-formFieldLabel,.cl-dividerText,.cl-footerActionText,.cl-socialButtonsBlockButtonText,.cl-footerPagesLink,.cl-identityPreviewText{color:#f7f3ea!important}" +
      ".cl-formFieldInput{background:#f7f3ea!important;color:#071d33!important;border-color:rgba(237,169,26,.55)!important}" +
      ".cl-formFieldInput::placeholder{color:#5d6874!important;opacity:1!important}" +
      ".cl-socialButtonsBlockButton{background:#173a5d!important;border-color:rgba(237,169,26,.55)!important;color:#f7f3ea!important}" +
      ".cl-footer{border-top-color:rgba(237,169,26,.38)!important}" +
      ".cl-footerActionLink,.cl-modalCloseButton{color:#eda91a!important}" +
      "*:has(>a[aria-label='Clerk logo'])>p,a[aria-label='Clerk logo'],a[aria-label='Clerk logo'] svg{color:#dbe5ef!important;opacity:1!important;filter:none!important}" +
      "a[aria-label='Clerk logo']:hover,a[aria-label='Clerk logo']:focus{color:#eda91a!important}" +
      "html.llm-profile-open [role='dialog']{width:min(900px,calc(100vw - 40px))!important;max-width:900px!important;height:min(620px,calc(100vh - 40px))!important;max-height:620px!important;min-height:0!important;margin:auto!important;box-sizing:border-box!important;overflow:hidden!important}" +
      "html.llm-profile-open [role='dialog']>.cl-cardBox,html.llm-profile-open [role='dialog']>.cl-card,html.llm-profile-open [role='dialog']>div{width:100%!important;max-width:900px!important;height:100%!important;max-height:620px!important;min-height:0!important;box-sizing:border-box!important}" +
      "html.llm-profile-open [role='dialog'] .cl-pageScrollBox,html.llm-profile-open [role='dialog'] .cl-scrollBox{max-height:620px!important;overflow-y:auto!important}" +
      "html.llm-profile-open [role='dialog'] .cl-navbar{width:220px!important;min-width:220px!important}" +
      "@media(max-width:760px){html.llm-profile-open [role='dialog']{width:calc(100vw - 20px)!important;height:calc(100vh - 20px)!important;max-width:none!important;max-height:none!important}html.llm-profile-open [role='dialog'] .cl-navbar{width:auto!important;min-width:0!important}}" +
      ".cl-userProfile-root,.cl-userProfile-root *{color:#f7f3ea!important}" +
      ".cl-userProfile-root .cl-card,.cl-userProfile-root .cl-navbar,.cl-userProfile-root .cl-pageScrollBox{background:#102d4a!important}" +
      ".cl-userProfile-root .cl-navbar{border-right:1px solid rgba(237,169,26,.28)!important}" +
      ".cl-userProfile-root .cl-headerTitle,.cl-userProfile-root .cl-profileSectionTitleText{color:#eda91a!important}" +
      ".cl-userProfile-root .cl-headerSubtitle,.cl-userProfile-root .cl-profileSectionSubtitle{color:#c8d0da!important}" +
      ".cl-userProfile-root .cl-navbarButton,.cl-userProfile-root .cl-profileSectionContent,.cl-userProfile-root .cl-profileSectionContent p,.cl-userProfile-root .cl-profileSectionContent span{color:#f7f3ea!important}" +
      ".cl-userProfile-root .cl-navbarButton[aria-current='page'],.cl-userProfile-root .cl-profileSectionPrimaryButton,.cl-userProfile-root a{color:#eda91a!important}" +
      ".cl-userProfile-root .cl-badge{color:#f7f3ea!important;background:#173a5d!important}" +
      ".cl-userProfile-root .cl-menuButton,.cl-userProfile-root .cl-modalCloseButton{color:#eda91a!important}" +
      ".cl-userProfile-root .cl-footer *{color:#dbe5ef!important}" +
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

  function showUserProfile(clerk) {
    document.documentElement.classList.add("llm-profile-open");
    clerk.openUserProfile({ appearance: appearance });
    window.setTimeout(function () {
      var observer = new MutationObserver(function () {
        if (!document.querySelector("[role='dialog']")) {
          document.documentElement.classList.remove("llm-profile-open");
          observer.disconnect();
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }, 500);
  }

  function openAccount() {
    return initializeClerk().then(function (clerk) {
      if (clerk.user && typeof clerk.openUserProfile === "function") {
        showUserProfile(clerk);
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
          showUserProfile(clerk);
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