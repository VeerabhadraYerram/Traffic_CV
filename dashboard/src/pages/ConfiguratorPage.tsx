import { useRef, useEffect, useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { SlidersHorizontal, Pencil, Minus, RotateCcw, Save, Info } from 'lucide-react';
import { dataService } from '@/lib/state-store';
import type { ConfiguratorCamera, NormalizedLine } from '@/types';
import { cn } from '@/lib/utils';

// ─── Types ────────────────────────────────────────────────────────────────────

type Tool = 'entry' | 'exit' | null;
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

  const [selectedId, setSelectedId] = useState<string>('');
  const [entryLine, setEntryLine] = useState<NormalizedLine | null>(null);
  const [exitLine, setExitLine] = useState<NormalizedLine | null>(null);
  const [tool, setTool] = useState<Tool>(null);
  const [drawState, setDrawState] = useState<DrawState>(0);
  const [tempPoint, setTempPoint] = useState<{ x: number; y: number } | null>(null);
  const [previewPoint, setPreviewPoint] = useState<{ x: number; y: number } | null>(null);
  const [saving, setSaving] = useState(false);
  const [frameError, setFrameError] = useState(false);

  // ── Fetch cameras ─────────────────────────────────────────────────────────
  const { data: cameras = [], isLoading } = useQuery({
    queryKey: ['cameras'],
    queryFn: () => dataService.getCameras() as Promise<ConfiguratorCamera[]>,
    staleTime: 60_000,
  });

  const selectedCamera = cameras.find((c) => c.id === selectedId) ?? null;

  // ── Load frame when camera changes ────────────────────────────────────────
  useEffect(() => {
    if (!selectedId) return;

    const cam = cameras.find((c) => c.id === selectedId);
    setEntryLine(cam?.entry_line ?? null);
    setExitLine(cam?.exit_line ?? null);
    setTool(null);
    setDrawState(0);
    setTempPoint(null);
    setPreviewPoint(null);
    setFrameError(false);

    const img = new Image();
    img.onload = () => {
      imageRef.current = img;
      const canvas = canvasRef.current;
      if (!canvas) return;
      canvas.width = img.width;
      canvas.height = img.height;
      redraw(img, cam?.entry_line ?? null, cam?.exit_line ?? null, null, null);
    };
    img.onerror = () => setFrameError(true);
    img.src = `/api/cameras/${selectedId}/frame?t=${Date.now()}`;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  // ── Redraw canvas ─────────────────────────────────────────────────────────
  const redraw = useCallback(
    (
      img: HTMLImageElement | null,
      entry: NormalizedLine | null,
      exit: NormalizedLine | null,
      preview: { x: number; y: number } | null,
      anchor: { x: number; y: number } | null,
      activeTool?: Tool
    ) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      if (img) ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      if (entry) {
        drawLine(
          ctx,
          entry.x1 * canvas.width, entry.y1 * canvas.height,
          entry.x2 * canvas.width, entry.y2 * canvas.height,
          '#22c55e', 'ENTRY'
        );
      }

      if (exit) {
        drawLine(
          ctx,
          exit.x1 * canvas.width, exit.y1 * canvas.height,
          exit.x2 * canvas.width, exit.y2 * canvas.height,
          '#ef4444', 'EXIT'
        );
      }

      // preview rubber-band
      if (anchor && preview && activeTool) {
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
    redraw(imageRef.current, entryLine, exitLine, previewPoint, tempPoint, tool);
  }, [entryLine, exitLine, previewPoint, tempPoint, tool, redraw]);

  // ── Canvas events ─────────────────────────────────────────────────────────
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!tool || !canvasRef.current) return;
    const { normX, normY } = getCanvasCoords(e, canvasRef.current);

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
    if (drawState !== 1 || !canvasRef.current) return;
    const { normX, normY } = getCanvasCoords(e, canvasRef.current);
    setPreviewPoint({ x: normX, y: normY });
  };

  // ── Save ─────────────────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!selectedId) return;
    setSaving(true);
    try {
      await dataService.saveCameraLines(selectedId, {
        entry_line: entryLine,
        exit_line: exitLine,
      });
      toast.success('Configuration saved', {
        description: `Tripwire lines updated for "${selectedCamera?.name}"`,
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
    setTool(null);
    setDrawState(0);
    setTempPoint(null);
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
            Draw entry and exit tripwire lines on the camera frame
          </p>
        </div>
      </div>

      <div className="flex gap-4 flex-1 min-h-0">
        {/* ── Sidebar Panel ── */}
        <div className="w-72 shrink-0 flex flex-col gap-4">

          {/* Camera selector */}
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
              <div className="rounded-md bg-muted/50 p-3 text-xs space-y-1 text-muted-foreground">
                <div className="flex justify-between">
                  <span>Role</span>
                  <span className="font-mono font-semibold text-foreground capitalize">
                    {selectedCamera.role}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>IP</span>
                  <span className="font-mono text-foreground">
                    {selectedCamera.ip_address ?? '—'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Speed Limit</span>
                  <span className="font-mono text-foreground">
                    {selectedCamera.speed_limit_kmh} km/h
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Status</span>
                  <span
                    className={cn(
                      'font-semibold',
                      selectedCamera.status === 'ACTIVE'
                        ? 'text-emerald-600'
                        : 'text-destructive'
                    )}
                  >
                    {selectedCamera.status}
                  </span>
                </div>
              </div>
            )}
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
                setPreviewPoint(null);
              }}
              disabled={!selectedId}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-2.5 text-sm font-semibold transition-all border',
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
                setPreviewPoint(null);
              }}
              disabled={!selectedId}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-2.5 text-sm font-semibold transition-all border',
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
              onClick={handleReset}
              disabled={!selectedId}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-2.5 text-sm font-medium transition-all border border-border bg-background hover:bg-accent text-muted-foreground',
                !selectedId && 'opacity-40 cursor-not-allowed'
              )}
            >
              <RotateCcw className="h-4 w-4" />
              Clear All Lines
            </button>
          </div>

          {/* Status indicator */}
          <div className="rounded-lg border bg-card p-4 flex flex-col gap-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-1.5 font-semibold text-foreground text-[11px] uppercase tracking-wider">
              <Info className="h-3.5 w-3.5" />
              Line Status
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

            {tool && (
              <div className="mt-1 rounded-md bg-primary/10 text-primary px-2 py-1.5 text-[11px] font-medium leading-snug">
                {drawState === 0
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
        <div className="flex-1 rounded-lg border bg-black overflow-hidden flex items-center justify-center relative">
          {!selectedId && (
            <div className="text-center text-muted-foreground space-y-2">
              <SlidersHorizontal className="h-12 w-12 mx-auto opacity-20" />
              <p className="text-sm font-medium">Select a camera to begin</p>
            </div>
          )}

          {selectedId && frameError && (
            <div className="text-center text-muted-foreground space-y-2">
              <p className="text-sm font-medium text-destructive">
                Could not load camera frame
              </p>
              <p className="text-xs">
                Check that the video source is accessible
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
