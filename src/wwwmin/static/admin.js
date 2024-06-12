function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - base64String.length % 4) % 4);
    var base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/');

    var rawData = window.atob(base64);
    return rawToUint8Array(rawData)
}

function rawToUint8Array(rawData) {
    var outputArray = new Uint8Array(rawData.length);

    for (var i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

async function getRegistration() {
  let registration = await navigator.serviceWorker.getRegistration()
  return registration !== undefined? registration : await navigator.serviceWorker.register('worker.js')
}

getRegistration()

async function subscribeWebPushNotifications() {
  let registration = await getRegistration()
  let subscription = await registration.pushManager.getSubscription()
  if (subscription === null) {
    const response = await fetch("/api/vapid-public-key")
    const vapidPublicKey = await response.text()
    console.log(vapidPublicKey)
    // console.log(window.atob(vapidPublicKey))
    // const convertedVapidKey = urlBase64ToUint8Array(vapidPublicKey);  
    const convertedVapidKey = vapidPublicKey

    console.log(convertedVapidKey)
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: convertedVapidKey,
    })
    if (subscription === null) {
      throw new Error('Failed to subscribe')
    }
  }
  await fetch("/api/register-push-subscription", {
    method: "post",
    headers: {
      "Content-type": "application/json",
    },
    body: JSON.stringify(subscription),
  });
}

document.querySelector("button.push-subscribe").addEventListener("click", async () => {
  let result = Notification.permission === "default"? await Notification.requestPermission(): Notification.permission
  if (result === "granted") {
    await subscribeWebPushNotifications()
  }
});

