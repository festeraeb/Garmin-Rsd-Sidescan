use ndarray::{ArrayView2, Array2};
use std::collections::HashMap;

/// Fast phase correlation for frame alignment
pub fn phase_correlate(frame1: ArrayView2<u8>, frame2: ArrayView2<u8>) -> i32 {
    // Simplified cross-correlation for horizontal shift detection
    let height = frame1.nrows().min(frame2.nrows());
    let width = frame1.ncols().min(frame2.ncols());
    
    if height == 0 || width == 0 {
        return 0;
    }
    
    let max_shift = 20; // Limit search range for performance
    let mut best_correlation = f64::NEG_INFINITY;
    let mut best_shift = 0;
    
    // Test different horizontal shifts
    for shift in -max_shift..=max_shift {
        let mut correlation = 0.0;
        let mut count = 0;
        
        // Sample every 4th row for speed
        for row in (0..height).step_by(4) {
            for col in 0..width {
                let col2 = (col as i32 + shift) as usize;
                
                if col2 < width {
                    let diff = (frame1[[row, col]] as f64 - frame2[[row, col2]] as f64).abs();
                    correlation += 255.0 - diff; // Higher is better
                    count += 1;
                }
            }
        }
        
        if count > 0 {
            correlation /= count as f64;
            if correlation > best_correlation {
                best_correlation = correlation;
                best_shift = shift;
            }
        }
    }
    
    best_shift
}

/// Optimized alignment using edge detection
pub fn phase_correlate_edges(frame1: ArrayView2<u8>, frame2: ArrayView2<u8>) -> i32 {
    let height = frame1.nrows().min(frame2.nrows());
    let width = frame1.ncols().min(frame2.ncols());
    
    if height < 3 || width < 3 {
        return 0;
    }
    
    // Extract edge features for more robust alignment
    let edges1 = extract_edges(frame1);
    let edges2 = extract_edges(frame2);
    
    let max_shift = 15;
    let mut best_correlation = f64::NEG_INFINITY;
    let mut best_shift = 0;
    
    for shift in -max_shift..=max_shift {
        let correlation = correlate_edges(&edges1, &edges2, shift, width);
        
        if correlation > best_correlation {
            best_correlation = correlation;
            best_shift = shift;
        }
    }
    
    best_shift
}

fn extract_edges(frame: ArrayView2<u8>) -> Array2<f32> {
    let height = frame.nrows();
    let width = frame.ncols();
    let mut edges = Array2::<f32>::zeros((height, width));
    
    // Simple Sobel-like edge detection
    for row in 1..height-1 {
        for col in 1..width-1 {
            let gx = (frame[[row-1, col+1]] as f32 + 2.0 * frame[[row, col+1]] as f32 + frame[[row+1, col+1]] as f32)
                   - (frame[[row-1, col-1]] as f32 + 2.0 * frame[[row, col-1]] as f32 + frame[[row+1, col-1]] as f32);
            
            let gy = (frame[[row+1, col-1]] as f32 + 2.0 * frame[[row+1, col]] as f32 + frame[[row+1, col+1]] as f32)
                   - (frame[[row-1, col-1]] as f32 + 2.0 * frame[[row-1, col]] as f32 + frame[[row-1, col+1]] as f32);
            
            edges[[row, col]] = (gx * gx + gy * gy).sqrt();
        }
    }
    
    edges
}

fn correlate_edges(edges1: &Array2<f32>, edges2: &Array2<f32>, shift: i32, width: usize) -> f64 {
    let height = edges1.nrows();
    let mut correlation = 0.0;
    let mut count = 0;
    
    // Sample every 3rd row and significant edges only
    for row in (2..height-2).step_by(3) {
        for col in 2..width-2 {
            let col2 = (col as i32 + shift) as usize;
            
            if col2 < width && edges1[[row, col]] > 10.0 { // Only process significant edges
                let diff = (edges1[[row, col]] - edges2[[row, col2]]).abs();
                correlation += (100.0 - diff.min(100.0)) as f64;
                count += 1;
            }
        }
    }
    
    if count > 0 {
        correlation / count as f64
    } else {
        0.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ndarray::Array2;
    
    #[test]
    fn test_phase_correlation() {
        let mut frame1 = Array2::<u8>::zeros((20, 100));
        let mut frame2 = Array2::<u8>::zeros((20, 100));
        
        // Create a pattern in frame1
        for i in 40..60 {
            frame1[[10, i]] = 255;
        }
        
        // Create the same pattern shifted by 5 pixels in frame2
        for i in 45..65 {
            frame2[[10, i]] = 255;
        }
        
        let shift = phase_correlate(frame1.view(), frame2.view());
        assert_eq!(shift, 5);
    }
}