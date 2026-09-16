/**
 * Sopline SPA Navigation & Smart Transition Engine (v2.1)
 * 
 * Provides native mobile-app-like page transitions without screen flickering (pir-piramasdan):
 * - Keeps Header, Sidebar, and Mobile Bottom Bar static in the DOM (no full-page reloads).
 * - Smoothly swaps `<main>` container content with hardware-accelerated animations.
 * - Synchronizes `<head>` styles & CSS links ({% block head %}) dynamically so pages are 100% styled.
 * - Handles inline scripts, DOMContentLoaded listeners, jQuery ready events, and Select2/Chart.js.
 * - Preserves browser history (Back/Forward buttons) via HTML5 pushState.
 * - Graceful fallback to native browser navigation if any network/parsing issue occurs.
 */
(function () {
    'use strict';

    if (typeof window === 'undefined' || typeof document === 'undefined') return;

    // Prevent Chrome DevTools Live Metrics crash on Soft Navigations (where t.entries[0] is undefined)
    try {
        if (!('devToolsReportSoftNavs' in window)) {
            Object.defineProperty(window, 'devToolsReportSoftNavs', {
                configurable: true,
                enumerable: false,
                get: function () { return false; },
                set: function () {}
            });
        }
    } catch (e) {}

    // Global guard to prevent unhandled TypeError from DevTools / web-vitals internal INP reporter
    window.addEventListener('error', function (event) {
        if (event && (
            (event.message && event.message.indexOf("reading 'startTime'") !== -1) ||
            (event.error && event.error.message && event.error.message.indexOf("reading 'startTime'") !== -1)
        )) {
            event.preventDefault();
            event.stopImmediatePropagation();
            return true;
        }
    }, true);

    // Cache of prefetched HTML text for instant rendering
    var pageCache = new Map();
    var hoverTimer = null;
    var progressBar = null;
    var progressInterval = null;
    var currentProgress = 0;
    var isNavigating = false;

    // Automatic tracking and cleanup of page background polling timers
    var trackedIntervals = new Set();
    var nativeSetInterval = window.setInterval;
    var nativeClearInterval = window.clearInterval;

    window.setInterval = function (fn, delay) {
        var args = Array.prototype.slice.call(arguments, 2);
        var id = nativeSetInterval.apply(window, [fn, delay].concat(args));
        if (id !== progressInterval) {
            trackedIntervals.add(id);
        }
        return id;
    };

    window.clearInterval = function (id) {
        trackedIntervals.delete(id);
        return nativeClearInterval.call(window, id);
    };

    function cleanupPageTimers() {
        if (window._chatPollInterval) {
            nativeClearInterval.call(window, window._chatPollInterval);
            window._chatPollInterval = null;
        }
        trackedIntervals.forEach(function (id) {
            nativeClearInterval.call(window, id);
        });
        trackedIntervals.clear();
    }

    // 1. Top Progress Bar
    function getProgressBar() {
        if (!progressBar) {
            progressBar = document.getElementById('instant-page-progress');
            if (!progressBar) {
                progressBar = document.createElement('div');
                progressBar.id = 'instant-page-progress';
                document.body.appendChild(progressBar);
            }
        }
        return progressBar;
    }

    function startProgressBar() {
        var bar = getProgressBar();
        if (!bar) return;

        clearInterval(progressInterval);
        currentProgress = 20;
        bar.style.width = currentProgress + '%';
        bar.classList.add('animating');

        progressInterval = setInterval(function () {
            if (currentProgress < 70) {
                currentProgress += 12;
            } else if (currentProgress < 88) {
                currentProgress += 4;
            } else if (currentProgress < 96) {
                currentProgress += 1;
            }
            bar.style.width = currentProgress + '%';
        }, 100);
    }

    function finishProgressBar() {
        var bar = getProgressBar();
        if (!bar) return;

        clearInterval(progressInterval);
        currentProgress = 100;
        bar.style.width = '100%';

        setTimeout(function () {
            bar.classList.remove('animating');
            setTimeout(function () {
                bar.style.width = '0%';
                currentProgress = 0;
            }, 200);
        }, 150);
    }

    // 2. Link Eligibility Check
    function getValidAnchor(target) {
        var el = target;
        while (el && el.tagName !== 'A') {
            el = el.parentElement;
        }
        return el;
    }

    function isSpaLink(anchor) {
        if (!anchor || !anchor.href) return false;

        // Skip non-GET or special attributes
        if (anchor.hasAttribute('download')) return false;
        if (anchor.target && anchor.target !== '_self') return false;
        if (anchor.hasAttribute('data-no-spa') || anchor.hasAttribute('data-no-instant')) return false;
        if (anchor.getAttribute('data-bs-toggle') || anchor.getAttribute('data-toggle')) return false;

        var rawHref = anchor.getAttribute('href') || '';
        if (rawHref.startsWith('#') || rawHref.startsWith('javascript:') || rawHref.startsWith('mailto:') || rawHref.startsWith('tel:')) {
            return false;
        }

        var url;
        try {
            url = new URL(anchor.href, window.location.href);
        } catch (e) {
            return false;
        }

        // Only same origin
        if (url.origin !== window.location.origin) return false;

        // Skip dangerous or state mutation endpoints
        var dangerousPattern = /(logout|delete|remove|destroy|clear|export|download|unblock|block|toggle)/i;
        if (dangerousPattern.test(url.pathname)) {
            return false;
        }

        return true;
    }

    // 3. Security Token & Network Obfuscation
    function getCsrfToken() {
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        if (match) return match[1];
        var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return input ? input.value : '';
    }

    function encodeSafeToken(pathStr) {
        try {
            return btoa(unescape(encodeURIComponent(pathStr)));
        } catch (e) {
            return btoa(pathStr);
        }
    }

    async function fetchPageSecurely(targetUrl) {
        var parsed = new URL(targetUrl, window.location.origin);
        var targetPath = parsed.pathname + parsed.search;
        var token = encodeSafeToken(targetPath);

        var csrf = getCsrfToken();
        var formData = new FormData();
        formData.append('token', token);

        try {
            var response = await fetch('/api/spa-gate/', {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrf,
                    'X-Sopline-Token': token
                },
                body: formData
            });

            if (response.ok && response.headers.get('X-Sopline-Protected') === '1') {
                return response;
            }
        } catch (e) {
            // fallback to direct request
        }

        return await fetch(targetUrl, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
    }

    // 4. Smart Prefetch (Warm Cache)
    var isPrefetching = false;
    function prefetchUrl(urlStr) {
        if (!urlStr || pageCache.has(urlStr) || isPrefetching || isNavigating) return;
        var connection = navigator.connection;
        if (connection && (connection.saveData || /2g/.test(connection.effectiveType || ''))) return;

        isPrefetching = true;
        fetchPageSecurely(urlStr)
            .then(function (res) {
                if (res && res.ok) {
                    return res.text();
                }
                return null;
            })
            .then(function (html) {
                if (html) {
                    pageCache.set(urlStr, { html: html, time: Date.now() });
                }
            })
            .catch(function () {})
            .finally(function () {
                isPrefetching = false;
            });
    }

    // 4. Synchronize Page Head Styles & CSS Links ({% block head %})
    function syncPageHead(htmlText, doc) {
        // Remove existing dynamic styles & link tags added by previous SPA navigations
        document.querySelectorAll('[data-spa-head]').forEach(function (el) {
            el.remove();
        });

        // 1. Try explicit boundary marker first: <!-- SPA_PAGE_HEAD_START --> ... <!-- SPA_PAGE_HEAD_END -->
        var headMatch = htmlText.match(/<!-- SPA_PAGE_HEAD_START -->([\s\S]*?)<!-- SPA_PAGE_HEAD_END -->/);
        var headHtml = headMatch ? headMatch[1].trim() : '';

        if (headHtml) {
            var temp = document.createElement('div');
            temp.innerHTML = headHtml;
            Array.from(temp.children).forEach(function (node) {
                var clone = node.cloneNode(true);
                clone.setAttribute('data-spa-head', 'true');
                document.head.appendChild(clone);
            });
        } else if (doc && doc.head) {
            // Fallback: extract page-specific style and link tags from doc.head
            Array.from(doc.head.children).forEach(function (node) {
                var tag = node.tagName.toLowerCase();
                if (tag === 'style' || (tag === 'link' && node.rel === 'stylesheet')) {
                    var text = node.textContent || '';
                    var href = node.getAttribute('href') || '';
                    // Skip base layout global stylesheets
                    var isBase = text.includes('form-control') ||
                                 text.includes('instant-page-progress') ||
                                 href.includes('bootstrap-icons');
                    if (!isBase) {
                        var clone = node.cloneNode(true);
                        clone.setAttribute('data-spa-head', 'true');
                        document.head.appendChild(clone);
                    }
                }
            });
        }

        // Trigger Tailwind CSS re-scan if available
        if (window.tailwind && typeof window.tailwind.scan === 'function') {
            try { window.tailwind.scan(); } catch (e) {}
        }
    }

    // 5. Script Execution Engine for SPA Container
    async function executeScripts(container) {
        var scripts = Array.from(container.querySelectorAll('script'));
        for (var oldScript of scripts) {
            // Keep data scripts in the DOM untouched (JSON data, templates, etc.)
            var scriptType = (oldScript.getAttribute('type') || '').trim().toLowerCase();
            if (scriptType && !['text/javascript', 'application/javascript', 'module'].includes(scriptType)) {
                continue;
            }

            oldScript.remove(); // Remove original non-executed script tag

            var newScript = document.createElement('script');
            Array.from(oldScript.attributes).forEach(function (attr) {
                newScript.setAttribute(attr.name, attr.value);
            });

            if (oldScript.src) {
                var alreadyLoaded = Array.from(document.querySelectorAll('script[src]'))
                    .some(function (s) { return s.src === newScript.src; });

                if (!alreadyLoaded) {
                    await new Promise(function (resolve) {
                        newScript.onload = resolve;
                        newScript.onerror = resolve;
                        document.head.appendChild(newScript);
                    });
                }
            } else {
                var scriptContent = oldScript.textContent;

                // Capture any DOMContentLoaded listener registered in this inline script
                var originalAddEventListener = document.addEventListener;
                var deferredListeners = [];

                document.addEventListener = function (type, listener, options) {
                    if (type === 'DOMContentLoaded') {
                        deferredListeners.push(listener);
                        return;
                    }
                    return originalAddEventListener.call(document, type, listener, options);
                };

                try {
                    // Safe execution via indirect eval in global scope so top-level let/const declarations
                    // don't collide or throw SyntaxError across SPA navigations
                    (0, eval)(scriptContent);
                } catch (err) {
                    console.error('SPA script execution warning:', err);
                } finally {
                    document.addEventListener = originalAddEventListener;
                }

                // Execute deferred listeners immediately
                deferredListeners.forEach(function (listener) {
                    try {
                        listener(new Event('DOMContentLoaded'));
                    } catch (e) {
                        console.error('SPA listener execution error:', e);
                    }
                });
            }
        }
    }

    // 6. Sidebar & UI Sync
    function syncNavigationState(doc) {
        // Sync Sidebar Navigation
        var currentNav = document.querySelector('#app-sidebar nav');
        var newNav = doc.querySelector('#app-sidebar nav');
        if (currentNav && newNav) {
            currentNav.innerHTML = newNav.innerHTML;
        }

        // Sync Mobile Bottom Bar
        var currentBottom = document.querySelector('.bottom-nav');
        var newBottom = doc.querySelector('.bottom-nav');
        if (currentBottom && newBottom) {
            currentBottom.innerHTML = newBottom.innerHTML;
        }

        // Re-evaluate submenus open/rotate state
        ['practice-submenu', 'guideline-status-submenu', 'sa-orgs-submenu', 'org-workers-submenu'].forEach(function (menuId) {
            var menu = document.getElementById(menuId);
            var chevron = document.getElementById(menuId.replace('submenu', 'chevron'));
            if (menu && chevron) {
                chevron.style.transform = menu.classList.contains('hidden') ? '' : 'rotate(180deg)';
            }
        });

        // Close mobile drawer if open
        if (window.closeSidebar) {
            window.closeSidebar();
        }

        // Clean up leftover modal backdrops
        document.querySelectorAll('.modal-backdrop').forEach(function (el) { el.remove(); });
        document.body.classList.remove('modal-open');
        document.body.style.removeProperty('overflow');
        document.body.style.removeProperty('padding-right');
    }

    // 7. Django Messages Toast Notification Trigger
    function triggerDjangoMessages() {
        var box = document.getElementById('django-messages');
        if (!box || typeof Swal === 'undefined') return;
        var toast = Swal.mixin({
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer: 2600,
            timerProgressBar: true,
            customClass: { popup: 'swal-toast-small' }
        });
        var iconMap = { success: 'success', error: 'error', warning: 'warning', info: 'info' };
        box.querySelectorAll('div[data-tag]').forEach(function (el) {
            toast.fire({ icon: iconMap[el.dataset.tag] || 'info', text: el.dataset.text });
        });
    }

    // 8. Core SPA Navigation Handler
    async function navigateTo(targetUrl, pushState) {
        if (isNavigating) return;
        isNavigating = true;

        // Immediately cancel any polling/intervals from the previous page
        cleanupPageTimers();

        startProgressBar();

        var currentMain = document.querySelector('main');
        if (currentMain) {
            currentMain.classList.remove('spa-transition-in');
            currentMain.classList.add('spa-transition-out');
        }

        try {
            var htmlText = null;
            var cached = pageCache.get(targetUrl);
            // Cache valid for 30 seconds
            if (cached && (Date.now() - cached.time < 30000)) {
                htmlText = cached.html;
            } else {
                var response = await fetchPageSecurely(targetUrl);

                if (!response.ok) {
                    throw new Error('HTTP status ' + response.status);
                }

                // If redirected (e.g. to login)
                if (response.redirected && response.url !== targetUrl) {
                    window.location.href = response.url;
                    return;
                }

                htmlText = await response.text();
            }

            var parser = new DOMParser();
            var doc = parser.parseFromString(htmlText, 'text/html');
            var newMain = doc.querySelector('main');

            if (!newMain || !currentMain) {
                // Fallback to traditional navigation
                window.location.href = targetUrl;
                return;
            }

            // Update page title
            if (doc.title) {
                document.title = doc.title;
            }

            // Sync URL in address bar
            if (pushState) {
                window.history.pushState({ url: targetUrl }, '', targetUrl);
            }

            // Synchronize page head styles ({% block head %})
            syncPageHead(htmlText, doc);

            // Clean up any remaining modals, backdrops or modal state
            document.querySelectorAll('body > .modal').forEach(function (m) {
                var bsModal = (window.bootstrap && bootstrap.Modal) ? bootstrap.Modal.getInstance(m) : null;
                if (bsModal) {
                    try { bsModal.hide(); } catch (_) {}
                    try { bsModal.dispose(); } catch (_) {}
                }
                m.remove();
            });
            document.querySelectorAll('.modal-backdrop').forEach(function (b) {
                b.remove();
            });
            document.body.classList.remove('modal-open');
            document.body.style.removeProperty('overflow');
            document.body.style.removeProperty('padding-right');

            // Smoothly replace main content
            currentMain.className = newMain.className;
            currentMain.innerHTML = newMain.innerHTML;

            // Sync menu & sidebar items
            syncNavigationState(doc);

            // Trigger smooth entrance animation
            currentMain.classList.remove('spa-transition-out');
            currentMain.classList.add('spa-transition-in');
            setTimeout(function () {
                currentMain.classList.remove('spa-transition-in');
            }, 250);

            // Scroll to top
            currentMain.scrollTop = 0;
            window.scrollTo(0, 0);

            // Execute scripts inside the new page
            await executeScripts(currentMain);

            // Trigger events safely
            try {
                document.dispatchEvent(new Event('DOMContentLoaded'));
            } catch (e) {}
            if (window.jQuery) {
                try {
                    window.jQuery(document).trigger('ready');
                } catch (e) {}
            }

            // Show any Django message alerts
            triggerDjangoMessages();

        } catch (error) {
            console.warn('SPA navigation fallback to standard reload:', error);
            window.location.href = targetUrl;
        } finally {
            finishProgressBar();
            isNavigating = false;
        }
    }

    // 8. Global Modal Handler (Prevents Stacking Context / Dark Backdrop Overlay Trap)
    document.addEventListener('show.bs.modal', function (event) {
        var modal = event.target;
        if (modal && modal.parentElement !== document.body) {
            document.body.appendChild(modal);
        }
    });

    // 9. Event Listeners
    // Hover / Touch intent prefetch (300ms debounce to avoid spamming the backend)
    document.addEventListener('pointerover', function (e) {
        if (isNavigating) return;
        var anchor = getValidAnchor(e.target);
        if (!anchor || !isSpaLink(anchor)) return;

        clearTimeout(hoverTimer);
        hoverTimer = setTimeout(function () {
            if (!isNavigating) {
                prefetchUrl(anchor.href);
            }
        }, 300);
    }, { passive: true });

    document.addEventListener('pointerout', function () {
        clearTimeout(hoverTimer);
    });

    document.addEventListener('touchstart', function (e) {
        if (isNavigating) return;
        var anchor = getValidAnchor(e.target);
        if (!anchor || !isSpaLink(anchor)) return;
        prefetchUrl(anchor.href);
    }, { passive: true });

    // Click interceptor
    document.addEventListener('click', function (e) {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.defaultPrevented || e.button !== 0) {
            return;
        }

        var anchor = getValidAnchor(e.target);
        if (!anchor || !isSpaLink(anchor)) return;

        var currentUrl = new URL(window.location.href);
        var targetUrl = new URL(anchor.href, window.location.href);

        // Same exact URL: no need to reload
        if (currentUrl.pathname === targetUrl.pathname && currentUrl.search === targetUrl.search) {
            e.preventDefault();
            return;
        }

        e.preventDefault();
        navigateTo(anchor.href, true);
    });

    // Browser Back / Forward navigation
    window.addEventListener('popstate', function () {
        navigateTo(window.location.href, false);
    });

    // Initial load cleanup
    finishProgressBar();

    // Export API
    window.SoplineSPA = {
        navigateTo: navigateTo,
        prefetch: prefetchUrl,
        syncPageHead: syncPageHead
    };
})();
