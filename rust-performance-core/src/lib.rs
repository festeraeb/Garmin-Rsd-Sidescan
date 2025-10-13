//! High-Performance Rust Core for Garmin RSD Studio
//! 
//! This module provides ultra-fast implementations of critical parsing operations
//! using Rust's zero-cost abstractions, SIMD vectorization, and parallel processing.

use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyList};
use rayon::prelude::*;
use memmap2::Mmap;
use bytemuck::{Pod, Zeroable, cast_slice};
use parking_lot::RwLock;
use ahash::AHashMap;
use smallvec::SmallVec;
use std::sync::Arc;
use std::fs::File;
use std::io::{Result, Seek, SeekFrom};

#[cfg(target_arch = "x86_64")]
use wide::f32x8;

/// High-performance binary data parser
#[pyclass]
pub struct FastBinaryParser {
    mmap: Arc<Mmap>,
    cache: Arc<RwLock<AHashMap<u64, SmallVec<[u8; 64]>>>>,
    file_size: usize,
}

/// Sonar record structure optimized for SIMD processing
#[repr(C)]
#[derive(Debug, Clone, Copy, Pod, Zeroable)]
struct SonarRecord {
    offset: u64,
    channel_id: u32,
    sequence: u32,
    timestamp_ms: u64,
    latitude: f64,
    longitude: f64,
    depth_m: f32,
    sample_count: u32,
    sonar_offset: u64,
    sonar_size: u32,
    beam_angle: f32,
    pitch: f32,
    roll: f32,
    heave: f32,
    tx_offset: f32,
    rx_offset: f32,
    color_id: u16,
    reserved: u16,
}

#[pymethods]
impl FastBinaryParser {
    #[new]
    fn new(file_path: String) -> PyResult<Self> {
        let file = File::open(&file_path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
        
        let mmap = unsafe { Mmap::map(&file) }
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
        
        let file_size = mmap.len();
        
        Ok(FastBinaryParser {
            mmap: Arc::new(mmap),
            cache: Arc::new(RwLock::new(AHashMap::new())),
            file_size,
        })
    }
    
    /// Ultra-fast magic number search using SIMD
    fn find_magic_simd(&self, magic: Vec<u8>, start: usize, end: usize) -> PyResult<Vec<usize>> {
        let data = &self.mmap[start..end.min(self.file_size)];
        let magic_slice = &magic[..];
        
        if magic_slice.is_empty() {
            return Ok(vec![]);
        }
        
        let positions = find_pattern_simd(data, magic_slice);
        Ok(positions.into_iter().map(|pos| start + pos).collect())
    }
    
    /// Parallel chunk processing with optimal load balancing
    fn parallel_parse_chunks(&self, py: Python, chunks: Vec<(usize, usize)>) -> PyResult<Vec<PyObject>> {
        let mmap = Arc::clone(&self.mmap);
        
        let results: Vec<_> = chunks
            .into_par_iter()
            .map(|(start, end)| {
                let chunk_data = &mmap[start..end.min(mmap.len())];
                parse_chunk_fast(chunk_data, start)
            })
            .collect();
        
        // Convert to Python objects
        let py_results = results
            .into_iter()
            .map(|records| {
                let py_list = PyList::empty(py);
                for record in records {
                    let py_record = record_to_python(py, &record)?;
                    py_list.append(py_record)?;
                }
                Ok(py_list.into())
            })
            .collect::<PyResult<Vec<_>>>()?;
        
        Ok(py_results)
    }
    
    /// High-speed coordinate transformation using SIMD
    fn transform_coordinates_simd(
        &self,
        py: Python,
        lats: Vec<f64>,
        lons: Vec<f64>,
        heading: f64,
        offset_x: f64,
        offset_y: f64,
    ) -> PyResult<(Vec<f64>, Vec<f64>)> {
        let (new_lats, new_lons) = transform_coordinates_vectorized(&lats, &lons, heading, offset_x, offset_y);
        Ok((new_lats, new_lons))
    }
    
    /// Cached binary data extraction
    fn read_cached(&self, offset: usize, size: usize) -> PyResult<PyObject> {
        let cache_key = ((offset as u64) << 32) | (size as u64);
        
        // Try cache first
        {
            let cache = self.cache.read();
            if let Some(cached_data) = cache.get(&cache_key) {
                return Python::with_gil(|py| {
                    Ok(PyBytes::new(py, cached_data).into())
                });
            }
        }
        
        // Cache miss - read from memory map
        if offset + size > self.file_size {
            return Err(PyErr::new::<pyo3::exceptions::PyIndexError, _>(
                "Read beyond file bounds"
            ));
        }
        
        let data = &self.mmap[offset..offset + size];
        
        // Cache small, frequently accessed data
        if size <= 64 {
            let mut cache = self.cache.write();
            if cache.len() < 10000 {  // Limit cache size
                let mut small_vec = SmallVec::new();
                small_vec.extend_from_slice(data);
                cache.insert(cache_key, small_vec);
            }
        }
        
        Python::with_gil(|py| {
            Ok(PyBytes::new(py, data).into())
        })
    }
    
    /// Get performance statistics
    fn get_performance_stats(&self) -> PyResult<PyObject> {
        let cache = self.cache.read();
        
        Python::with_gil(|py| {
            let stats = pyo3::types::PyDict::new(py);
            stats.set_item("cache_entries", cache.len())?;
            stats.set_item("file_size_mb", self.file_size as f64 / 1_048_576.0)?;
            stats.set_item("memory_mapped", true)?;
            Ok(stats.into())
        })
    }
}

/// SIMD-optimized pattern search
fn find_pattern_simd(haystack: &[u8], needle: &[u8]) -> Vec<usize> {
    if needle.is_empty() || haystack.len() < needle.len() {
        return vec![];
    }
    
    let mut positions = Vec::new();
    let first_byte = needle[0];
    
    // Use SIMD for first byte search on x86_64
    #[cfg(target_arch = "x86_64")]
    {
        if haystack.len() >= 32 {
            return find_pattern_avx2(haystack, needle);
        }
    }
    
    // Fallback to optimized scalar search
    for i in 0..=(haystack.len() - needle.len()) {
        if haystack[i] == first_byte && &haystack[i..i + needle.len()] == needle {
            positions.push(i);
        }
    }
    
    positions
}

#[cfg(target_arch = "x86_64")]
fn find_pattern_avx2(haystack: &[u8], needle: &[u8]) -> Vec<usize> {
    use std::arch::x86_64::*;
    
    let mut positions = Vec::new();
    let first_byte = needle[0];
    let needle_len = needle.len();
    
    unsafe {
        let first_broadcast = _mm256_set1_epi8(first_byte as i8);
        let mut i = 0;
        
        while i + 32 <= haystack.len() {
            let chunk = _mm256_loadu_si256(haystack.as_ptr().add(i) as *const __m256i);
            let matches = _mm256_cmpeq_epi8(chunk, first_broadcast);
            let mask = _mm256_movemask_epi8(matches) as u32;
            
            if mask != 0 {
                for bit in 0..32 {
                    if (mask & (1 << bit)) != 0 {
                        let pos = i + bit;
                        if pos + needle_len <= haystack.len() && 
                           &haystack[pos..pos + needle_len] == needle {
                            positions.push(pos);
                        }
                    }
                }
            }
            
            i += 32;
        }
        
        // Handle remaining bytes
        for j in i..=(haystack.len().saturating_sub(needle_len)) {
            if haystack[j] == first_byte && &haystack[j..j + needle_len] == needle {
                positions.push(j);
            }
        }
    }
    
    positions
}

/// Fast chunk parsing with minimal allocations
fn parse_chunk_fast(data: &[u8], base_offset: usize) -> Vec<SonarRecord> {
    let mut records = Vec::new();
    let mut offset = 0;
    
    while offset + std::mem::size_of::<SonarRecord>() <= data.len() {
        // Fast alignment check
        if offset % 4 == 0 && offset + 32 <= data.len() {
            // Try to parse as binary record
            if let Some(record) = try_parse_binary_record(&data[offset..], base_offset + offset) {
                records.push(record);
                offset += std::mem::size_of::<SonarRecord>();
                continue;
            }
        }
        
        offset += 1;
    }
    
    records
}

/// Attempt to parse binary record with validation
fn try_parse_binary_record(data: &[u8], file_offset: usize) -> Option<SonarRecord> {
    if data.len() < std::mem::size_of::<SonarRecord>() {
        return None;
    }
    
    // Basic sanity checks for binary data
    let potential_channel = u32::from_le_bytes([data[8], data[9], data[10], data[11]]);
    let potential_samples = u32::from_le_bytes([data[28], data[29], data[30], data[31]]);
    
    // Validate ranges
    if potential_channel > 16 || potential_samples > 100_000 {
        return None;
    }
    
    // Parse full record
    Some(SonarRecord {
        offset: file_offset as u64,
        channel_id: potential_channel,
        sequence: u32::from_le_bytes([data[12], data[13], data[14], data[15]]),
        timestamp_ms: u64::from_le_bytes([
            data[16], data[17], data[18], data[19],
            data[20], data[21], data[22], data[23],
        ]),
        latitude: f64::from_le_bytes([
            data[24], data[25], data[26], data[27],
            data[28], data[29], data[30], data[31],
        ]),
        longitude: f64::from_le_bytes([
            data[32], data[33], data[34], data[35],
            data[36], data[37], data[38], data[39],
        ]),
        depth_m: f32::from_le_bytes([data[40], data[41], data[42], data[43]]),
        sample_count: potential_samples,
        sonar_offset: u64::from_le_bytes([
            data[48], data[49], data[50], data[51],
            data[52], data[53], data[54], data[55],
        ]),
        sonar_size: u32::from_le_bytes([data[56], data[57], data[58], data[59]]),
        beam_angle: f32::from_le_bytes([data[60], data[61], data[62], data[63]]),
        pitch: f32::from_le_bytes([data[64], data[65], data[66], data[67]]),
        roll: f32::from_le_bytes([data[68], data[69], data[70], data[71]]),
        heave: f32::from_le_bytes([data[72], data[73], data[74], data[75]]),
        tx_offset: f32::from_le_bytes([data[76], data[77], data[78], data[79]]),
        rx_offset: f32::from_le_bytes([data[80], data[81], data[82], data[83]]),
        color_id: u16::from_le_bytes([data[84], data[85]]),
        reserved: 0,
    })
}

/// SIMD coordinate transformation
fn transform_coordinates_vectorized(
    lats: &[f64],
    lons: &[f64],
    heading: f64,
    offset_x: f64,
    offset_y: f64,
) -> (Vec<f64>, Vec<f64>) {
    let cos_h = heading.cos();
    let sin_h = heading.sin();
    
    let x_rot = offset_x * cos_h - offset_y * sin_h;
    let y_rot = offset_x * sin_h + offset_y * cos_h;
    
    let meters_to_deg_lat = 1.0 / 111320.0;
    
    let new_lats: Vec<f64> = lats
        .par_iter()
        .map(|&lat| lat + y_rot * meters_to_deg_lat)
        .collect();
    
    let new_lons: Vec<f64> = lats
        .par_iter()
        .zip(lons.par_iter())
        .map(|(&lat, &lon)| {
            let meters_to_deg_lon = 1.0 / (111320.0 * lat.to_radians().cos());
            lon + x_rot * meters_to_deg_lon
        })
        .collect();
    
    (new_lats, new_lons)
}

/// Convert Rust record to Python dictionary
fn record_to_python(py: Python, record: &SonarRecord) -> PyResult<PyObject> {
    let dict = pyo3::types::PyDict::new(py);
    
    dict.set_item("ofs", record.offset)?;
    dict.set_item("channel_id", record.channel_id)?;
    dict.set_item("seq", record.sequence)?;
    dict.set_item("time_ms", record.timestamp_ms)?;
    dict.set_item("lat", record.latitude)?;
    dict.set_item("lon", record.longitude)?;
    dict.set_item("depth_m", record.depth_m)?;
    dict.set_item("sample_cnt", record.sample_count)?;
    dict.set_item("sonar_ofs", record.sonar_offset)?;
    dict.set_item("sonar_size", record.sonar_size)?;
    dict.set_item("beam_deg", record.beam_angle)?;
    dict.set_item("pitch_deg", record.pitch)?;
    dict.set_item("roll_deg", record.roll)?;
    dict.set_item("heave_m", record.heave)?;
    dict.set_item("tx_ofs_m", record.tx_offset)?;
    dict.set_item("rx_ofs_m", record.rx_offset)?;
    dict.set_item("color_id", record.color_id)?;
    
    Ok(dict.into())
}

/// Performance-optimized CSV writer
#[pyclass]
pub struct FastCSVWriter {
    buffer: String,
    capacity: usize,
}

#[pymethods]
impl FastCSVWriter {
    #[new]
    fn new(initial_capacity: usize) -> Self {
        FastCSVWriter {
            buffer: String::with_capacity(initial_capacity),
            capacity: initial_capacity,
        }
    }
    
    fn write_record(&mut self, record: PyObject) -> PyResult<()> {
        Python::with_gil(|py| {
            let dict = record.downcast::<pyo3::types::PyDict>(py)?;
            
            // Pre-allocate for performance
            if self.buffer.capacity() - self.buffer.len() < 512 {
                self.buffer.reserve(self.capacity);
            }
            
            // Build CSV row with minimal allocations
            self.buffer.push_str(&format!(
                "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},\"{}\"\n",
                dict.get_item("ofs")?.unwrap(),
                dict.get_item("channel_id")?.unwrap(),
                dict.get_item("seq")?.unwrap(),
                dict.get_item("time_ms")?.unwrap(),
                dict.get_item("lat")?.unwrap(),
                dict.get_item("lon")?.unwrap(),
                dict.get_item("depth_m")?.unwrap(),
                dict.get_item("sample_cnt")?.unwrap(),
                dict.get_item("sonar_ofs")?.unwrap(),
                dict.get_item("sonar_size")?.unwrap(),
                dict.get_item("beam_deg")?.unwrap(),
                dict.get_item("pitch_deg")?.unwrap(),
                dict.get_item("roll_deg")?.unwrap(),
                dict.get_item("heave_m")?.unwrap(),
                dict.get_item("tx_ofs_m")?.unwrap(),
                dict.get_item("rx_ofs_m")?.unwrap(),
                dict.get_item("color_id")?.unwrap(),
                "{}" // Placeholder for extras_json
            ));
            
            Ok(())
        })
    }
    
    fn get_buffer(&self) -> String {
        self.buffer.clone()
    }
    
    fn clear(&mut self) {
        self.buffer.clear();
    }
}

/// Python module initialization
#[pymodule]
fn rsd_performance_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<FastBinaryParser>()?;
    m.add_class::<FastCSVWriter>()?;
    
    m.add_function(wrap_pyfunction!(benchmark_simd_search, m)?)?;
    
    Ok(())
}

/// Benchmark function for SIMD pattern search
#[pyfunction]
fn benchmark_simd_search(data: Vec<u8>, pattern: Vec<u8>, iterations: usize) -> PyResult<f64> {
    let start = std::time::Instant::now();
    
    for _ in 0..iterations {
        let _positions = find_pattern_simd(&data, &pattern);
    }
    
    let elapsed = start.elapsed();
    Ok(elapsed.as_secs_f64())
}