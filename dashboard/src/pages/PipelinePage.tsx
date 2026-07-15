import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { dataService } from '@/lib/state-store';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Play, Square, AlertCircle } from 'lucide-react';
import type { ConfiguratorCamera } from '@/types';

export function PipelinePage() {
  const [selectedCam, setSelectedCam] = useState<string>('');
  const [isPlaying, setIsPlaying] = useState(false);

  const { data: cameras = [], isLoading } = useQuery<ConfiguratorCamera[]>({
    queryKey: ['cameras'],
    queryFn: () => dataService.getCameras(),
  });

  useEffect(() => {
    if (cameras.length > 0 && !selectedCam) {
      const activeCams = cameras.filter((c: ConfiguratorCamera) => c.status === 'ONLINE');
      if (activeCams.length > 0) setSelectedCam(activeCams[0].id);
      else setSelectedCam(cameras[0].id);
    }
  }, [cameras, selectedCam]);

  const handleStart = () => {
    setIsPlaying(true);
  };

  const handleStop = () => {
    setIsPlaying(false);
  };

  useEffect(() => {
    return () => setIsPlaying(false);
  }, []);

  return (
    <div className="flex flex-col gap-6 p-6 h-full">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Live Pipeline</h1>
          <p className="text-muted-foreground mt-2">
            Real-time YOLO11 tracking and speed estimation stream.
          </p>
        </div>
      </div>

      <Card className="flex-1 min-h-[600px] flex flex-col">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <div>
            <CardTitle>Stream Viewer</CardTitle>
            <CardDescription>Select a camera and click run to start the AI stream.</CardDescription>
          </div>
          
          <div className="flex items-center space-x-4">
            <Select value={selectedCam} onValueChange={setSelectedCam} disabled={isPlaying || isLoading}>
              <SelectTrigger className="w-[250px]">
                <SelectValue placeholder="Select Camera" />
              </SelectTrigger>
              <SelectContent>
                {cameras.map((c: ConfiguratorCamera) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name} {c.status === 'ONLINE' ? '(Active)' : '(Inactive)'}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            {!isPlaying ? (
              <Button onClick={handleStart} disabled={!selectedCam || isLoading} className="w-32 bg-green-600 hover:bg-green-700 text-white">
                <Play className="mr-2 h-4 w-4" /> Start Pipeline
              </Button>
            ) : (
              <Button onClick={handleStop} variant="destructive" className="w-32">
                <Square className="mr-2 h-4 w-4" /> Stop Stream
              </Button>
            )}
          </div>
        </CardHeader>
        
        <CardContent className="flex-1 flex flex-col items-center justify-center bg-black/5 rounded-b-xl border-t relative overflow-hidden">
          {!isPlaying ? (
            <div className="text-center p-8">
              <Play className="h-16 w-16 mx-auto text-muted-foreground mb-4 opacity-50" />
              <h3 className="text-xl font-semibold mb-2">Stream Offline</h3>
              <p className="text-muted-foreground max-w-sm mx-auto">
                Click "Start Pipeline" to spin up the YOLO model and connect to the live MJPEG stream. CPU usage will automatically drop to 0% when stopped.
              </p>
            </div>
          ) : (
            <div className="w-full h-full relative flex items-center justify-center bg-black">
              <img 
                src={`http://localhost:8001/api/stream/${selectedCam}?t=${Date.now()}`}
                alt="Pipeline Live Stream"
                className="max-w-full max-h-full object-contain"
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                  const errEl = document.getElementById('stream-error');
                  if (errEl) errEl.classList.remove('hidden');
                }}
              />
              <div id="stream-error" className="hidden absolute inset-0 flex items-center justify-center bg-black/80">
                 <div className="max-w-md bg-red-950 text-white border-red-900 border p-4 rounded-md flex items-center">
                  <AlertCircle className="h-5 w-5 mr-3" />
                  <span className="text-lg">Lost connection to the streaming server. Make sure the pipeline container is running.</span>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
