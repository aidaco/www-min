self.addEventListener("push", (event) => {
  const payload = event.data.json();
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      vibrate: [200, 100, 200, 100, 200, 100, 200]
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    clients.openWindow("/admin.html");
  },
  false,
);
