#
# MIT License
#
# Copyright (c) 2024, Yebouet Cédrick-Armel
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# mypy: disable-error-code="misc, no-untyped-def, type-arg"
import itertools

import apache_beam as beam
import numpy as np
import pandas as pd
import tensorflow as tf
from astropy.stats import sigma_clip

from neuripsadc.etl.ops import make_example
from neuripsadc.utilis import save_to_tfrecords


class CalibrationFn(beam.DoFn):
    """Perfroms the raw data calibration."""

    def __init__(
        self,
        cut_inf: int,
        cut_sup: int,
        mask: bool,
        corr: bool,
        dark: bool,
        flat: bool,
        signature: tuple,
        binning: int | None = None,
    ):
        """
        Args:
            cut_inf (int): Images cropping range lower limit.
            cut_sup (int): Images cropping range upper limit.
            binning (int | None): Number of images to bin together.
            mask (bool): Wheteher to mask dead and hot pixels.
            corr (bool): Wheteher to apply linear correction.
            dark (bool): Whether to apply current dark correction.
            flat (bool): Whether to apply flat pixels correction.
            signature (tuple): List of tf.TypeSpec
        """

        self.CUT_INF = cut_inf
        self.CUT_SUP = cut_sup
        self.BINNING = binning
        self.MASK = mask
        self.CORR = corr
        self.DARK = dark
        self.FLAT = flat
        self.signature = signature

    def process(self, element):  # type: ignore
        id, uris, timestamp = element
        airs_data, fgs_data, info_data = self._load_data(id, uris)
        airs_signal = self._calibrate_airs_data(airs_data, info_data)
        airs_signal = tf.convert_to_tensor(airs_signal.reshape(1, *airs_signal.shape))
        fgs_signal = self._calibrate_fgs_data(fgs_data, info_data)
        fgs_signal = tf.convert_to_tensor(fgs_signal.reshape(1, *fgs_signal.shape))
        labels = (
            np.array([np.nan]) if info_data["labels"] is None else info_data["labels"]
        )
        labels = tf.convert_to_tensor(labels.reshape(1, *labels.shape))
        record = tf.data.Dataset.from_generator(
            lambda: iter([(int(id), airs_signal, fgs_signal, labels)]),
            output_signature=self.signature,
        )
        record = record.map(
            lambda id, airs, fgs, target: tf.py_function(
                func=make_example, inp=[id, airs, fgs, target], Tout=tf.string
            )
        )
        bucket = uris[0].split("/")[2]
        tmp_output_path = (
            f"gs://{bucket}/pipeline_root/neurips-etl/{timestamp}/record-{id}.tfrecord"
        )
        save_to_tfrecords(record, tmp_output_path)
        return [tmp_output_path]

    def _calibrate_airs_data(
        self, data: dict[str, pd.DataFrame], info: dict[str, pd.DataFrame]
    ) -> np.ndarray:
        """AIRS-CH0 device's data calibration logic.

        Args:
            data (dict[str, pd.DataFrame]): The raw ADC converted data.
            info (dict[str, pd.DataFrame]): Informations for calibration.

        Returns:
            np.ndarray: Cleand and calibrated data.
        """
        signal = self._adc_revert(
            data["signal"], info["airs_gain"], info["airs_offset"]
        )
        dt = info["airs_it"]
        dt[1::2] += 0.1
        signal = signal[:, :, self.CUT_INF : self.CUT_SUP]
        if self.MASK:
            signal = self._mask_hot_dead(signal, data["dead"], data["dark"])
        if self.CORR:
            signal = self._apply_linear_corr(data["linear_corr"], signal)
        if self.DARK:
            signal = self._clean_dark_current(signal, data["dead"], data["dark"], dt)
        signal = self._get_cds(signal)
        if self.BINNING:
            signal = self._bin_obs(signal, self.BINNING)
        else:
            signal = signal.transpose(0, 2, 1)
        if self.FLAT:
            signal = self._correct_flat_field(data["flat"], data["dead"], signal)
        return signal

    def _calibrate_fgs_data(
        self, data: dict[str, pd.DataFrame], info: dict[str, pd.DataFrame]
    ) -> np.ndarray:
        """FGS device's data calibration logic.

        Args:
            data (dict[str, pd.DataFrame]): The raw ADC converted data.
            info (dict[str, pd.DataFrame]): Informations for calibration.

        Returns:
            np.ndarray: Cleand and calibrated data.
        """
        signal = self._adc_revert(data["signal"], info["fgs_gain"], info["fgs_offset"])
        dt = np.ones(len(signal)) * 0.1
        dt[1::2] += 0.1
        if self.MASK:
            signal = self._mask_hot_dead(signal, data["dead"], data["dark"])
        if self.CORR:
            signal = self._apply_linear_corr(data["linear_corr"], signal)
        if self.DARK:
            signal = self._clean_dark_current(signal, data["dead"], data["dark"], dt)
        signal = self._get_cds(signal)
        if self.BINNING:
            signal = self._bin_obs(signal, self.BINNING * 12)
        else:
            signal = signal.transpose(0, 2, 1)
        if self.FLAT:
            signal = self._correct_flat_field(data["flat"], data["dead"], signal)
        return signal

    def _adc_revert(self, signal: np.ndarray, gain: float, offset: float) -> np.ndarray:
        """Revert pixel voltage from ADC.

        Args:
            signal (np.ndarray): ADC converted signal integer.
            gain (float): ADC gain error.
            offset (float): ADC offset error.

        Returns:
            np.ndarray: Pixel voltages.
        """
        signal = signal.astype(np.float64)
        signal /= gain
        signal += offset
        return signal

    def _mask_hot_dead(
        self, signal: np.ndarray, dead: np.ndarray, dark: np.ndarray
    ) -> np.ndarray:
        """Mask dead and hot pixels so that they won't be took\
            in account in corrections.

        Args:
            signal (np.ndarray): Pixel voltage signal.
            dead (np.ndarray): Dead pixels.
            dark (np.ndarray): Dark pixels.

        Returns:
            np.ndarray: Pixel voltages with dead pixels masked.
        """
        hot = sigma_clip(dark, sigma=5, maxiters=5).mask
        hot = np.tile(hot, (signal.shape[0], 1, 1))
        dead = np.tile(dead, (signal.shape[0], 1, 1))
        signal = np.ma.masked_where(dead, signal)
        signal = np.ma.masked_where(hot, signal)
        return signal

    def _apply_linear_corr(self, corr: np.ndarray, signal: np.ndarray) -> np.ndarray:
        """Fix non-linearity due to capacity leakage in the detector.

        Args:
            corr (np.ndarray): Correction coefficients
            signal (np.ndarray): Signal to correct.

        Returns:
            np.ndarray: Corrected signal
        """
        linear_corr = np.flip(corr, axis=0)
        for x, y in itertools.product(range(signal.shape[1]), range(signal.shape[2])):
            poli = np.poly1d(linear_corr[:, x, y])
            signal[:, x, y] = poli(signal[:, x, y])
        return signal

    def _clean_dark_current(
        self, signal: np.ndarray, dead: np.ndarray, dark: np.ndarray, dt: np.ndarray
    ) -> np.ndarray:
        """Remove the accumulated charge due to dark current.

        Args:
            signal (np.ndarray): Signal to clean
            dead (np.ndarray): Dead pixels.
            dark (np.ndarray): Dark pixels.
            dt (np.array): Short frames delay.

        Returns:
            np.ndarray: Cleaned signal.
        """
        dark = np.ma.masked_where(dead, dark)
        dark = np.tile(dark, (signal.shape[0], 1, 1))

        signal -= dark * dt[:, np.newaxis, np.newaxis]
        return signal

    def _get_cds(self, signal: np.ndarray) -> np.ndarray:
        """Return the actual accumulated charge (a delta) due to the transit.

        Args:
            signal (np.ndarray): Signal.

        Returns:
            np.ndarray: An image for one observation in the time\
                  (Time series observations).
        """
        cds = signal[1::2, :, :] - signal[::2, :, :]
        return cds

    def _bin_obs(self, cds: np.ndarray, binning: int) -> np.ndarray:
        """Binnes cds time series together at the specified frequency.

        Args:
            cds (np.ndarray): CDS signal.
            binning (int): Binning frequency.

        Returns:
            np.ndarray: _description_
        """
        cds_transposed = cds.transpose(0, 2, 1)
        cds_binned = np.zeros(
            (
                cds_transposed.shape[0] // binning,
                cds_transposed.shape[1],
                cds_transposed.shape[2],
            )
        )
        for i in range(cds_transposed.shape[0] // binning):
            cds_binned[i, :, :] = np.sum(
                cds_transposed[i * binning : (i + 1) * binning, :, :], axis=0
            )
        return cds_binned

    def _correct_flat_field(
        self, flat: np.ndarray, dead: np.ndarray, signal: np.ndarray
    ) -> np.ndarray:
        """Correction by calibrating on an uniform signal.

        Args:
            flat (np.ndarray): Flat signal
            dead (np.ndarray): Dead pixels
            signal (np.ndarray): CDS signal
        """

        flat = flat.transpose(1, 0)
        dead = dead.transpose(1, 0)
        flat = np.ma.masked_where(dead, flat)
        flat = np.tile(flat, (signal.shape[0], 1, 1))
        signal = signal / flat
        return signal

    def _load_data(self, pid: int, uris: list[str]) -> tuple:
        """
        Load data from a list of URIs, reading the files as CSV or Parquet,
        and organize them by type ('dark', 'dead', etc.) for AIRS and FGS.

        Args:
            pid (int): Planet's id.
            uris (List[str]): List of URIs to load data from.
        """
        airs_data = {}
        fgs_data = {}
        info_data = {}
        calib_data_types = [
            "dark",
            "dead",
            "flat",
            "linear_corr",
            "read",
            "signal",
            "labels",
            "axis_info",
            "adc_info",
        ]

        def read_data(uri: str):
            try:
                return pd.read_csv(uri)
            except UnicodeDecodeError:
                return pd.read_parquet(uri)

        for uri in uris:
            df = read_data(uri)
            for data_type in calib_data_types:
                if data_type in uri:
                    if "AIRS" in uri:
                        if "signal" in uri:
                            airs_data[data_type] = df.values.astype(np.float64).reshape(
                                (df.shape[0], 32, 356)
                            )
                        elif "linear_corr" in uri:
                            airs_data[data_type] = df.values.astype(np.float64).reshape(
                                (6, 32, 356)
                            )[:, :, self.CUT_INF : self.CUT_SUP]
                        else:
                            airs_data[data_type] = df.values.astype(np.float64).reshape(
                                (32, 356)
                            )[:, self.CUT_INF : self.CUT_SUP]
                    elif "FGS" in uri:
                        if "signal" in uri:
                            fgs_data[data_type] = df.values.astype(np.float64).reshape(
                                (df.shape[0], 32, 32)
                            )
                        elif "linear_corr" in uri:
                            fgs_data[data_type] = df.values.astype(np.float64).reshape(
                                (6, 32, 32)
                            )
                        else:
                            fgs_data[data_type] = df.values.astype(np.float64).reshape(
                                (32, 32)
                            )
                    else:
                        try:
                            info_data[data_type] = df.set_index("planet_id").loc[
                                int(pid)
                            ]
                        except KeyError:
                            if "labels" in uri:
                                info_data[data_type] = None
                            elif "axis_info" in uri:
                                info_data[data_type] = df
                            else:
                                pass
        info_data["fgs_gain"] = info_data["adc_info"]["FGS1_adc_gain"]
        info_data["fgs_offset"] = info_data["adc_info"]["FGS1_adc_offset"]
        info_data["airs_gain"] = info_data["adc_info"]["AIRS-CH0_adc_gain"]
        info_data["airs_offset"] = info_data["adc_info"]["AIRS-CH0_adc_offset"]
        if info_data["labels"] is not None:
            info_data["labels"] = info_data["labels"].values
        info_data["airs_it"] = (
            info_data["axis_info"]["AIRS-CH0-integration_time"].dropna().values
        )
        del info_data["adc_info"], info_data["axis_info"]
        return airs_data, fgs_data, info_data


class CombineDataFn(beam.CombineFn):
    """Combine all ParDo outpus in one collection"""

    def create_accumulator(self):
        return (None, [])

    def add_input(self, accumulator, input):
        _, bag = accumulator
        if bag is None:
            bag = []
        bag.append(input)
        return (None, bag)

    def merge_accumulators(self, accumulators):
        merge = []
        for _, item in accumulators:
            merge.extend(item)
        return (None, merge)

    def extract_output(self, merge):
        _, merge = merge
        return [merge]
