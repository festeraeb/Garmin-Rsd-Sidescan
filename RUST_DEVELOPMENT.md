# Rust Video Acceleration Development

This branch explores implementing video acceleration using Rust for the RSD Studio project.

## Performance Goals
- 10-100x faster waterfall generation (SIMD + zero-copy)
- 5-20x faster video encoding (hardware acceleration)
- 50-80% memory reduction
- Total video export: 58s → 3-6s for 1600 frames

## Architecture
```
rust-video-core/           # Rust crate
├── src/
│   ├── waterfall.rs       # Fast waterfall generation
│   ├── encoder.rs         # Hardware-accelerated encoding  
│   ├── alignment.rs       # Phase correlation optimization
│   ├── lib.rs             # Python bindings (PyO3)
│   └── main.rs            # CLI testing
├── Cargo.toml
└── README.md

python-wrapper/            # Python integration
├── rsd_video_fast.py      # High-level wrapper
└── benchmark.py           # Performance comparison
```

## Current Python Bottlenecks (Measured)
- PIL Image.open(): 32.94ms per frame
- NumPy conversion: 1.75ms per frame  
- Processing overhead: 1.39ms per frame
- **Total per frame: 36.09ms**
- **1600 frames: 57.74 seconds**

## Development Plan
1. ✅ Create rust-video-acceleration branch
2. 🔄 Set up Rust workspace with PyO3
3. ⏳ Implement basic waterfall generation
4. ⏳ Add SIMD optimizations
5. ⏳ Integrate FFmpeg for hardware encoding
6. ⏳ Create Python bindings
7. ⏳ Benchmark against current implementation
8. ⏳ Integration testing with full RSD files

## Dependencies
- Rust (latest stable)
- PyO3 for Python bindings
- FFmpeg for video encoding
- SIMD crates for optimization

## Auto-Allow Configuration
VSCode workspace configured for automated testing and building of Rust components.