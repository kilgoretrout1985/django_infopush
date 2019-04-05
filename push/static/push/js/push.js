// https://developers.google.com/web/updates/2015/03/push-notifications-on-the-open-web
// https://developers.google.com/web/fundamentals/push-notifications/how-push-works

(function() {
    var push_is_enabled = false;
    
    function push_supported() {
        // Service workers isn't supported on this browser
        if (!('serviceWorker' in navigator)) {
            return false;
        }
        
        // Push isn't supported on this browser
        if (!('PushManager' in window)) {
            return false;
        }
        
        if (!('showNotification' in ServiceWorkerRegistration.prototype)) {
            console.warn('Notifications aren\'t supported.');
            return false;
        }
        
        // Check the current Notification permission.  
        // If its denied, it's a permanent block until user changes the permission
        // https://developers.google.com/web/updates/2015/05/notifying-you-of-changes-to-notifications#android-notifications
        if ('Notification' in window && window.Notification &&
            Notification.permission === 'denied') {
            console.warn('User has blocked notifications.');
            return false;
        }
        
        return true;
    }
    
    // Once the service worker is registered set the initial state  
    function push_initialise() {
        // We need the service worker registration to check for a subscription  
        navigator.serviceWorker.ready
        .then(function(serviceWorkerRegistration) {
            // Do we already have a push message subscription?
            return serviceWorkerRegistration.pushManager.getSubscription();
        })
        .then(function(subscription) {
            // Enable any UI which subscribes / unsubscribes from messages
            var pushButton = document.querySelector('.js-push-button');  
            if (pushButton) { pushButton.disabled = false; }
            
            if (subscription) {
                console.debug('Got subscription on initialise state ', subscription);
                // Keep your server in sync with the latest subscription id
                push_save_on_server(subscription);
                // Set your UI to show they have subscribed for push messages
                if (pushButton) {
                    pushButton.textContent = django_infopush_js_dynamic_vars.off_button_label;
                    push_is_enabled = true;
                }
            } else if (!pushButton && !getCookie('push_dnd')) {
                // на странице где есть кнопка управления, автомата нет
                // кука значит, чел. уже подписывался и, видимо, отписался
                
                // если чел. не подписан, спросим его об этом автоматически
                // задержка, чтобы не сразу все вываливтаь на пользователя -
                // дадим освоиться на странице и отсеем тех, кто сразу уходит
                console.debug('No subscription, need to push_subscribe()');
                setTimeout(function() { push_subscribe(); }, 12000);
            }
        })
        .catch(function(e) {
            console.error('Error during getSubscription()', e);
        });
    }
    
    // from https://github.com/GoogleChromeLabs/web-push-codelab/issues/46
    function urlBase64ToUint8Array(base64String) {
        var padding = '='.repeat((4 - base64String.length % 4) % 4);
        var base64 = (base64String + padding)
            .replace(/\-/g, '+')
            .replace(/_/g, '/');
    
        var rawData = window.atob(base64);
        var outputArray = new Uint8Array(rawData.length);
    
        for (var i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }
    
    function push_subscribe() {
        // Disable the button so it can't be changed while  
        // we process the permission request  
        var pushButton = document.querySelector('.js-push-button');  
        if(pushButton) { pushButton.disabled = true; }
        
        navigator.serviceWorker.ready
        .then(function(serviceWorkerRegistration) {
            return serviceWorkerRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(
                    django_infopush_js_dynamic_vars.vapid_public_key
                )
            });
        })
        .then(function(subscription) {
            // The subscription was successful
            if(pushButton) {
                push_is_enabled = true;
                pushButton.textContent = django_infopush_js_dynamic_vars.off_button_label;
                pushButton.disabled = false;
            }
            // Send the subscription id to your server  
            // and save it to send a push message at a later date
            push_save_on_server(subscription);
            // delete "do not disturb" cookie
            setCookie('push_dnd', '', {expires: -86400, path: '/'});
        })
        .catch(function(e) {
            if ('Notification' in window && window.Notification &&
                Notification.permission === 'denied') {  
                // The user denied the notification permission which  
                // means we failed to subscribe and the user will need  
                // to manually change the notification permission to  
                // subscribe to push messages
                console.warn('Permission for Notifications was denied');
                if(pushButton) { pushButton.disabled = true; }
            } else {
                // A problem occurred with the subscription; common reasons  
                // include network errors, and lacking gcm_sender_id and/or  
                // gcm_user_visible_only in the manifest.  
                console.error('Unable to subscribe to push.', e);
                if(pushButton) {
                    pushButton.disabled = false;
                    pushButton.textContent = django_infopush_js_dynamic_vars.on_button_label;
                }
            }
        });
    }
    
    function setCookie(e,t,n){n=n||{};var r=n.expires;if(typeof r=="number"&&r){var i=new Date;i.setTime(i.getTime()+r*1e3);r=n.expires=i}if(r&&r.toUTCString){n.expires=r.toUTCString()}t=encodeURIComponent(t);var s=e+"="+t;for(var o in n){s+="; "+o;var u=n[o];if(u!==true){s+="="+u}}document.cookie=s}
    function getCookie(e){var t=document.cookie.match(new RegExp("(?:^|; )"+e.replace(/([\.$?*|{}\(\)\[\]\\\/\+^])/g,"\\$1")+"=([^;]*)"));return t?decodeURIComponent(t[1]):undefined}
    
    function find_endpoint(subscription) {
        return (('subscriptionId' in subscription) && !('endpoint' in subscription))
                    ? subscription.subscriptionId : subscription.endpoint;
    }
    
    function find_keys(subscription) {
        var rawKey = subscription.getKey ? subscription.getKey('p256dh') : '';
        var key = rawKey ? btoa(String.fromCharCode.apply(null, new Uint8Array(rawKey))) : '';
        var rawAuthSecret = subscription.getKey ? subscription.getKey('auth') : '';
        var authSecret = rawAuthSecret ? btoa(String.fromCharCode.apply(null, new Uint8Array(rawAuthSecret))) : '';
        return [key, authSecret];
    }
    
    function find_timezone() {
        // based on the fact that you have ALREADY loaded jstz on your web-page
        // https://bitbucket.org/pellepim/jstimezonedetect
        if (typeof jstz !== 'undefined') {
            var tz = jstz.determine();
            if(tz) {
                var tz_name = tz.name();
                if(tz_name) {
                    return tz_name;
                }
            }
        }
        return '';
    }
    
    // hash the most important parts of subscription object
    // so later we can understand if it changes
    function push_hash(endpoint, key, auth_secret, tz) {
        // http://stackoverflow.com/questions/7616461/generate-a-hash-from-string-in-javascript-jquery
        function hash_string(s) {
            var hash = 0, chr;
            if (s.length === 0) return hash;
            for (var i = 0; i < s.length; i++) {
                chr   = s.charCodeAt(i);
                hash  = ((hash << 5) - hash) + chr;
                hash |= 0; // Convert to 32bit integer
            }
            return hash.toString();
        }
        
        return hash_string( [endpoint, key, auth_secret, tz].join('_') );
    }
    
    function push_save_on_server(subscription) {
        console.log('Got subscription object to save.', subscription);
        
        var endpoint = find_endpoint(subscription);
        var keys = find_keys(subscription);
        var key = keys[0];
        var auth_secret = keys[1];
        var timezone = find_timezone();
        var hash = push_hash(endpoint, key, auth_secret, timezone);
        if (hash == getCookie('push_hash')) {
            // На каждом запросе, есди чел. подписан, мы получаем его
            // id подписки. Он может измениться, если юзер отписался
            // и переподписался сам через браузер. Соответственно проверка, что
            // на сервере и так актуальная инфа, чтобы не мучать его запросами.
            console.log('Subscription already actual, save not needed.');
            return true;
        }
        
        var data = new FormData();
        data.append('endpoint', endpoint);
        if (key !== '') { data.append('key', key); }
        if (auth_secret !== '') { data.append('auth_secret', auth_secret); }
        if (timezone) { data.append('timezone', timezone); }
        var csrftoken = getCookie('csrftoken');
        var request = new Request(django_infopush_js_dynamic_vars.save_url, {
            'method': 'POST',
            'cache': 'no-cache',
            'body': data,
            'credentials': 'include',
            'headers': new Headers({ 'X-CSRFToken': csrftoken })
        });
        
        fetch(request)
        .then(function(response) {
            if(response.ok) {
                setCookie('push_hash', hash, {expires: 7*24*3600, path: '/'});
                console.log('Successfully saved subscription.');
            } else {
                console.warn('Network response on subscription save was not ok.', response);
            }
        })
        .catch(function(e) {
            console.error('Error while saving subscription.', e);
        });
    }
    
    function push_deactivate_on_server(subscription) {
        console.log('Got subscription object to deactivate.', subscription);
        
        var data = new FormData();
        data.append('endpoint', find_endpoint(subscription));
        var csrftoken = getCookie('csrftoken');
        var request = new Request(django_infopush_js_dynamic_vars.deactivate_url, {
            'method': 'POST',
            'cache': 'no-cache',
            'body': data,
            'credentials': 'include',
            'headers': new Headers({ 'X-CSRFToken': csrftoken })
        });
        
        fetch(request)
        .then(function(response) {
            if(response.ok) {
                console.log('Successfully deactivated subscription.');
            } else {
                console.warn('Network response on subscription deactivation was not ok.', response);
            }
        })
        .catch(function(e) {
            console.error('Error while deactivating subscription.', e);
        });
    }
    
    function push_unsubscribe() {
        var pushButton = document.querySelector('.js-push-button');
        // this function is always called via the button
        pushButton.disabled = true;
        
        navigator.serviceWorker.ready
        .then(function(serviceWorkerRegistration) {
            // To unsubscribe from push messaging, you need get the
            // subscription object, which you can call unsubscribe() on.
            return serviceWorkerRegistration.pushManager.getSubscription();
        })
        .then(function(subscription) {
            console.log('Got subscription to unsubscribe: ', subscription);
            
            // Check we have a subscription to unsubscribe
            if (!subscription) {
                // No subscription object, so set the state  
                // to allow the user to subscribe to push  
                push_is_enabled = false;
                pushButton.disabled = false;
                pushButton.textContent = django_infopush_js_dynamic_vars.on_button_label;
                throw new Error('No subscription object to unsubscribe');
            }
            
            // We have a subscription, so call unsubscribe on it  
            return Promise.all([ subscription.unsubscribe(), subscription ]);
        })
        .then(function(data) { 
            var unsubscribed = data[0]; // boolean
            var subscription = data[1]; 
            if (unsubscribed) {
                // Make a request to your server to remove
                // the subscription from your data store so you
                // don't attempt to send them push messages anymore
                push_deactivate_on_server(subscription);
                setCookie('push_dnd', '1', {expires: 365*86400, path: '/'});
                pushButton.disabled = false;
                pushButton.textContent = django_infopush_js_dynamic_vars.on_button_label;
                push_is_enabled = false;
            } else {
                // We failed to unsubscribe, this can lead to  
                // an unusual state, so may be best to remove
                // the users data from your data store and
                // inform the user that you have done so
                pushButton.disabled = false;
            }
        })
        .catch(function(e) {
            console.error('Error thrown while unsubscribing from push messaging.', e);  
        });
    }
    
    document.addEventListener("DOMContentLoaded", function() {
        if(!push_supported()) { return; }
        
        var pushButton = document.querySelector('.js-push-button');
        if (pushButton) {
            pushButton.addEventListener('click', function() {
                if (push_is_enabled) {
                    push_unsubscribe();
                } else {
                    push_subscribe();
                }
            });
        }
        navigator.serviceWorker.register('/service-worker.js')
        .then(function(serviceWorkerRegistration) {
            // Listen for any messages from the service worker.
            // https://serviceworke.rs/message-relay_index_doc.html
            serviceWorkerRegistration.addEventListener('message', function(event) {
                console.debug('push.js got message from service worker with ' +
                            'the following event.data:', event.data);
                if (event.data.message == 'push_subscribe') {
                    push_subscribe();
                }
            });
            
            // the actual work
            push_initialise();
        });
    });
})();