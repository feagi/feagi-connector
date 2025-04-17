use pyo3::prelude::*;
use pyo3::types::PyModule;
use numpy::{IntoPyArray, PyArray3, PyReadonlyArray3};
use rust_core_sensiomotor_functions::ImageDiff;
use ndarray::{Array3, ArrayView3};

#[pyclass]
#[pyo3(name = "ImageDiff")]
struct PyImageDiff {
    inner: ImageDiff,
}

#[pymethods]
impl PyImageDiff {
    #[new]
    fn new(image_width: usize, image_height: usize, color_depth: usize) -> PyResult<Self> {
        // TODO error handling
        Ok(Self {
            inner: ImageDiff::new(image_width, image_height, color_depth),
        })
    }

    /// Returns the shape of the image as (height, width, channels)
    fn shape(&self) -> (usize, usize, usize) {
        let rust_shape = self.inner.shape();
        // Convert from Rust's (channels, height, width) to Python's (height, width, channels) 
        (rust_shape.1, rust_shape.2, rust_shape.0)
    }

    /// Returns the new delta from the new frame
    fn get_new_delta_from_new_frame<'py>(&mut self, py: Python<'py>, input: PyReadonlyArray3<'py, u8>) -> &'py PyArray3<u8> {
        let input_array: ArrayView3<u8> = input.as_array();
        // Convert from ArrayView3 to owned Array3
        let owned_input = Array3::from_shape_vec(
            input_array.raw_dim(),
            input_array.iter().cloned().collect(),
        ).expect("Failed to convert input array");
        
        let output = self.inner.get_new_delta_from_new_frame(owned_input);

        
        output.into_pyarray(py)
    }
    */
}


#[pymodule]
fn rust_core_sensiomotor_functions_py(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyImageDiff>()?;
    m.add("__doc__", "Python bindings for FEAGI image processing functions")?;
    
    Ok(())
}
