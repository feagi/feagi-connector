use ndarray::{Array3, Zip};

pub struct ImageDiff  {
    latest: Array3<u8>,
    previous: Array3<u8>,
}


impl ImageDiff {
    pub fn new(image_width: usize, image_height: usize, color_depth: usize) -> Self {
        ImageDiff {
            latest: Array3::zeros((color_depth, image_height, image_width)),   // z, y, x order!
            previous: Array3::zeros((color_depth, image_height, image_width)),
        }
    }


    pub fn create_gray_scale(image_width: usize, image_height: usize) -> Self {
        let color_depth: usize = 1;
        Self::new(image_width, image_height, color_depth)
    }

    pub fn create_rgb(image_width: usize, image_height: usize) -> Self {
        let color_depth: usize = 3;
        Self::new(image_width, image_height, color_depth)
    }

    /// Returns the shape of the internal array (color_depth, height, width)
    pub fn shape(&self) -> (usize, usize, usize) {
        let shape = self.latest.shape();
        (shape[0], shape[1], shape[2])
    }

    pub fn get_new_delta_from_new_frame(&mut self, new_image_frame: Array3<u8>) -> Result<Array3<u8>, String> {
        // Shape check for sanity
        if new_image_frame.shape() != self.latest.shape() {
            return Err(format!(
                "Resolution mismatch! Expected {:?}, got {:?}",
                self.latest.shape(),
                new_image_frame.shape()
            ));
        }

        // TODO we will need to use a different comparison algorithm
        let mut diff = Array3::zeros(self.latest.dim());

        // In place subtraction with saturating subtraction to avoid overflow
        Zip::from(&mut diff)
            .and(&new_image_frame)
            .and(&self.latest)
            .for_each(|d, &new, &old| {
                // Use saturating_sub to prevent overflow
                *d = new.saturating_sub(old);
            });

        // In place replacement
        self.previous = std::mem::replace(&mut self.latest, new_image_frame);

        Ok(diff)
    }
}