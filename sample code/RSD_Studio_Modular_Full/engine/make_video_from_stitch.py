
#!/usr/bin/env python3
# requires: pip install imageio imageio-ffmpeg av
from pathlib import Path
import argparse, sys
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--frames",required=True); ap.add_argument("--out",required=True); ap.add_argument("--fps",type=int,default=30); a=ap.parse_args()
    try: import imageio.v3 as iio
    except Exception: print("Install: pip install imageio imageio-ffmpeg av", file=sys.stderr); sys.exit(2)
    frames=sorted(Path(a.frames).glob("*.png")); 
    if not frames: print("No PNG frames", file=sys.stderr); sys.exit(1)
    first=iio.imread(frames[0]); print(f"{len(frames)} frames @ {a.fps} → {a.out}")
    with iio.imopen(a.out,"w",plugin="pyav") as f:
        f.init_video_stream("libx264", fps=a.fps)
        for p in frames: f.write_frame(iio.imread(p))
if __name__=="__main__": main()
