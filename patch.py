import re

file_path = r"c:\Internship\Trafffic-Analytics\Traffic_CV\dashboard\src\pages\ConfiguratorPage.tsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update Tool type
content = content.replace(
    "type Tool = 'entry' | 'exit' | 'polygon' | null;",
    "type Tool = 'entry' | 'exit' | 'polygon' | 'calibration' | null;"
)

# 2. Add state for calibration
content = content.replace(
    "const [speedPolygon, setSpeedPolygon] = useState<NormalizedPoint[]>([]);",
    "const [speedPolygon, setSpeedPolygon] = useState<NormalizedPoint[]>([]);\n  const [calibrationPolygon, setCalibrationPolygon] = useState<NormalizedPoint[]>([]);"
)
content = content.replace(
    "const [tempPolygon, setTempPolygon] = useState<NormalizedPoint[]>([]);",
    "const [tempPolygon, setTempPolygon] = useState<NormalizedPoint[]>([]);\n  const [tempCalibration, setTempCalibration] = useState<NormalizedPoint[]>([]);"
)

# 3. Load calibration from camera
content = content.replace(
    "setSpeedPolygon(cam?.speed_polygon_normalized ?? []);",
    "setSpeedPolygon(cam?.speed_polygon_normalized ?? []);\n    setCalibrationPolygon(cam?.calibration_polygon_normalized ?? []);"
)
content = content.replace(
    "setTempPolygon([]);",
    "setTempPolygon([]);\n    setTempCalibration([]);"
)

# 4. Update redraw signature and calls
content = content.replace(
    "redraw(img, cam?.entry_line ?? null, cam?.exit_line ?? null, cam?.speed_polygon_normalized ?? [], null, null, [], null, showEntryExit, showPolygon);",
    "redraw(img, cam?.entry_line ?? null, cam?.exit_line ?? null, cam?.speed_polygon_normalized ?? [], cam?.calibration_polygon_normalized ?? [], null, null, [], [], null, showEntryExit, showPolygon);"
)

# Replace the redraw definition
old_redraw_def = """  const redraw = useCallback(
    (
      img: HTMLImageElement | null,
      entry: NormalizedLine | null,
      exit: NormalizedLine | null,
      polygon: NormalizedPoint[],
      preview: { x: number; y: number } | null,
      anchor: { x: number; y: number } | null,
      tPolygon: NormalizedPoint[],
      activeTool?: Tool,
      sEntryExit?: boolean,
      sPolygon?: boolean
    ) => {"""
new_redraw_def = """  const redraw = useCallback(
    (
      img: HTMLImageElement | null,
      entry: NormalizedLine | null,
      exit: NormalizedLine | null,
      polygon: NormalizedPoint[],
      calibration: NormalizedPoint[],
      preview: { x: number; y: number } | null,
      anchor: { x: number; y: number } | null,
      tPolygon: NormalizedPoint[],
      tCalibration: NormalizedPoint[],
      activeTool?: Tool,
      sEntryExit?: boolean,
      sPolygon?: boolean
    ) => {"""
content = content.replace(old_redraw_def, new_redraw_def)

# Update the useEffect for redraw
content = content.replace(
    "redraw(imageRef.current, entryLine, exitLine, speedPolygon, previewPoint, tempPoint, tempPolygon, tool, showEntryExit, showPolygon);",
    "redraw(imageRef.current, entryLine, exitLine, speedPolygon, calibrationPolygon, previewPoint, tempPoint, tempPolygon, tempCalibration, tool, showEntryExit, showPolygon);"
)
content = content.replace(
    "}, [entryLine, exitLine, speedPolygon, previewPoint, tempPoint, tempPolygon, tool, showEntryExit, showPolygon, redraw]);",
    "}, [entryLine, exitLine, speedPolygon, calibrationPolygon, previewPoint, tempPoint, tempPolygon, tempCalibration, tool, showEntryExit, showPolygon, redraw]);"
)

# 5. Draw logic inside redraw
# Find where drawPoly is defined
draw_poly_def = """      // Speed Polygon
      const drawPoly = (points: NormalizedPoint[], isComplete: boolean) => {"""
new_draw_poly_def = """      // Generic Polygon Drawer
      const drawPoly = (points: NormalizedPoint[], isComplete: boolean, colorStr: string, fillColorStr: string) => {"""
content = content.replace(draw_poly_def, new_draw_poly_def)

# Replace hardcoded colors in drawPoly
content = content.replace("ctx.fillStyle = 'rgba(234, 179, 8, 0.2)'; // Yellow with opacity", "ctx.fillStyle = fillColorStr;")
content = content.replace("ctx.strokeStyle = '#eab308';", "ctx.strokeStyle = colorStr;")
content = content.replace("ctx.fillStyle = '#eab308';", "ctx.fillStyle = colorStr;")

# Update drawPoly calls
content = content.replace("drawPoly(polygon, true);", "drawPoly(polygon, true, '#eab308', 'rgba(234, 179, 8, 0.2)');")
content = content.replace("drawPoly(tPolygon, false);", "drawPoly(tPolygon, false, '#eab308', 'rgba(234, 179, 8, 0.2)');")

# Also fix the `if (sPolygon && polygon.length === 4)` to `polygon.length >= 3`
content = content.replace("if (sPolygon && polygon.length === 4) {", "if (sPolygon && polygon.length >= 3) {")

# Add drawing for calibration polygon
calibration_draw_code = """
      if (sPolygon && calibration.length === 4) {
         drawPoly(calibration, true, '#06b6d4', 'rgba(6, 182, 212, 0.2)'); // Cyan
      }

      if (activeTool === 'calibration' && tCalibration.length > 0) {
         drawPoly(tCalibration, false, '#06b6d4', 'rgba(6, 182, 212, 0.2)');
         if (preview) {
             ctx.beginPath();
             const last = tCalibration[tCalibration.length - 1];
             ctx.moveTo(last.x * canvas.width, last.y * canvas.height);
             ctx.lineTo(preview.x * canvas.width, preview.y * canvas.height);
             ctx.strokeStyle = '#06b6d4';
             ctx.setLineDash([8,4]);
             ctx.stroke();
             ctx.setLineDash([]);
         }
      }
"""
content = content.replace("      // Lines", calibration_draw_code + "\n      // Lines")

# 6. Mouse down logic
old_mouse_down = """    if (tool === 'polygon') {
      const newPoly = [...tempPolygon, { x: normX, y: normY }];
      if (newPoly.length === 4) {
          setSpeedPolygon(newPoly);
          setTempPolygon([]);
          setTool(null);
          setPreviewPoint(null);
      } else {
          setTempPolygon(newPoly);
      }
      return;
    }"""
new_mouse_down = """    if (tool === 'polygon') {
      setTempPolygon([...tempPolygon, { x: normX, y: normY }]);
      return;
    }

    if (tool === 'calibration') {
      const newCal = [...tempCalibration, { x: normX, y: normY }];
      if (newCal.length === 4) {
          setCalibrationPolygon(newCal);
          setTempCalibration([]);
          setTool(null);
          setPreviewPoint(null);
      } else {
          setTempCalibration(newCal);
      }
      return;
    }"""
content = content.replace(old_mouse_down, new_mouse_down)

# Mouse move logic
content = content.replace("if (tool === 'polygon' && tempPolygon.length === 0) return;", "if (tool === 'polygon' && tempPolygon.length === 0) return;\n    if (tool === 'calibration' && tempCalibration.length === 0) return;")

# 7. Save logic
old_save = """        speed_polygon: speedPolygon.length === 4 ? speedPolygon : null,
        distance_between_lines_meters: distance"""
new_save = """        speed_polygon: speedPolygon.length >= 3 ? speedPolygon : null,
        calibration_polygon: calibrationPolygon.length === 4 ? calibrationPolygon : null,
        distance_between_lines_meters: distance"""
content = content.replace(old_save, new_save)

# 8. Reset logic
content = content.replace("setSpeedPolygon([]);", "setSpeedPolygon([]);\n    setCalibrationPolygon([]);")
content = content.replace("setTempPolygon([]);", "setTempPolygon([]);\n    setTempCalibration([]);")

# 9. UI Buttons - Add finish polygon button and calibration button
old_buttons = """                  <Button
                    variant={tool === 'polygon' ? 'default' : 'outline'}
                    size="sm"
                    className="w-full justify-start"
                    onClick={() => { setTool('polygon'); setTempPolygon([]); setDrawState(0); }}
                  >
                    <Hexagon className="mr-2 h-4 w-4" />
                    Speed Polygon
                  </Button>"""

new_buttons = """                  <Button
                    variant={tool === 'polygon' ? 'default' : 'outline'}
                    size="sm"
                    className="w-full justify-start"
                    onClick={() => { setTool('polygon'); setTempPolygon([]); setDrawState(0); }}
                  >
                    <Hexagon className="mr-2 h-4 w-4" />
                    Speed ROI Polygon
                  </Button>
                  
                  {tool === 'polygon' && tempPolygon.length >= 3 && (
                     <Button
                       variant="default"
                       size="sm"
                       className="w-full justify-start bg-green-600 hover:bg-green-700"
                       onClick={() => { 
                         setSpeedPolygon(tempPolygon);
                         setTempPolygon([]);
                         setTool(null);
                         setPreviewPoint(null);
                       }}
                     >
                       <Save className="mr-2 h-4 w-4" />
                       Finish ROI Polygon
                     </Button>
                  )}

                  <Button
                    variant={tool === 'calibration' ? 'default' : 'outline'}
                    size="sm"
                    className="w-full justify-start"
                    onClick={() => { setTool('calibration'); setTempCalibration([]); setDrawState(0); }}
                  >
                    <Hexagon className="mr-2 h-4 w-4" />
                    Calibration Box (4pt)
                  </Button>"""

content = content.replace(old_buttons, new_buttons)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("ConfiguratorPage.tsx patched successfully!")
