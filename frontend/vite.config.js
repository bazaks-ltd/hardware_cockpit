import path from "node:path"
import react from "@vitejs/plugin-react"
import frappeui from "frappe-ui/vite"
import { defineConfig } from "vite"

// Mirrors the pos_next build wiring, but for React:
//  - frappeui() sets up the dev proxy to the Frappe backend, injects the jinja boot-data
//    loop into the built HTML, and copies the built index.html -> www/item_cockpit.html.
//  - build output lands in ../hardware_cockpit/public/item_cockpit and is served at
//    /assets/hardware_cockpit/item_cockpit/.
export default defineConfig({
	plugins: [
		frappeui({
			frappeProxy: true,
			jinjaBootData: true,
			lucideIcons: false,
			frappeTypes: false,
			buildConfig: {
				indexHtmlPath: "../hardware_cockpit/www/item_cockpit.html",
				outDir: "../hardware_cockpit/public/item_cockpit",
				emptyOutDir: true,
				sourcemap: false,
			},
		}),
		react(),
	],
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "src"),
		},
	},
	build: {
		outDir: "../hardware_cockpit/public/item_cockpit",
		emptyOutDir: true,
		target: "es2018",
		sourcemap: false,
	},
	server: {
		port: 8081,
	},
})
