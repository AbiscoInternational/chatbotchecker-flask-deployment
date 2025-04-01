document.addEventListener("DOMContentLoaded", function () {
    const form = document.querySelector("form");
    form.addEventListener("submit", function () {
        const loadingIndicator = document.createElement("div");
        loadingIndicator.className = "loading";
        loadingIndicator.innerHTML = "<i class='fas fa-spinner fa-spin'></i> Processing...";
        form.appendChild(loadingIndicator);
    });
});
