import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { dataService } from '@/lib/state-store';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Play, Square, AlertCircle, Smartphone, Radio, Video, Globe, Copy, Check } from 'lucide-react';
import { toast } from 'sonner';
import type { ConfiguratorCamera } from '@/types';

export function PipelinePage() {
  const [selectedCam, setSelectedCam] = useState<string>('');
  const [isPlaying, setIsPlaying] = useState(false);
  const [copied, setCopied] = useState(false);

  const { data: cameras = [], isLoading } = useQuery<ConfiguratorCamera[]>({
    queryKey: ['cameras'],
    queryFn: () => dataService.getCameras(),
  });

  const { data: networkInfo } = useQuery({
    queryKey: ['network-info'],
    queryFn: () => dataService.getNetworkInfo(),
    staleTime: 300_000,
  });

  const currentCamera = cameras.find((c) => c.id === selectedCam);

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

  const copyMobileUrl = () => {
    if (networkInfo?.phone_stream_url) {
      navigator.clipboard.writeText(networkInfo.phone_stream_url);
      setCopied(true);
      toast.success('Mobile pairing URL copied!');
      setTimeout(() => setCopied(false), 2000);
    }
  };

  useEffect(() => {
    return () => setIsPlaying(false);
  }, []);

  const getSourceBadge = (source?: string) => {
    if (!source) return null;
    if (source === 'push') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
          <Smartphone className="h-3 w-3" /> Phone Web Stream
        </span>
      );
    }
    if (source.startsWith('rtsp://') || source.startsWith('http://') || source.startsWith('https://')) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-500/10 text-cyan-500 border border-cyan-500/20">
          <Radio className="h-3 w-3" /> Mobile RTSP Feed
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-500 border border-blue-500/20">
        <Video className="h-3 w-3" /> Local Video File
      </span>
    );
  };

  return (
    <div className="flex flex-col gap-6 p-6 h-full">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Live AI Pipeline</h1>
          <p className="text-muted-foreground mt-1">
            Real-time YOLO11 tracking, DeepSORT trajectory filtering, and consensus ANPR access logging.
          </p>
        </div>

        {networkInfo && (
          <div className="flex items-center gap-2 bg-muted/60 border rounded-lg px-3 py-2 text-xs">
            <Globe className="h-4 w-4 text-emerald-500" />
            <span className="text-muted-foreground">Phone Stream:</span>
            <span className="font-mono font-medium text-foreground">{networkInfo.phone_stream_url}</span>
            <Button size="icon" variant="ghost" className="h-6 w-6" onClick={copyMobileUrl}>
              {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
            </Button>
          </div>
        )}
      </div>

      <Card className="flex-1 min-h-[600px] flex flex-col">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4 border-b">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <CardTitle>Stream Viewer</CardTitle>
              {currentCamera && getSourceBadge(currentCamera.video_source)}
            </div>
            <CardDescription className="font-mono text-xs">
              {currentCamera ? `Source: ${currentCamera.video_source}` : 'Select a camera to begin.'}
            </CardDescription>
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
              <Button onClick={handleStart} disabled={!selectedCam || isLoading} className="w-36 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold">
                <Play className="mr-2 h-4 w-4" /> Start Pipeline
              </Button>
            ) : (
              <Button onClick={handleStop} variant="destructive" className="w-36 font-semibold">
                <Square className="mr-2 h-4 w-4" /> Stop Stream
              </Button>
            )}
          </div>
        </CardHeader>
        
        <CardContent className="flex-1 flex flex-col items-center justify-center bg-black/5 rounded-b-xl relative overflow-hidden p-0">
          {!isPlaying ? (
            <div className="text-center p-8">
              <Play className="h-16 w-16 mx-auto text-muted-foreground mb-4 opacity-40" />
              <h3 className="text-xl font-semibold mb-2">AI Stream Standby</h3>
              <p className="text-muted-foreground max-w-md mx-auto text-sm">
                Click <strong>"Start Pipeline"</strong> to run YOLO11 detection, DeepSORT tracking, and real-time license plate consensus on the selected feed.
              </p>
              {currentCamera?.video_source === 'push' && networkInfo && (
                <div className="mt-4 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg max-w-sm mx-auto text-xs text-emerald-600 dark:text-emerald-400">
                  📱 Mobile push mode is active! Open <strong>{networkInfo.phone_stream_url}</strong> on your phone and tap Start Stream.
                </div>
              )}
            </div>
          ) : (
            <div className="w-full h-full relative flex items-center justify-center bg-black">
              <img 
                src={`${window.location.protocol}//${window.location.hostname}:8001/api/stream/${selectedCam}?t=${Date.now()}`}
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
                  <AlertCircle className="h-5 w-5 mr-3 flex-shrink-0" />
                  <span className="text-sm">Lost connection to the streaming server. Make sure the pipeline container is running on port 8001.</span>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
