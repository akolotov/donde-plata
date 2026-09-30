(() => {
  const telegram = window.Telegram?.WebApp;
  const status = document.getElementById("status");
  telegram?.ready();
  if (!telegram?.initData) {
    status.textContent = "Open this app using the button in your Telegram bot chat.";
    return;
  }
  telegram.expand();

  async function load() {
    try {
      const response = await fetch("./api/context", {
        headers: { Authorization: `tma ${telegram.initData}` },
        cache: "no-store",
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Unable to open the app.");
      status.textContent = "Your Mini App is ready.";
    } catch (error) {
      status.textContent = error.message || "Unable to open the app. Please try again.";
    }
  }
  load();
})();
