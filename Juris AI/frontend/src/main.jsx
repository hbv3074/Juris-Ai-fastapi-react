import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

function showBootError(message) {
	const root = document.getElementById("root");
	if (!root) return;
	root.innerHTML = `
		<div style="padding:16px;font-family:Segoe UI,Arial,sans-serif;color:#7f1d1d;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;margin:16px;">
			<h2 style="margin:0 0 8px 0;">Frontend Startup Error</h2>
			<pre style="white-space:pre-wrap;margin:0;">${String(message)}</pre>
		</div>
	`;
}

window.addEventListener("error", (event) => {
	showBootError(event.error?.stack || event.message || "Unknown runtime error");
});

window.addEventListener("unhandledrejection", (event) => {
	showBootError(event.reason?.stack || event.reason || "Unhandled promise rejection");
});

try {
	createRoot(document.getElementById("root")).render(<App />);
} catch (err) {
	showBootError(err?.stack || err?.message || err);
}
