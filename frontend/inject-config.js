// Runs at build time and writes frontend/config.js next to this script.
// Set VITE_API_BASE in Vercel to your Railway backend URL.

const fs = require("fs");
const path = require("path");

const apiBase = process.env.VITE_API_BASE || "http://localhost:8000";
const outputPath = path.join(__dirname, "config.js");

const content = `// Auto-generated at build time; do not edit.
window.__API_BASE__ = "${apiBase}";
`;

fs.writeFileSync(outputPath, content);
console.log(`[inject-config] API_BASE set to: ${apiBase}`);
