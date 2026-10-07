extends Control
## A fictional, local-only outdoor planner. All data and artwork are original.
## The demo uses ordinary Godot controls; no capture-specific app integration.

const Terrain = preload("res://terrain.gd")
const INK := Color("183c34")
const MUTED := Color("69786c")
const PAPER := Color("f4f6ef")
const LIME := Color("dbefa7")
const BORDER := Color("dce3d5")
const STATE_IDS := ["home", "discover", "detail", "loading", "empty", "error", "saved", "settings", "save_modal", "ready"]

var _screen: Control
var _state := "home"
var _has_saved_plan := false
var _notifications := true
var _serial := 0


func _ready() -> void:
	var initial := "home"
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--demo-state="):
			initial = argument.trim_prefix("--demo-state=")
	show_state(initial if STATE_IDS.has(initial) else "home")


func show_state(state_id: String) -> void:
	_state = state_id
	_serial = 0
	if is_instance_valid(_screen):
		remove_child(_screen)
		_screen.queue_free()
	_screen = Control.new()
	_screen.name = "Screen"
	_screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_screen)
	var background := ColorRect.new()
	background.color = PAPER
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	background.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_screen.add_child(background)
	_label(_screen, 24, 10, 100, 28, "9:41", 14, INK)
	_label(_screen, 248, 10, 118, 28, "LTE   100%", 12, INK, HORIZONTAL_ALIGNMENT_RIGHT)
	match state_id:
		"home": _home()
		"discover": _discover()
		"detail": _detail()
		"loading": _loading()
		"empty": _empty()
		"error": _error()
		"saved": _saved()
		"settings": _settings()
		"save_modal": _save_modal()
		"ready": _ready_plan()
	if not ["loading", "error", "save_modal", "ready"].has(state_id):
		_nav()


func _home() -> void:
	_label(_screen, 24, 57, 290, 32, "fieldnotes", 26, INK)
	_label(_screen, 24, 100, 270, 24, "MAKE ROOM FOR OUTSIDE", 10, MUTED)
	_label(_screen, 24, 127, 342, 86, "A little more\noutside.", 35, INK)
	_label(_screen, 24, 219, 342, 44, "Small adventures. A slower weekend.\nYour next trail is closer than you think.", 14, MUTED)
	var hero := _panel(_screen, 24, 283, 342, 270, Color.WHITE)
	_art(hero, 10, 10, 322, 163)
	_label(hero, 20, 184, 270, 25, "Cerro Azul loop", 20, INK)
	_label(hero, 20, 216, 235, 24, "4.8 km  ·  Easy  ·  1 h 20 min", 12, MUTED)
	_button(hero, "OpenFeaturedTrail", 270, 205, 52, 48, "→", show_state.bind("detail"), INK, Color.WHITE)
	_label(_screen, 24, 578, 230, 25, "A good day to wander", 18, INK)
	var weather := _panel(_screen, 24, 618, 342, 89, Color("e6eddf"))
	_label(weather, 18, 12, 72, 41, "21°", 32, INK)
	_label(weather, 105, 16, 215, 24, "Clear skies, light breeze", 14, INK)
	_label(weather, 105, 43, 210, 22, "A gentle start. Pack some water.", 11, MUTED)


func _discover() -> void:
	_heading("Explore", "A few paths worth taking.")
	var search := _panel(_screen, 24, 159, 342, 51, Color.WHITE)
	_label(search, 17, 13, 300, 26, "⌕   Trails near the coast", 14, MUTED)
	_pill(_screen, 24, 228, 79, "Easy", INK, Color.WHITE)
	_pill(_screen, 113, 228, 107, "Nearby", Color("e6eddf"), INK)
	_pill(_screen, 230, 228, 136, "Under 2 hours", Color("e6eddf"), INK)
	_label(_screen, 24, 286, 280, 25, "Take the scenic route", 18, INK)
	_trail_card(329, "Cerro Azul loop", "Quiet hills, open views", "4.8 km  ·  Easy", "OpenCerroAzul")
	_trail_card(491, "El Faro lookout", "A little climb. A wide horizon.", "3.2 km  ·  Easy", "OpenElFaro")
	_label(_screen, 24, 674, 342, 42, "Good trails don't need to be far away.", 13, MUTED)


func _detail() -> void:
	_button(_screen, "BackFromTrail", 24, 57, 48, 44, "←", show_state.bind("discover"), Color("e6eddf"), INK)
	_label(_screen, 86, 64, 260, 24, "TRAIL NOTES", 11, MUTED)
	_label(_screen, 24, 120, 342, 48, "Cerro Azul loop", 30, INK)
	_label(_screen, 24, 171, 342, 26, "A gentle climb above the coastline.", 14, MUTED)
	var map := _panel(_screen, 24, 220, 342, 224, Color.WHITE)
	_art(map, 8, 8, 326, 208, true)
	var stats := _panel(_screen, 24, 464, 342, 79, Color("e6eddf"))
	_label(stats, 17, 11, 102, 28, "4.8 km", 20, INK)
	_label(stats, 17, 42, 100, 21, "DISTANCE", 9, MUTED)
	_label(stats, 132, 11, 102, 28, "1 h 20", 20, INK)
	_label(stats, 132, 42, 100, 21, "EST. TIME", 9, MUTED)
	_label(stats, 258, 11, 70, 28, "Easy", 20, INK)
	_label(stats, 258, 42, 70, 21, "PACE", 9, MUTED)
	_label(_screen, 24, 562, 342, 23, "Leave early. Take your time.", 18, INK)
	_label(_screen, 24, 597, 342, 43, "Bring water, a light layer and a friend.\nThe lookout is best before midday.", 13, MUTED)
	_button(_screen, "PrepareRoute", 24, 663, 228, 51, "Prepare my route", show_state.bind("loading"), INK, Color.WHITE)
	_button(_screen, "SaveTrail", 264, 663, 102, 51, "Save", show_state.bind("save_modal"), LIME, INK)


func _loading() -> void:
	_label(_screen, 24, 70, 342, 26, "FIELDNOTES", 11, MUTED, HORIZONTAL_ALIGNMENT_CENTER)
	var art := _panel(_screen, 44, 180, 302, 228, Color.WHITE)
	_art(art, 10, 10, 282, 208, true)
	_label(_screen, 24, 446, 342, 46, "Finding your way", 28, INK, HORIZONTAL_ALIGNMENT_CENTER)
	_label(_screen, 32, 504, 326, 57, "Preparing your trail notes\nand checking the route ahead.", 14, MUTED, HORIZONTAL_ALIGNMENT_CENTER)
	var progress := ProgressBar.new()
	progress.name = "RouteProgress"
	progress.position = Vector2(64, 594)
	progress.size = Vector2(262, 8)
	progress.value = 68
	progress.show_percentage = false
	progress.add_theme_stylebox_override("background", _style(BORDER, 4))
	progress.add_theme_stylebox_override("fill", _style(INK, 4))
	_screen.add_child(progress)
	_label(_screen, 24, 615, 342, 22, "A moment to slow down.", 12, MUTED, HORIZONTAL_ALIGNMENT_CENTER)
	_button(_screen, "CancelPreparation", 94, 676, 202, 49, "Back to trail", show_state.bind("detail"), Color("e6eddf"), INK)
	_button(_screen, "ConnectionHelp", 94, 738, 202, 44, "Connection help", show_state.bind("error"), PAPER, MUTED)


func _empty() -> void:
	_heading("Your plans", "Keep a little adventure in your pocket.")
	var art := _panel(_screen, 54, 210, 282, 197, Color.WHITE)
	_art(art, 10, 10, 262, 177)
	_label(_screen, 34, 446, 322, 83, "Room for your\nnext adventure", 28, INK, HORIZONTAL_ALIGNMENT_CENTER)
	_label(_screen, 34, 544, 322, 50, "Save a trail that catches your eye.\nWe'll keep the details right here.", 14, MUTED, HORIZONTAL_ALIGNMENT_CENTER)
	_button(_screen, "BrowseTrails", 66, 624, 258, 52, "Find a trail", show_state.bind("discover"), INK, Color.WHITE)


func _error() -> void:
	_label(_screen, 24, 70, 342, 26, "FIELDNOTES", 11, MUTED, HORIZONTAL_ALIGNMENT_CENTER)
	var card := _panel(_screen, 116, 234, 158, 136, Color("eae3d3"))
	_label(card, 0, 22, 158, 86, "…", 65, Color("9b7250"), HORIZONTAL_ALIGNMENT_CENTER)
	_label(_screen, 24, 412, 342, 45, "The trail went quiet", 27, INK, HORIZONTAL_ALIGNMENT_CENTER)
	_label(_screen, 35, 479, 320, 75, "We couldn't finish preparing your route.\nYour saved plans are still here.\nTry again when you're connected.", 14, MUTED, HORIZONTAL_ALIGNMENT_CENTER)
	_button(_screen, "RetryConnection", 54, 605, 282, 53, "Try again", show_state.bind("loading"), INK, Color.WHITE)
	_button(_screen, "ReturnHome", 54, 676, 282, 49, "Back to home", show_state.bind("home"), Color("e6eddf"), INK)


func _saved() -> void:
	_has_saved_plan = true
	_heading("Your plans", "A good weekend starts with a small plan.")
	var card := _panel(_screen, 24, 171, 342, 341, Color.WHITE)
	_art(card, 10, 10, 322, 163)
	_label(card, 20, 191, 294, 22, "SATURDAY  ·  08:30", 10, MUTED)
	_label(card, 20, 224, 294, 29, "Cerro Azul loop", 24, INK)
	_label(card, 20, 263, 294, 24, "4.8 km  ·  Easy  ·  Bring water", 12, MUTED)
	_button(card, "OpenItinerary", 20, 286, 302, 44, "Open your plan  →", show_state.bind("ready"), Color("e6eddf"), INK)
	_label(_screen, 24, 545, 342, 25, "One plan. Plenty of possibility.", 18, INK)
	_label(_screen, 24, 584, 342, 50, "Keep it simple. Leave room for\na coffee stop on the way home.", 14, MUTED)
	_button(_screen, "FindAnotherTrail", 24, 668, 342, 48, "Explore another trail", show_state.bind("discover"), INK, Color.WHITE)


func _settings() -> void:
	_heading("Your pace", "Make Fieldnotes feel a little more like you.")
	var profile := _panel(_screen, 24, 171, 342, 83, Color("e6eddf"))
	_label(profile, 18, 12, 55, 49, "F", 33, INK, HORIZONTAL_ALIGNMENT_CENTER)
	_label(profile, 91, 15, 228, 25, "Weekend wanderer", 18, INK)
	_label(profile, 91, 45, 228, 21, "Small trips, good company", 12, MUTED)
	_label(_screen, 24, 287, 342, 25, "PREFERENCES", 10, MUTED)
	_setting_row(327, "Distance", "Kilometers")
	_setting_row(397, "Preferred pace", "Easy going")
	var reminder := _panel(_screen, 24, 467, 342, 60, Color.WHITE)
	_label(reminder, 18, 16, 185, 26, "Weekend reminders", 14, INK)
	_button(reminder, "ToggleReminders", 243, 8, 81, 44, "On" if _notifications else "Off", _toggle_reminders, LIME if _notifications else BORDER, INK)
	_label(_screen, 24, 565, 342, 23, "A gentler kind of planning", 18, INK)
	_label(_screen, 24, 603, 342, 58, "You choose the trail and the pace.\nTake breaks. Notice things.\nLeave the place a little better.", 13, MUTED)
	_label(_screen, 24, 688, 342, 23, "Fieldnotes  ·  local demo", 11, MUTED)


func _save_modal() -> void:
	_detail()
	# Underlying controls are disabled while the confirmation is open.
	for node in _screen.find_children("*", "Button", true, false):
		node.disabled = true
	var shade := ColorRect.new()
	shade.color = Color(0.04, 0.12, 0.09, 0.5)
	shade.position = Vector2(0, 42)
	shade.size = Vector2(390, 802)
	_screen.add_child(shade)
	var sheet := _panel(_screen, 16, 489, 358, 324, PAPER)
	var handle := _panel(sheet, 158, 13, 42, 4, BORDER)
	handle.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_label(sheet, 24, 47, 310, 42, "Keep this little adventure?", 24, INK)
	_label(sheet, 24, 102, 310, 59, "Save Cerro Azul loop for Saturday.\nThe route and your trail notes\nwill be waiting in Your plans.", 14, MUTED)
	_button(sheet, "ConfirmSave", 24, 185, 310, 52, "Save my plan", show_state.bind("saved"), INK, Color.WHITE)
	_button(sheet, "CancelSave", 24, 250, 310, 44, "Maybe later", show_state.bind("detail"), PAPER, MUTED)


func _ready_plan() -> void:
	_button(_screen, "BackFromPlan", 24, 57, 48, 44, "←", show_state.bind("saved"), Color("e6eddf"), INK)
	_label(_screen, 86, 64, 260, 24, "YOUR SATURDAY", 11, MUTED)
	_label(_screen, 24, 126, 342, 50, "A day well spent.", 31, INK)
	_label(_screen, 24, 185, 342, 27, "Cerro Azul loop  ·  A gentle little escape", 13, MUTED)
	var art := _panel(_screen, 24, 236, 342, 174, Color.WHITE)
	_art(art, 8, 8, 326, 158, true)
	_itinerary_row(438, "08:30", "Meet at the trailhead", "Fill your bottle. Take a deep breath.")
	_itinerary_row(523, "09:15", "The coastal lookout", "Stop for the view. Stay a little longer.")
	_itinerary_row(608, "10:00", "Back for a coffee", "No rush. That's the whole point.")
	_button(_screen, "FinishPlan", 24, 722, 342, 54, "Sounds like a plan", show_state.bind("home"), INK, Color.WHITE)


func _nav() -> void:
	var nav := _panel(_screen, 16, 752, 358, 66, Color.WHITE)
	var items := [["Home", "home"], ["Explore", "discover"], ["Saved", "saved" if _has_saved_plan else "empty"], ["You", "settings"]]
	for index in range(items.size()):
		var item: Array = items[index]
		var active: bool = _state == item[1] or (_state == "detail" and index == 1)
		_button(nav, "Nav" + str(item[0]), 6 + index * 87, 10, 84, 45, item[0], show_state.bind(item[1]), LIME if active else Color.WHITE, INK if active else MUTED)
	var gesture := _panel(_screen, 139, 832, 112, 4, INK)
	gesture.mouse_filter = Control.MOUSE_FILTER_IGNORE


func _heading(title: String, subtitle: String) -> void:
	_label(_screen, 24, 67, 342, 46, title, 32, INK)
	_label(_screen, 24, 118, 342, 27, subtitle, 12, MUTED)


func _trail_card(y: float, title: String, subtitle: String, stats: String, control_name: String) -> void:
	var card := _panel(_screen, 24, y, 342, 140, Color.WHITE)
	_art(card, 10, 10, 100, 120)
	_label(card, 128, 13, 204, 29, title, 18, INK)
	_label(card, 128, 48, 202, 34, subtitle, 11, MUTED)
	_label(card, 128, 85, 202, 21, stats, 11, MUTED)
	_label(card, 128, 110, 194, 22, "View trail  →", 12, INK)
	_button(card, control_name, 0, 0, 342, 140, "", show_state.bind("detail"), Color.TRANSPARENT, INK)


func _setting_row(y: float, title: String, value: String) -> void:
	var row := _panel(_screen, 24, y, 342, 60, Color.WHITE)
	_label(row, 18, 16, 181, 26, title, 14, INK)
	_label(row, 192, 16, 132, 26, value, 12, MUTED, HORIZONTAL_ALIGNMENT_RIGHT)


func _pill(parent: Control, x: float, y: float, w: float, text: String, background: Color, foreground: Color) -> void:
	var pill := _panel(parent, x, y, w, 34, background)
	_label(pill, 0, 0, w, 34, text, 12, foreground, HORIZONTAL_ALIGNMENT_CENTER)


func _itinerary_row(y: float, time: String, title: String, detail: String) -> void:
	_label(_screen, 24, y, 66, 25, time, 14, INK)
	_label(_screen, 110, y - 3, 255, 27, title, 17, INK)
	_label(_screen, 110, y + 32, 255, 28, detail, 11, MUTED)


func _art(parent: Control, x: float, y: float, w: float, h: float, map_mode: bool = false) -> void:
	var art := Terrain.new()
	art.name = "TrailIllustration"
	art.position = Vector2(x, y)
	art.size = Vector2(w, h)
	art.compact = h < 180
	art.map_mode = map_mode
	parent.add_child(art)


func _panel(parent: Control, x: float, y: float, w: float, h: float, color: Color) -> Panel:
	_serial += 1
	var panel := Panel.new()
	panel.name = "Panel%03d" % _serial
	panel.position = Vector2(x, y)
	panel.size = Vector2(w, h)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_theme_stylebox_override("panel", _style(color, 18))
	parent.add_child(panel)
	return panel


func _label(parent: Control, x: float, y: float, w: float, h: float, content: String, font_size: int, color: Color, alignment: int = HORIZONTAL_ALIGNMENT_LEFT) -> Label:
	_serial += 1
	var label := Label.new()
	label.name = "Label%03d" % _serial
	label.position = Vector2(x, y)
	label.size = Vector2(w, h)
	label.text = content
	label.horizontal_alignment = alignment
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(label)
	return label


func _button(parent: Control, control_name: String, x: float, y: float, w: float, h: float, content: String, action: Callable, background: Color, foreground: Color) -> Button:
	var button := Button.new()
	button.name = control_name
	button.position = Vector2(x, y)
	button.size = Vector2(w, h)
	button.text = content
	button.add_theme_font_size_override("font_size", 13)
	button.add_theme_color_override("font_color", foreground)
	button.add_theme_color_override("font_hover_color", foreground)
	button.add_theme_color_override("font_pressed_color", foreground)
	button.add_theme_stylebox_override("normal", _style(background, 14))
	button.add_theme_stylebox_override("hover", _style(background.lightened(0.05), 14))
	button.add_theme_stylebox_override("pressed", _style(background.darkened(0.06), 14))
	var focus := _style(Color.TRANSPARENT, 14)
	focus.border_color = Color("93aa73")
	focus.set_border_width_all(2)
	button.add_theme_stylebox_override("focus", focus)
	button.pressed.connect(action)
	parent.add_child(button)
	return button


func _style(color: Color, radius: int) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(radius)
	style.content_margin_left = 8
	style.content_margin_right = 8
	style.content_margin_top = 2
	style.content_margin_bottom = 2
	return style


func _toggle_reminders() -> void:
	_notifications = not _notifications
	show_state("settings")

