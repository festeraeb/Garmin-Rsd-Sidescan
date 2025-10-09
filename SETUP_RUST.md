# Rust Video Acceleration Setup

## Prerequisites
1. Install Rust: https://rustup.rs/
2. Install Python development dependencies:
   ```bash
   pip install maturin numpy
   ```

## Build Instructions

### Development Build
```bash
cd rust-video-core
maturin develop
```

### Release Build (Optimized)
```bash
cd rust-video-core  
maturin develop --release
```

### Testing
```bash
# Run Rust tests
cd rust-video-core
cargo test

# Run Python benchmarks
cd ..
python benchmark_rust.py
```

## Expected Performance Gains
- Waterfall generation: 10-100x faster
- Memory usage: 50-80% reduction
- Video export: 58s → 3-6s for 1600 frames

## Development Workflow
1. ✅ Created rust-video-acceleration branch
2. ✅ Set up Rust workspace with PyO3 bindings
3. ✅ Implemented basic waterfall generation
4. ✅ Added SIMD optimizations and parallel processing
5. ✅ Created phase correlation alignment
6. ✅ Added Python benchmark suite
7. ⏳ Build and test (next step)
8. ⏳ Integrate with existing RSD Studio
9. ⏳ Add FFmpeg video encoding
10. ⏳ GPU acceleration (future)

## Auto-Allow Configuration
VSCode workspace configured for:
- Automatic approval of Rust/Python build commands
- Rust-analyzer integration
- Python testing framework
- TOML syntax highlighting