extends Control
## Original, deterministic vector artwork drawn by Godot. No external assets.

var compact := false
var map_mode := false


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	resized.connect(queue_redraw)


func _draw() -> void:
	var w := size.x
	var h := size.y
	if w <= 0 or h <= 0:
		return
	if map_mode:
		_draw_map(w, h)
		return
	draw_rect(Rect2(Vector2.ZERO, size), Color("dce8d7"))
	draw_circle(Vector2(w * 0.77, h * 0.23), h * 0.085, Color("f5e6a2"))
	var far := PackedVector2Array([
		Vector2(0, h * 0.57), Vector2(w * 0.18, h * 0.22),
		Vector2(w * 0.34, h * 0.49), Vector2(w * 0.52, h * 0.1),
		Vector2(w * 0.75, h * 0.53), Vector2(w, h * 0.3),
		Vector2(w, h), Vector2(0, h),
	])
	draw_colored_polygon(far, Color("a6bea7"))
	var near := PackedVector2Array([
		Vector2(0, h * 0.77), Vector2(w * 0.16, h * 0.48),
		Vector2(w * 0.37, h * 0.71), Vector2(w * 0.64, h * 0.36),
		Vector2(w, h * 0.74), Vector2(w, h), Vector2(0, h),
	])
	draw_colored_polygon(near, Color("5a8169"))
	var foreground := PackedVector2Array([
		Vector2(0, h * 0.92), Vector2(w * 0.31, h * 0.67),
		Vector2(w * 0.53, h * 0.84), Vector2(w * 0.8, h * 0.64),
		Vector2(w, h * 0.76), Vector2(w, h), Vector2(0, h),
	])
	draw_colored_polygon(foreground, Color("244b3e"))
	var trail := PackedVector2Array([
		Vector2(w * 0.4, h * 0.98), Vector2(w * 0.58, h * 0.86),
		Vector2(w * 0.53, h * 0.74), Vector2(w * 0.64, h * 0.62),
	])
	draw_polyline(trail, Color("e9dcb5"), 5.0 if compact else 9.0, true)
	for tree in [Vector2(w * 0.16, h * 0.81), Vector2(w * 0.84, h * 0.82), Vector2(w * 0.89, h * 0.73)]:
		var scale := 0.6 if compact else 1.0
		draw_line(tree, tree + Vector2(0, 20 * scale), Color("173e32"), 3.0)
		draw_colored_polygon(PackedVector2Array([tree + Vector2(0, -23 * scale),
			tree + Vector2(-13, 6) * scale, tree + Vector2(13, 6) * scale]), Color("173e32"))


func _draw_map(w: float, h: float) -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Color("e8eddf"))
	for i in range(7):
		var y := float(i) * h * 0.19 - h * 0.1
		var contour := PackedVector2Array()
		for x in range(0, int(w) + 8, 8):
			contour.append(Vector2(minf(x, w), clampf(y + sin(float(x) / 70.0 + i) * h * 0.11, 0.0, h)))
		draw_polyline(contour, Color("c9d7bd"), 1.5, true)
	var route := PackedVector2Array([
		Vector2(w * 0.2, h * 0.74), Vector2(w * 0.31, h * 0.56),
		Vector2(w * 0.49, h * 0.61), Vector2(w * 0.68, h * 0.32),
		Vector2(w * 0.78, h * 0.37), Vector2(w * 0.67, h * 0.65),
		Vector2(w * 0.43, h * 0.78), Vector2(w * 0.2, h * 0.74),
	])
	draw_polyline(route, Color("244b3e"), 4.0, true)
	draw_circle(route[0], 8, Color("244b3e"))
	draw_circle(route[0], 3, Color("e9f3bd"))
	draw_circle(route[3], 5, Color("d88856"))
