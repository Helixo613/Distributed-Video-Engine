import { useState, useRef } from 'react';
import { UploadCloud, CheckCircle2, Sparkles } from 'lucide-react';
import { cn } from '../../lib/utils';
import { toast } from 'sonner';
import { apiUrl } from '../../lib/api';
import type { JobPhase } from '../../types';

interface VideoUploadProps {
  onSelect: (path: string) => void;
  onPreviewChange?: (preview: string | null) => void;
  isProcessing?: boolean;
  progress?: number;
  phase?: JobPhase;
  className?: string;
}

async function createThumbnail(file: File): Promise<string | null> {
  const objectUrl = URL.createObjectURL(file);
  try {
    const thumb = await new Promise<string>((resolve, reject) => {
      const video = document.createElement('video');
      video.src = objectUrl;
      video.muted = true;
      video.playsInline = true;
      video.preload = 'metadata';

      video.onloadedmetadata = () => {
        video.currentTime = Math.min(1, Math.max(video.duration / 3, 0));
      };

      video.onseeked = () => {
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(video.videoWidth, 1);
        canvas.height = Math.max(video.videoHeight, 1);
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          reject(new Error('Unable to create thumbnail context'));
          return;
        }
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL('image/jpeg', 0.82));
      };

      video.onerror = () => reject(new Error('Failed to decode video for thumbnail'));
    });
    return thumb;
  } catch {
    return null;
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

export function VideoUpload({
  onSelect,
  onPreviewChange,
  isProcessing = false,
  progress = 0,
  phase = 'queued',
  className,
}: VideoUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [thumbnailData, setThumbnailData] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (file: File) => {
    setUploading(true);
    const thumb = await createThumbnail(file);
    if (thumb) {
      setThumbnailData(thumb);
      onPreviewChange?.(thumb);
    } else {
      onPreviewChange?.(null);
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(apiUrl('/upload'), {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error('Upload failed');

      const data = await res.json();
      setSelectedFile(data.filename);
      onSelect(data.path);
      toast.success('Video uploaded successfully!');
    } catch (e) {
      toast.error('Upload failed');
      console.error(e);
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleUpload(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className={cn('bg-[#111111] border border-[#222222] rounded-2xl p-6 h-full flex flex-col', className)}>
      <h3 className="text-sm font-bold text-zinc-500 uppercase tracking-wider mb-4">Input Source</h3>

      <div
        className={cn(
          'flex-1 border-2 border-dashed rounded-xl flex flex-col items-center justify-center transition-all cursor-pointer relative overflow-hidden',
          isDragging ? 'border-indigo-500 bg-indigo-500/10' : 'border-[#333] hover:border-[#444] hover:bg-white/5',
          selectedFile ? 'border-emerald-500/50 bg-emerald-500/5' : ''
        )}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          accept="video/*"
          onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
        />

        {uploading ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-xs font-bold text-indigo-400">Uploading...</span>
          </div>
        ) : selectedFile ? (
          <div className="w-full h-full">
            {thumbnailData ? (
              <div className="relative w-full h-full rounded-lg overflow-hidden border border-[#333]">
                <img
                  src={thumbnailData}
                  alt="Video thumbnail preview"
                  className="w-full h-full object-cover scale-[1.01]"
                  style={{
                    filter: isProcessing ? 'grayscale(0.7) contrast(1.2) saturate(0.7)' : 'none',
                    imageRendering: isProcessing ? 'pixelated' : 'auto',
                  }}
                />

                {isProcessing && (
                  <>
                    <div
                      className="absolute inset-y-0 left-0 overflow-hidden transition-all duration-300"
                      style={{ width: `${progress}%` }}
                    >
                      <img
                        src={thumbnailData}
                        alt="Rendered thumbnail progress"
                        className="w-full h-full object-cover scale-[1.01]"
                        style={{ filter: 'saturate(1.1) contrast(1.05) brightness(1.05)' }}
                      />
                    </div>
                    <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(transparent_0%,rgba(15,15,15,0.12)_50%,transparent_100%)] bg-[length:100%_8px] mix-blend-overlay" />
                    <div
                      className="absolute top-0 bottom-0 w-[2px] bg-cyan-300/90 shadow-[0_0_12px_rgba(34,211,238,0.8)] transition-all duration-300"
                      style={{ left: `calc(${progress}% - 1px)` }}
                    />
                  </>
                )}

                {isProcessing ? (
                  <div className="absolute inset-0 bg-black/35 backdrop-blur-[1px] flex flex-col items-center justify-center px-4">
                    <Sparkles className="w-7 h-7 text-cyan-200 animate-pulse mb-2" />
                    <p className="text-[10px] font-bold uppercase tracking-wider text-cyan-100 mb-2">
                      Rendering {phase}
                    </p>
                    <div className="w-full max-w-[220px] h-2.5 bg-black/60 rounded-full overflow-hidden border border-cyan-300/20">
                      <div
                        className="h-full bg-gradient-to-r from-cyan-500 via-indigo-500 to-fuchsia-500 transition-all duration-300"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                    <p className="text-sm text-white mt-2 font-bold">{progress}%</p>
                  </div>
                ) : (
                  <>
                    <div className="absolute bottom-2 left-2 right-2 p-2 rounded-lg bg-black/45 backdrop-blur-sm border border-white/10">
                      <p className="text-xs text-white font-semibold truncate">{selectedFile}</p>
                      <p className="text-[10px] text-emerald-300 font-bold uppercase tracking-wider mt-0.5">Ready to deploy</p>
                    </div>
                    <div className="absolute top-2 right-2 px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider bg-emerald-500/80 text-white">
                      Ready
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 h-full justify-center">
                <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                </div>
                <span className="text-sm font-bold text-white max-w-[200px] truncate">{selectedFile}</span>
                <span className="text-[10px] text-emerald-500 font-bold uppercase tracking-wider">Ready to Deploy</span>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 text-zinc-500">
            <div className="w-12 h-12 rounded-2xl bg-[#1a1a1a] flex items-center justify-center border border-[#333]">
              <UploadCloud className="w-6 h-6" />
            </div>
            <div className="text-center">
              <span className="text-xs font-bold block text-zinc-300">Click to Upload</span>
              <span className="text-[10px]">or drag video file here</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
