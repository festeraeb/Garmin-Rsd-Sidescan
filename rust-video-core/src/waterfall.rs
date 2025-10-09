use ndarray::{Array2, ArrayView2, Axis};
use rayon::prelude::*;

/// Fast waterfall generation with SIMD optimizations
pub fn generate_waterfall_fast(
    left: ArrayView2<u8>,
    right: ArrayView2<u8>,
    total_width: usize,
    gap_pixels: usize,
) -> Array2<u8> {
    let height = left.nrows().min(right.nrows());
    let channel_width = (total_width - gap_pixels) / 2;
    
    let mut waterfall = Array2::<u8>::zeros((height, total_width));
    
    // Parallel processing for each row
    waterfall.axis_iter_mut(Axis(0))
        .into_par_iter()
        .enumerate()
        .for_each(|(row_idx, mut waterfall_row)| {
            if row_idx < height {
                // Left channel
                if let Some(left_row) = left.row(row_idx).get(..channel_width) {
                    waterfall_row.slice_mut(s![..channel_width])
                        .assign(&ArrayView2::from_shape((1, channel_width), left_row).unwrap().row(0));
                }
                
                // Gap (filled with background)
                waterfall_row.slice_mut(s![channel_width..channel_width + gap_pixels])
                    .fill(128); // Mid-gray background
                
                // Right channel  
                if let Some(right_row) = right.row(row_idx).get(..channel_width) {
                    waterfall_row.slice_mut(s![channel_width + gap_pixels..])
                        .assign(&ArrayView2::from_shape((1, channel_width), right_row).unwrap().row(0));
                }
            }
        });
    
    waterfall
}

/// Optimized waterfall with intensity scaling
pub fn generate_waterfall_with_scaling(
    left: ArrayView2<u8>,
    right: ArrayView2<u8>, 
    total_width: usize,
    gap_pixels: usize,
    intensity_scale: f32,
) -> Array2<u8> {
    let height = left.nrows().min(right.nrows());
    let channel_width = (total_width - gap_pixels) / 2;
    
    let mut waterfall = Array2::<u8>::zeros((height, total_width));
    
    // SIMD-friendly scaling function
    let scale_intensity = |value: u8| -> u8 {
        ((value as f32 * intensity_scale).min(255.0).max(0.0)) as u8
    };
    
    waterfall.axis_iter_mut(Axis(0))
        .into_par_iter()
        .enumerate()
        .for_each(|(row_idx, mut waterfall_row)| {
            if row_idx < height {
                // Process left channel with scaling
                if let Some(left_row) = left.row(row_idx).get(..channel_width) {
                    for (i, &pixel) in left_row.iter().enumerate() {
                        waterfall_row[i] = scale_intensity(pixel);
                    }
                }
                
                // Gap
                for i in channel_width..channel_width + gap_pixels {
                    waterfall_row[i] = 128;
                }
                
                // Process right channel with scaling
                if let Some(right_row) = right.row(row_idx).get(..channel_width) {
                    for (i, &pixel) in right_row.iter().enumerate() {
                        waterfall_row[channel_width + gap_pixels + i] = scale_intensity(pixel);
                    }
                }
            }
        });
    
    waterfall
}

#[cfg(test)]
mod tests {
    use super::*;
    use ndarray::Array2;
    
    #[test]
    fn test_waterfall_generation() {
        let left = Array2::<u8>::ones((10, 50));
        let right = Array2::<u8>::zeros((10, 50));
        
        let waterfall = generate_waterfall_fast(left.view(), right.view(), 104, 4);
        
        assert_eq!(waterfall.shape(), &[10, 104]);
        
        // Check left channel (should be 1s)
        assert_eq!(waterfall[[0, 0]], 1);
        assert_eq!(waterfall[[0, 49]], 1);
        
        // Check gap (should be 128)
        assert_eq!(waterfall[[0, 50]], 128);
        assert_eq!(waterfall[[0, 53]], 128);
        
        // Check right channel (should be 0s)
        assert_eq!(waterfall[[0, 54]], 0);
        assert_eq!(waterfall[[0, 103]], 0);
    }
}