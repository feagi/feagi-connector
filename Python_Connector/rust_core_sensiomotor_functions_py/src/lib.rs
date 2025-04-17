use pyo3::prelude::*;
use numpy::{IntoPyArray, PyArray3, PyReadonlyArray3};
use rust_core_sensiomotor_functions::ImageDiff;
use ndarray::{Array3, ArrayView3};

#[pyclass]
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

    /*
    fn get_new_delta_from_new_frame<'py>(
        &mut self,
        py: Python<'py>,
        input: PyReadonlyArray3<'py, u8>,
    ) -> &'py PyArray3<u8> {
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
fn FEAGI_Connector(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyImageDiff>()?;
    Ok(())
}
