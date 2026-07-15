import { useRef, useEffect, useState, useCallback } from 'react';
import type { ChangeEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { SlidersHorizontal, Pencil, Minus, RotateCcw, Save, Info, Hexagon, Upload, Eye, EyeOff } from 'lucide-react';
import { dataService } from '@/lib/state-store';
import type { ConfiguratorCamera, NormalizedLine, NormalizedPoint } from '@/types';
import { cn } from '@/lib/utils';

// ─── Types ────────────────────────────────────────────────────────────────────

type Tool = 'entry' | 'exit' | 'polygon' | 'calibration' | null;
type DrawState = 0 | 1; // 0 = idle, 1 = first point placed

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getCanvasCoords(
  e: React.MouseEvent<HTMLCanvasElement>,
  canvas: HTMLCanvasElement
): { normX: number; normY: number } {
  const rect = canvas.getBoundingClientRect();
  const intrinsicW = canvas.width;
  const intrinsicH = canvas.height;

  const displayRatio = rect.width / rect.height;
  const intrinsicRatio = intrinsicW / intrinsicH;

  let drawW: number, drawH: number, offX = 0, offY = 0;
  if (displayRatio > intrinsicRatio) {
    drawH = rect.height;
    drawW = rect.height * intrinsicRatio;
    offX = (rect.width - drawW) / 2;
  } else {
    drawW = rect.width;
    drawH = rect.width / intrinsicRatio;
    offY = (rect.height - drawH) / 2;
  }

  const mouseX = e.clientX - rect.left - offX;
  const mouseY = e.clientY - rect.top - offY;

  return {
    normX: Math.max(0, Math.min(1, mouseX / drawW)),
    normY: Math.max(0, Math.min(1, mouseY / drawH)),
  };
}

function drawLine(
  ctx: CanvasRenderingContext2D,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  color: string,
  label?: string
) {
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.setLineDash([]);
  ctx.stroke();

  // endpoints
  for (const [px, py] of [[x1, y1], [x2, y2]]) {
    ctx.beginPath();
    ctx.arc(px, py, 7, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = 'white';
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  // label
  if (label) {
    const midX = (x1 + x2) / 2;
    const midY = (y1 + y2) / 2;
    ctx.font = 'bold 13px Inter, sans-serif';
    ctx.fillStyle = 'white';
    ctx.strokeStyle = 'rgba(0,0,0,0.7)';
    ctx.lineWidth = 4;
    ctx.strokeText(label, midX + 8, midY - 8);
    ctx.fillText(label, midX + 8, midY - 8);
  }
}

function drawPreviewLine(
  ctx: CanvasRenderingContext2D,
  x1: number, y1: number,
  x2: number, y2: number,
  color: string
) {
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.setLineDash([8, 4]);
  ctx.stroke();
  ctx.setLineDash([]);
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function ConfiguratorPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const [selectedId, setSelectedId] = useState<string>('');
  
  // Configurations
  const [entryLine, setEntryLine] = useState<NormalizedLine | null>(null);
  const [exitLine, setExitLine] = useState<NormalizedLine | null>(null);
  const [speedPolygon, setSpeedPolygon] = useState<NormalizedPoint[]>([]);
  const [calibrationPolygon, setCalibrationPolygon] = useState<NormalizedPoint[]>([]);
  const [distance, setDistance] = useState<number>(15.0);

  // View Options
  const [showEntryExit, setShowEntryExit] = useState(true);
  const [showPolygon, setShowPolygon] = useState(true);

  // Tools & State
  const [tool, setTool] = useState<Tool>(null);
  const [drawState, setDrawState] = useState<DrawState>(0);
  const [tempPoint, setTempPoint] = useState<{ x: number; y: number } | null>(null);
  const [tempPolygon, setTempPolygon] = useState<NormalizedPoint[]>([]);
  const [tempCalibration, setTempCalibration] = useState<NormalizedPoint[]>([]);
  const [previewPoint, setPreviewPoint] = useState<{ x: number; y: number } | null>(null);
  
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [frameError, setFrameError] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // ── Fetch cameras ─────────────────────────────────────────────────────────
  const { data: cameras = [], isLoading } = useQuery({
    queryKey: ['cameras'],
    queryFn: () => dataService.getCameras() as Promise<ConfiguratorCamera[]>,
    staleTime: 60_000,
  });
  const queryClient = useQueryClient();

  const selectedCamera = cameras.find((c) => c.id === selectedId) ?? null;

  // ── Load frame when camera changes ────────────────────────────────────────
  useEffect(() => {
    if (!selectedId) return;

    const cam = cameras.find((c) => c.id === selectedId);
    setEntryLine(cam?.entry_line ?? null);
    setExitLine(cam?.exit_line ?? null);
    setSpeedPolygon(cam?.speed_polygon_normalized ?? []);
    setCalibrationPolygon(cam?.calibration_polygon_normalized ?? []);
    setDistance(cam?.distance_between_lines_meters ?? 15.0);
    
    setTool(null);
    setDrawState(0);
    setTempPoint(null);
    setPreviewPoint(null);
    setTempPolygon([]);
    setTempCalibration([]);
    setTempCalibration([]);
    setFrameError(false);

    const img = new Image();
    img.onload = () => {
      imageRef.current = img;
      const canvas = canvasRef.current;
      if (!canvas) return;
      canvas.width = img.width;
      canvas.height = img.height;
      redraw(img, cam?.entry_line ?? null, cam?.exit_line ?? null, cam?.speed_polygon_normalized ?? [], cam?.calibration_polygon_normalized ?? [], null, null, [], [], null, showEntryExit, showPolygon);
    };
    img.onerror = () => setFrameError(true);
    img.src = `/api/cameras/${selectedId}/frame?t=${Date.now()}`;
    
    return () => {
      img.onload = null;
      img.onerror = null;
      img.src = '';
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, refreshTrigger]);

  // ── Redraw canvas ─────────────────────────────────────────────────────────
  const redraw = useCallback(
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
    ) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      if (img) ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      // Generic Polygon Drawer
      const drawPoly = (points: NormalizedPoint[], isComplete: boolean, colorStr: string, fillColorStr: string) => {
         if (points.length === 0) return;
         ctx.beginPath();
         ctx.moveTo(points[0].x * canvas.width, points[0].y * canvas.height);
         for(let i = 1; i < points.length; i++) {
             ctx.lineTo(points[i].x * canvas.width, points[i].y * canvas.height);
         }
         
         if (isComplete) {
            ctx.closePath();
            ctx.fillStyle = fillColorStr;
            ctx.fill();
         }
         
         ctx.strokeStyle = colorStr;
         ctx.lineWidth = 2;
         ctx.stroke();

         for (const p of points) {
            ctx.beginPath();
            ctx.arc(p.x * canvas.width, p.y * canvas.height, 5, 0, Math.PI * 2);
            ctx.fillStyle = colorStr;
            ctx.fill();
            ctx.strokeStyle = 'white';
            ctx.stroke();
         }
      };

      if (sPolygon && polygon.length >= 3) {
         drawPoly(polygon, true, '#eab308', 'rgba(234, 179, 8, 0.2)');
      }

      if (activeTool === 'polygon' && tPolygon.length > 0) {
         drawPoly(tPolygon, false, '#eab308', 'rgba(234, 179, 8, 0.2)');
         if (preview) {
             ctx.beginPath();
             const last = tPolygon[tPolygon.length - 1];
             ctx.moveTo(last.x * canvas.width, last.y * canvas.height);
             ctx.lineTo(preview.x * canvas.width, preview.y * canvas.height);
             ctx.strokeStyle = '#eab308';
             ctx.setLineDash([8,4]);
             ctx.stroke();
             ctx.setLineDash([]);
         }
      }


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

      // Lines
      if (sEntryExit && entry) {
        drawLine(
          ctx,
          entry.x1 * canvas.width, entry.y1 * canvas.height,
          entry.x2 * canvas.width, entry.y2 * canvas.height,
          '#22c55e', 'ENTRY'
        );
      }

      if (sEntryExit && exit) {
        drawLine(
          ctx,
          exit.x1 * canvas.width, exit.y1 * canvas.height,
          exit.x2 * canvas.width, exit.y2 * canvas.height,
          '#ef4444', 'EXIT'
        );
      }

      // preview rubber-band for lines
      if (anchor && preview && (activeTool === 'entry' || activeTool === 'exit')) {
        const color = activeTool === 'entry' ? '#22c55e' : '#ef4444';
        drawPreviewLine(
          ctx,
          anchor.x * canvas.width, anchor.y * canvas.height,
          preview.x * canvas.width, preview.y * canvas.height,
          color
        );
      }
    },
    []
  );

  // trigger redraw whenever lines change
  useEffect(() => {
    redraw(imageRef.current, entryLine, exitLine, speedPolygon, calibrationPolygon, previewPoint, tempPoint, tempPolygon, tempCalibration, tool, showEntryExit, showPolygon);
  }, [entryLine, exitLine, speedPolygon, calibrationPolygon, previewPoint, tempPoint, tempPolygon, tempCalibration, tool, showEntryExit, showPolygon, redraw]);

  // ── Canvas events ─────────────────────────────────────────────────────────
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!tool || !canvasRef.current) return;
    const { normX, normY } = getCanvasCoords(e, canvasRef.current);

    if (tool === 'polygon') {
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
    }

    if (drawState === 0) {
      setTempPoint({ x: normX, y: normY });
      setDrawState(1);
    } else {
      // Complete the line
      if (tool === 'entry') {
        setEntryLine({ x1: tempPoint!.x, y1: tempPoint!.y, x2: normX, y2: normY });
      } else {
        setExitLine({ x1: tempPoint!.x, y1: tempPoint!.y, x2: normX, y2: normY });
      }
      setDrawState(0);
      setTempPoint(null);
      setPreviewPoint(null);
      setTool(null);
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!tool || !canvasRef.current) return;
    if (tool === 'polygon' && tempPolygon.length === 0) return;
    if (tool === 'calibration' && tempCalibration.length === 0) return;
    if ((tool === 'entry' || tool === 'exit') && drawState !== 1) return;
    
    const { normX, normY } = getCanvasCoords(e, canvasRef.current);
    setPreviewPoint({ x: normX, y: normY });
  };

  // ── Video Upload ─────────────────────────────────────────────────────────
  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0 || !selectedId) return;
    const file = e.target.files[0];
    
    setUploading(true);
    try {
      await dataService.uploadVideo(selectedId, file);
      toast.success('Video uploaded successfully', { description: 'The video source for this camera has been updated.' });
      queryClient.invalidateQueries({ queryKey: ['cameras'] });
      setRefreshTrigger(prev => prev + 1); // trigger frame reload
    } catch (err) {
      toast.error('Upload failed', { description: String(err) });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // ── Save ─────────────────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!selectedId) return;
    setSaving(true);
    try {
      await dataService.saveCameraLines(selectedId, {
        entry_line: entryLine,
        exit_line: exitLine,
        speed_polygon: speedPolygon.length >= 3 ? speedPolygon : null,
        calibration_polygon: calibrationPolygon.length === 4 ? calibrationPolygon : null,
        distance_between_lines_meters: distance
      });
      queryClient.invalidateQueries({ queryKey: ['cameras'] });
      toast.success('Configuration saved', {
        description: `Tripwire and speed configurations updated for "${selectedCamera?.name}"`,
      });
    } catch (err) {
      toast.error('Save failed', { description: String(err) });
    } finally {
      setSaving(false);
    }
  };

  // ── Reset ─────────────────────────────────────────────────────────────────
  const handleReset = () => {
    setEntryLine(null);
    setExitLine(null);
    setSpeedPolygon([]);
    setCalibrationPolygon([]);
    setTool(null);
    setDrawState(0);
    setTempPoint(null);
    setTempPolygon([]);
    setTempCalibration([]);
    setTempCalibration([]);
    setPreviewPoint(null);
  };

  // ── Cursor style ──────────────────────────────────────────────────────────
  const cursorStyle = tool ? 'crosshair' : 'default';

  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col space-y-4 h-full">
      {/* Page header */}
      <div className="flex items-center gap-3">
        <SlidersHorizontal className="h-5 w-5 text-primary" />
        <div>
          <h1 className="text-xl font-bold tracking-tight">Camera Configurator</h1>
          <p className="text-sm text-muted-foreground">
            Draw tracking zones and configure video feeds
          </p>
        </div>
      </div>

      <div className="flex gap-4 flex-1 min-h-0 overflow-y-auto">
        {/* ── Sidebar Panel ── */}
        <div className="w-80 shrink-0 flex flex-col gap-4">

          {/* Camera selector & Upload */}
          <div className="rounded-lg border bg-card p-4 flex flex-col gap-3">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Select Camera
            </label>
            {isLoading ? (
              <div className="h-10 rounded-md bg-muted animate-pulse" />
            ) : (
              <select
                value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
              >
                <option value="">— Select a Camera —</option>
                {cameras.map((cam) => (
                  <option key={cam.id} value={cam.id}>
                    {cam.name} ({cam.role})
                  </option>
                ))}
              </select>
            )}

            {/* Camera meta */}
            {selectedCamera && (
              <div className="rounded-md bg-muted/50 p-3 text-xs space-y-2 text-muted-foreground">
                <div className="flex justify-between items-center">
                  <span>Source File</span>
                  <span className="font-mono text-[10px] text-foreground truncate max-w-[150px]" title={selectedCamera.video_source}>
                    {selectedCamera.video_source.split('/').pop()}
                  </span>
                </div>
                
                <div className="pt-2 border-t border-border">
                  <input type="file" accept="video/mp4,video/x-m4v,video/*" className="hidden" ref={fileInputRef} onChange={handleFileUpload} />
                  <button 
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                    className="w-full flex items-center justify-center gap-2 rounded-md bg-secondary text-secondary-foreground hover:bg-secondary/80 px-2 py-1.5 text-xs font-medium transition-colors"
                  >
                    <Upload className="h-3.5 w-3.5" />
                    {uploading ? 'Uploading...' : 'Upload New Video'}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Configuration Inputs */}
          <div className="rounded-lg border bg-card p-4 flex flex-col gap-3">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Speed Configuration
            </label>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Real-world distance between lines (Meters)</label>
              <input 
                type="number" 
                value={distance} 
                onChange={e => setDistance(parseFloat(e.target.value) || 0)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                step="0.5"
                min="1"
              />
            </div>
            
            <div className="flex items-center gap-2 pt-2">
               <button 
                  onClick={() => setShowEntryExit(!showEntryExit)} 
                  className={cn("flex-1 flex items-center justify-center gap-2 rounded-md px-2 py-1.5 text-xs font-medium border transition-colors", showEntryExit ? "border-primary text-primary bg-primary/10" : "border-border text-muted-foreground")}
               >
                 {showEntryExit ? <Eye className="h-3 w-3"/> : <EyeOff className="h-3 w-3"/>}
                 Entry/Exit
               </button>
               <button 
                  onClick={() => setShowPolygon(!showPolygon)} 
                  className={cn("flex-1 flex items-center justify-center gap-2 rounded-md px-2 py-1.5 text-xs font-medium border transition-colors", showPolygon ? "border-yellow-500 text-yellow-600 bg-yellow-500/10" : "border-border text-muted-foreground")}
               >
                 {showPolygon ? <Eye className="h-3 w-3"/> : <EyeOff className="h-3 w-3"/>}
                 Speed Poly
               </button>
            </div>
          </div>

          {/* Drawing tools */}
          <div className="rounded-lg border bg-card p-4 flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Drawing Tools
            </label>

            <button
              onClick={() => {
                setTool('entry');
                setDrawState(0);
                setTempPoint(null);
                setTempPolygon([]);
    setTempCalibration([]);
    setTempCalibration([]);
                setPreviewPoint(null);
                setShowEntryExit(true);
              }}
              disabled={!selectedId}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition-all border',
                tool === 'entry'
                  ? 'bg-emerald-500/15 border-emerald-500 text-emerald-600'
                  : 'border-border bg-background hover:bg-accent text-foreground',
                !selectedId && 'opacity-40 cursor-not-allowed'
              )}
            >
              <Pencil className="h-4 w-4" />
              Draw Entry Line
            </button>

            <button
              onClick={() => {
                setTool('exit');
                setDrawState(0);
                setTempPoint(null);
                setTempPolygon([]);
    setTempCalibration([]);
    setTempCalibration([]);
                setPreviewPoint(null);
                setShowEntryExit(true);
              }}
              disabled={!selectedId}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition-all border',
                tool === 'exit'
                  ? 'bg-red-500/15 border-red-500 text-red-600'
                  : 'border-border bg-background hover:bg-accent text-foreground',
                !selectedId && 'opacity-40 cursor-not-allowed'
              )}
            >
              <Minus className="h-4 w-4" />
              Draw Exit Line
            </button>

            <button
              onClick={() => {
                setTool('polygon');
                setDrawState(0);
                setTempPoint(null);
                setTempPolygon([]);
                setTempCalibration([]);
                setPreviewPoint(null);
                setShowPolygon(true);
              }}
              disabled={!selectedId}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition-all border',
                tool === 'polygon'
                  ? 'bg-yellow-500/15 border-yellow-500 text-yellow-600'
                  : 'border-border bg-background hover:bg-accent text-foreground',
                !selectedId && 'opacity-40 cursor-not-allowed'
              )}
            >
              <Hexagon className="h-4 w-4" />
              Speed ROI Poly
            </button>
            
            {tool === 'polygon' && tempPolygon.length >= 3 && (
              <button
                onClick={() => {
                  setSpeedPolygon(tempPolygon);
                  setTempPolygon([]);
                  setTool(null);
                  setPreviewPoint(null);
                }}
                className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition-all border bg-green-500/15 border-green-500 text-green-600 hover:bg-green-500/25"
              >
                <Save className="h-4 w-4" />
                Finish ROI Poly
              </button>
            )}

            <button
              onClick={() => {
                setTool('calibration');
                setDrawState(0);
                setTempPoint(null);
                setTempPolygon([]);
                setTempCalibration([]);
                setPreviewPoint(null);
                setShowPolygon(true);
              }}
              disabled={!selectedId}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition-all border',
                tool === 'calibration'
                  ? 'bg-cyan-500/15 border-cyan-500 text-cyan-600'
                  : 'border-border bg-background hover:bg-accent text-foreground',
                !selectedId && 'opacity-40 cursor-not-allowed'
              )}
            >
              <Hexagon className="h-4 w-4" />
              Calibration Box (4pt)
            </button>

            <button
              onClick={handleReset}
              disabled={!selectedId}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-2 mt-2 text-sm font-medium transition-all border border-border bg-background hover:bg-accent text-muted-foreground',
                !selectedId && 'opacity-40 cursor-not-allowed'
              )}
            >
              <RotateCcw className="h-4 w-4" />
              Clear All Overlays
            </button>
          </div>

          {/* Status indicator */}
          <div className="rounded-lg border bg-card p-4 flex flex-col gap-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-1.5 font-semibold text-foreground text-[11px] uppercase tracking-wider">
              <Info className="h-3.5 w-3.5" />
              Overlay Status
            </div>
            <div className="flex justify-between">
              <span>Entry Line</span>
              <span className={entryLine ? 'text-emerald-600 font-semibold' : 'text-muted-foreground'}>
                {entryLine ? '✓ Set' : 'Not set'}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Exit Line</span>
              <span className={exitLine ? 'text-red-600 font-semibold' : 'text-muted-foreground'}>
                {exitLine ? '✓ Set' : 'Not set'}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Speed Polygon</span>
              <span className={speedPolygon.length === 4 ? 'text-yellow-600 font-semibold' : 'text-muted-foreground'}>
                {speedPolygon.length === 4 ? '✓ Set' : 'Not set'}
              </span>
            </div>

            {tool && (
              <div className="mt-1 rounded-md bg-primary/10 text-primary px-2 py-1.5 text-[11px] font-medium leading-snug">
                {tool === 'polygon' 
                  ? `Click to place point ${tempPolygon.length + 1} of 4 for the polygon`
                  : drawState === 0
                    ? `Click on the frame to set the start point of the ${tool} line`
                    : `Click again to complete the ${tool} line`}
              </div>
            )}
          </div>

          {/* Save */}
          <button
            onClick={handleSave}
            disabled={saving || !selectedId}
            className={cn(
              'mt-auto flex items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-bold transition-all',
              'bg-primary text-primary-foreground hover:bg-primary/90 shadow',
              (saving || !selectedId) && 'opacity-50 cursor-not-allowed'
            )}
          >
            <Save className="h-4 w-4" />
            {saving ? 'Saving…' : 'Save Configuration'}
          </button>
        </div>

        {/* ── Canvas Panel ── */}
        <div className="flex-1 rounded-lg border bg-black overflow-hidden flex items-center justify-center relative min-h-[500px]">
          {!selectedId && (
            <div className="text-center text-muted-foreground space-y-2">
              <SlidersHorizontal className="h-12 w-12 mx-auto opacity-20" />
              <p className="text-sm font-medium">Select a camera to begin</p>
            </div>
          )}

          {selectedId && frameError && (
            <div className="text-center text-muted-foreground space-y-2 z-10 absolute inset-0 flex flex-col justify-center items-center bg-black/80">
              <p className="text-sm font-medium text-destructive">
                Could not load camera frame
              </p>
              <p className="text-xs">
                Check that the video source is accessible or upload a new video.
              </p>
            </div>
          )}

          <canvas
            ref={canvasRef}
            style={{ cursor: cursorStyle, maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
          />
        </div>
      </div>
    </div>
  );
}

export default ConfiguratorPage;
