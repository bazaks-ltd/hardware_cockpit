// Desk helper: the "Item Cockpit" Workspace opens a desk page at /app/item-cockpit, but the
// actual dashboard is the standalone SPA at /item-cockpit. Whenever the desk routes to the
// Item Cockpit workspace, bounce the browser to the SPA so the sidebar entry / awesomebar
// search / apps tile all land on the real screen.
(function () {
	var TARGET = "/item-cockpit";

	function slug(s) {
		return String(s == null ? "" : s).trim().toLowerCase().replace(/\s+/g, "-");
	}

	function isCockpitRoute() {
		try {
			var r = (frappe.get_route && frappe.get_route()) || [];
			if (!r.length) return false;
			// Workspace routes appear either as a single slug ["item-cockpit"] or as
			// ["Workspaces", "Item Cockpit"] depending on the Frappe version.
			if (slug(r[0]) === "item-cockpit") return true;
			if (slug(r[0]) === "workspaces" && slug(r[1]) === "item-cockpit") return true;
			return false;
		} catch (e) {
			return false;
		}
	}

	function maybeRedirect() {
		// TARGET is a website route (no /app prefix), so this leaves the desk — no loop.
		if (isCockpitRoute()) window.location.href = TARGET;
	}

	if (window.frappe && frappe.router && frappe.router.on) {
		frappe.router.on("change", maybeRedirect);
	}
	maybeRedirect();
})();
