use pyo3::prelude::*;
use numpy::{IntoPyArray, PyArray2, PyReadonlyArray2};
use ndarray::{Array2, ArrayView2};

mod waterfall;
mod alignment; 

use waterfall::generate_waterfall_fast;
use alignment::phase_correlate;

/// Generate waterfall visualization from dual sidescan channels
#[pyfunction]
fn generate_sidescan_waterfall(
    py: Python,
    left_data: PyReadonlyArray2<u8>,
    right_data: PyReadonlyArray2<u8>,
    width: usize,
    gap_pixels: Option<usize>,
) -> PyResult<&PyArray2<u8>> {
    let left = left_data.as_array();
    let right = right_data.as_array();
    let gap = gap_pixels.unwrap_or(4);
    
    let result = generate_waterfall_fast(left, right, width, gap);
    Ok(result.into_pyarray(py))
}

/// Fast phase correlation for waterfall alignment
#[pyfunction]
fn align_waterfall_frames(
    py: Python,
    frame1: PyReadonlyArray2<u8>,
    frame2: PyReadonlyArray2<u8>,
) -> PyResult<i32> {
    let f1 = frame1.as_array();
    let f2 = frame2.as_array();
    
    let shift = phase_correlate(f1, f2);
    Ok(shift)
}

/// Benchmark function to compare with Python implementation
#[pyfunction]
fn benchmark_waterfall_generation(
    py: Python,
    iterations: usize,
    height: usize,
    width: usize,
) -> PyResult<f64> {
    use std::time::Instant;
    
    // Create dummy data
    let left = Array2::<u8>::zeros((height, width / 2));
    let right = Array2::<u8>::zeros((height, width / 2));
    
    let start = Instant::now();
    
    for _ in 0..iterations {
        let _result = generate_waterfall_fast(left.view(), right.view(), width, 4);
    }
    
    let duration = start.elapsed();
    Ok(duration.as_secs_f64() / iterations as f64)
}

/// A Python module implemented in Rust.
#[pymodule]
fn rsd_video_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(generate_sidescan_waterfall, m)?)?;
    m.add_function(wrap_pyfunction!(align_waterfall_frames, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_waterfall_generation, m)?)?;
    Ok(())
}