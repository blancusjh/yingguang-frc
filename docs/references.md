# References and attribution

The model follows the device dimensions and field orientations described in:

- Sun et al. (2013), *Acta Physica Sinica* **62**, 078407.
  [DOI: 10.7498/aps.62.078407](https://doi.org/10.7498/aps.62.078407).
  Section 2.3 specifies mirror polarity relative to the bias and main drive.
- Sun et al. (2017), *Matter and Radiation at Extremes* **2**, 263.
  [DOI: 10.1016/j.mre.2017.07.003](https://doi.org/10.1016/j.mre.2017.07.003).
  Used for device field calibration and experimental context.

The publications are not redistributed by this repository. Consult the
publisher versions for scientific claims.

The solver is [WarpX](https://github.com/BLAST-WarpX/warpx), upstream revision
`312d507407a1bf6f01ae43fb41b5c3a3700d053c`.
Its RZ hybrid-PIC cylinder-compression example informed the simulation setup.
This repository is a separate device model, not a WarpX distribution.

Use [CITATION.cff](../CITATION.cff) to cite this repository, and include the
commit and configuration used for any new result.
