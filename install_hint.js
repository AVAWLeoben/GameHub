/* WasteGame: small, infrequent iPad Home Screen help.
 * Direct URL: explain Share → Add to Home Screen.
 * Embedded in itch.io: optionally offer the configured direct URL instead.
 * No trackers, no dependencies on Pygame, no interruption to game loop.
 */
(() => {
    "use strict";

    const STORAGE_KEY = "wastegame-home-screen-tip-v2";
    const SHOW_DELAY_MS = 6000;
    const VISIBLE_FOR_MS = 18000;
    const REPEAT_AFTER_DAYS = 21;
    const DIRECT_URL = window.WASTEGAME_STANDALONE_URL || null;

    const params = new URLSearchParams(window.location.search);
    // Developer QA only: append ?show_install_hint=1 to a direct game URL.
    const forced = params.get("show_install_hint") === "1";

    function isIpad() {
        const ua = navigator.userAgent || "";
        return /iPad/i.test(ua) ||
            (/Macintosh/i.test(ua) && navigator.maxTouchPoints > 1);
    }

    function installed() {
        return navigator.standalone === true ||
            (typeof window.matchMedia === "function" &&
             (window.matchMedia("(display-mode: standalone)").matches ||
              window.matchMedia("(display-mode: fullscreen)").matches));
    }

    function embedded() {
        try { return window.top !== window.self; }
        catch (_) { return true; }
    }

    function readState() {
        try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"); }
        catch (_) { return null; }
    }

    function saveState(value) {
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify(value)); }
        catch (_) { /* Non-persistent private browsing is fine. */ }
    }

    // No install instructions in standalone mode. Never claim that adding
    // itch.io's outer page to the Home Screen will install our game.
    if (installed() || (!isIpad() && !forced)) return;
    if (embedded() && !DIRECT_URL && !forced) return;

    const stored = readState();
    if (!forced && stored && (stored.dismissed ||
        (Number.isFinite(stored.lastShown) &&
         Date.now() - stored.lastShown < REPEAT_AFTER_DAYS * 86400000))) return;

    function showHint() {
        if (installed() || document.getElementById("wg-home-screen-tip")) return;
        if (!document.body || !document.head) return;

        const de = /^(de)(-|$)/i.test(navigator.language || "");
        const inIframe = embedded();
        const style = document.createElement("style");
        style.id = "wg-home-screen-tip-style";
        style.textContent = `
            #wg-home-screen-tip {
                position: fixed;
                top: calc(12px + env(safe-area-inset-top, 0px));
                right: calc(12px + env(safe-area-inset-right, 0px));
                box-sizing: border-box;
                max-width: min(330px, calc(100vw - 26px));
                padding: 10px 9px 10px 12px;
                border-radius: 12px;
                color: white;
                background: rgba(18, 40, 38, .94);
                box-shadow: 0 3px 15px rgba(0,0,0,.18);
                font: 13px/1.38 -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
                display: flex;
                align-items: flex-start;
                gap: 9px;
                pointer-events: auto;
                z-index: 2147483647;
                -webkit-user-select: none;
                user-select: none;
                -webkit-touch-callout: none;
                touch-action: manipulation;
            }
            #wg-home-screen-tip strong { display: block; margin-bottom: 3px; }
            #wg-home-screen-tip p { margin: 0; }
            #wg-home-screen-tip a { color: #b4e8ff; text-decoration: underline; }
            #wg-home-screen-tip button {
                border: 0; border-radius: 8px; background: rgba(255,255,255,.14);
                color: #fff; font: 21px/30px -apple-system, sans-serif;
                width: 30px; height: 30px; padding: 0; cursor: pointer;
                flex: 0 0 30px;
            }
        `;
        const tip = document.createElement("aside");
        tip.id = "wg-home-screen-tip";
        tip.setAttribute("role", "status");
        tip.setAttribute("aria-label", de ? "App-Hinweis" : "App tip");

        const content = document.createElement("div");
        const heading = document.createElement("strong");
        const body = document.createElement("p");
        if (inIframe && DIRECT_URL) {
            heading.textContent = de ? "WasteGame als App spielen" : "Play WasteGame as an app";
            const link = document.createElement("a");
            link.href = DIRECT_URL;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = de ? "Eigene Spielseite öffnen" : "Open the game directly";
            body.appendChild(link);
        } else {
            heading.textContent = de ? "Ohne Browserleisten spielen" : "Play without browser bars";
            body.textContent = de
                ? "In Safari: Teilen → Zum Home-Bildschirm → Als Web-App öffnen."
                : "In Safari: Share → Add to Home Screen → Open as Web App.";
        }
        content.append(heading, body);

        const close = document.createElement("button");
        close.type = "button";
        close.textContent = "×";
        close.setAttribute("aria-label", de ? "Nicht mehr anzeigen" : "Don't show again");
        tip.append(content, close);

        let timer;
        function hide(permanent) {
            window.clearTimeout(timer);
            tip.remove();
            style.remove();
            if (permanent) saveState({ dismissed: true, lastShown: Date.now() });
        }
        close.addEventListener("click", () => hide(true));
        document.head.appendChild(style);
        document.body.appendChild(tip);
        if (!forced) saveState({ dismissed: false, lastShown: Date.now() });
        timer = window.setTimeout(() => hide(false), VISIBLE_FOR_MS);
    }

    const start = () => window.setTimeout(showHint, forced ? 200 : SHOW_DELAY_MS);
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start, { once: true });
    } else {
        start();
    }
})();
