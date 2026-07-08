app_name = "hardware_cockpit"
app_title = "Hardware Cockpit"
app_publisher = "Hardware Cockpit"
app_description = "Item Cockpit — a single-screen item manager for hardware stores, built on ERPNext."
app_email = "terence.zama@gmail.com"
app_license = "mit"

# Apps
# ------------------
required_apps = ["erpnext"]

# Show a tile on the Apps launcher screen (/apps) that opens the cockpit.
add_to_apps_screen = [
	{
		"name": "hardware_cockpit",
		"logo": "/assets/hardware_cockpit/images/logo.svg",
		"title": "Item Cockpit",
		"route": "/item-cockpit",
		"has_permission": "hardware_cockpit.api.has_app_permission",
	}
]

# Installation
# ------------
after_install = "hardware_cockpit.install.after_install"

# Uninstallation
# ------------
before_uninstall = "hardware_cockpit.install.before_uninstall"

# Website
# -------
# Serve the built React SPA (www/item_cockpit.html + public/item_cockpit assets) at
# /item-cockpit. The first rule maps the exact route (the www file's own name uses an
# underscore); the second lets client-side sub-paths resolve back to the same SPA.
website_route_rules = [
	{"from_route": "/item-cockpit", "to_route": "item_cockpit"},
	{"from_route": "/item-cockpit/<path:app_path>", "to_route": "item_cockpit"},
]
