{% load i18n %}

//{# https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerGlobalScope/skipWaiting #}
self.addEventListener('install', function(event) {
    self.skipWaiting();
});


//{# https://developer.mozilla.org/en-US/docs/Web/API/Clients/claim #}
self.addEventListener('activate', function(event) {
    if ('clients' in self && self.clients.claim) {
        event.waitUntil(self.clients.claim());
    }
});


//{# https://stackoverflow.com/questions/46541071/progressive-web-app-does-not-work-offline-error #}
self.addEventListener('fetch', function(event) {});


//{# https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerGlobalScope/onpushsubscriptionchange #}
//{# https://serviceworke.rs/push-subscription-management_service-worker_doc.html #}
self.addEventListener('pushsubscriptionchange', function(event) {
    //{# do something, usually resubscribe to push and send the new subscription #}
    //{# details back to the server via XHR or Fetch. #}
    console.debug('pushsubscriptionchange event called:', event);
    
    event.waitUntil(
        //{# https://serviceworke.rs/message-relay_service-worker_doc.html #}
        self.clients.matchAll()
        .then(function(clientList) {
            clientList.forEach(function(client) {
                //{# can't use fetch here because we need django csrf #}
                //{# cookie which is not available in service worker #}
                client.postMessage({ message: 'push_subscribe' });
            });
        })
    );
});


self.addEventListener('push', function(event) {
    console.log('Service worker got push message: ', event);

    var promises;
    
    function make_notification_options(backend_data) {
        var opt = {
            requireInteraction: true,
            renotify: true,
            body: backend_data.message,
            icon: backend_data.icon,
            tag: backend_data.tag,
            data: {
                url: backend_data.url,
                closings_stat_url: backend_data.closings_stat_url
            }
        };
        if (backend_data.image) {
            opt.image = backend_data.image;
        }
        return opt;
    }
    
    var payload = (event.data) ? event.data.json() : null;
    console.log('Payload received: ', payload);
    if (payload) {
        var options = make_notification_options(payload);
        promises = fetch(payload.views_stat_url, {
            method: 'GET',
            credentials: 'include'
        })
        .then(function(response) {
            return self.registration.showNotification(payload.title, options);
        })
        .catch(function(e) {
            console.error('Unable to save statistics', e);
            //{# still show notification because we have to #}
            //{# and error in stats is not so important actually #}
            return self.registration.showNotification(payload.title, options);
        });
    //{# for clients which don't support payload and encryption #}
    } else {
        //{# This is a Django template call, because you are actually #}
        //{# viewing a django template file, not static js. #}
        var last_notification_url = '{% url "push_last_notification" %}';
        promises = fetch(last_notification_url, {
            method: 'GET',
            credentials: 'include'
        })
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            console.debug('Data from '+last_notification_url+': ', data);
            if (data.error || !data.notification) {
                console.error('The API returned an error.', data.error);  
                throw new Error();
            }
            return self.registration.showNotification(
                data.notification.title,
                make_notification_options(data.notification)
            );
        })
        .catch(function(e) {
            console.error('Unable to retrieve data', e);
            //{# You'll notice that we show a notification even when there is an #}
            //{# error. This is because if we don't, Chrome will show it's own #}
            //{# generic notification. #}
            return self.registration.showNotification('{% trans "Error occurred" %}', {
                body: '{% trans "We were unable to get information for this push message" %}',
                tag: 'notification-error'
            });
        });
    }
    event.waitUntil(promises);
});


function escapeRegExp(s) {
    return String(s).replace(/([.*+?^=!:${}()|\[\]\/\\])/g, "\\$1");
}


self.addEventListener('notificationclick', function(event) {
    console.log('On notification click event: ', event);
    
    var notification = event.notification;
    notification.close();
    var url = (notification.data && 'url' in notification.data) ? notification.data.url : '/';
    
    //{# This looks to see if the current url is already open and focuses if it is #}
    event.waitUntil(
        clients.matchAll({ type: "window" })
        .then(function(clientList) {
            //{# client.url is an absolute url in console.log, but we supply #}
            //{# relative url in our json and in google manuals client.url is #}
            //{# relative (no domain). Fight this complexity with regexps )) #}
            var match_url = String(url).replace(/\?from\=[^\?\&\/]+$/, '');
            var url_re = new RegExp(
                "^(?:[hH]{1}[tT]{2}[pP]{1}[sS]{0,1}\\:\\/\\/[^\\/]{4,})?" +
                "(?:" + escapeRegExp(match_url) + "|" + escapeRegExp(url) + ")$"
            );
            for (var i = 0; i < clientList.length; i++) {
                var client = clientList[i];
                if ('focus' in client && url_re.test(client.url)) {
                    return client.focus();
                }
            }
            return clients.openWindow(url);
        })
    );
});


//{# called if the user dismisses one of your notifications #}
//{# (i.e. the user clicks the cross or swipes the notification away) #}
self.addEventListener('notificationclose', function(event) {
    console.log('On notification closed event: ', event);
    
    event.waitUntil(
        fetch(event.notification.data.closings_stat_url, {
            method: 'GET',
            credentials: 'include'
        })
    );
});
