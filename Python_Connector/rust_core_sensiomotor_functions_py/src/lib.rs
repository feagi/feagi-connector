use pyo3::prelude::*;
use numpy::{IntoPyArray, PyArray3, PyReadonlyArray3};
use rust_core_sensiomotor_functions::ImageDiff;
use ndarray::ArrayView3;

#[pyclass]
struct PyImageDiff {
    inner: ImageDiff,
}

#[pymethods]
impl PyImageDiff {
    #[new]
    fn new(image_width: usize, image_height: usize, color_depth: usize) -> Self {
        Self {
            inner: ImageDiff::new(image_width, image_height, color_depth),
        }
    }

    fn get_new_delta_from_new_frame<'py>(
        &self,
        py: Python<'py>,
        input: PyReadonlyArray3<'py, u8>,
    ) -> &'py PyArray3<u8> {
        let input_array: ArrayView3<u8> = input.as_array();
        let output = self.inner.get_new_delta_from_new_frame(&input_array);
        output.into_pyarray(py)
    }
}


#[pymodule]
fn FEAGI_Connector(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PyImageDiff>()?;
    Ok(())
}
