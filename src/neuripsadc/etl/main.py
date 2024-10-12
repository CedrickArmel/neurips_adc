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

import argparse
import logging

import apache_beam as beam
import tensorflow as tf
from apache_beam.options.pipeline_options import (
    PipelineOptions,
    SetupOptions,
    _BeamArgumentParser,
)
from apache_beam.options.value_provider import RuntimeValueProvider

from neuripsadc.etl.ops import get_raw_data_uris, save_dataset_to_tfrecords
from neuripsadc.etl.transforms import CalibrationFn, CombineDataFn


class ETLOptions(PipelineOptions):
    """Custom Beam options for the ETL pipeline"""

    @classmethod
    def _add_argparse_args(cls, parser: _BeamArgumentParser) -> None:
        parser.add_value_provider_argument(
            "--source",
            type=str,
            required=True,
            help="GCS path containing the source data.",
        )
        parser.add_value_provider_argument(
            "--output",
            type=str,
            required=True,
            help="GCS URI or local path where the resulting TFRecord dataset will be stored (e.g., gs://bucket/output/ds.tfrecords).",
        )
        parser.add_value_provider_argument(
            "--cutinf",
            type=int,
            required=False,
            default=39,
            help="Lower bound (inclusive) for the cut range on the data. Default is 39.",
        )
        parser.add_value_provider_argument(
            "--cutsup",
            type=int,
            required=False,
            default=321,
            help="Upper bound (inclusive) for the cut range on the data. Default is 321.",
        )
        parser.add_value_provider_argument(
            "--mask",
            required=False,
            action="store_true",
            help="Apply a mask to the hot and dead pixels in the data.",
        )
        parser.add_value_provider_argument(
            "--corr",
            required=False,
            action="store_true",
            help="Apply non-linear accumulation corrections to the data.",
        )
        parser.add_value_provider_argument(
            "--dark",
            required=False,
            action="store_true",
            help="Apply current dark correction.",
        )
        parser.add_value_provider_argument(
            "--flat",
            required=False,
            action="store_true",
            help="Apply calibration against a flat (uniform signal).",
        )
        parser.add_value_provider_argument(
            "--binning",
            type=int,
            required=False,
            default=30,
            help="Binning factor for the data, which aggregates adjacent images to reduce data size. Default is 30.",
        )


class LogValueProviderFn(beam.DoFn):
    def process(self):
        args = [
            "source",
            "output",
            "cutinf",
            "cutsup",
            "mask",
            "corr",
            "dark",
            "flat",
            "binning",
        ]
        for arg in args:
            logging.info(f"""{arg} : {RuntimeValueProvider.get_value(arg, str, "")}""")


def run_pipeline(argv: list | None = None, save_session: bool = True):
    parser = argparse.ArgumentParser()
    _, pipeline_args = parser.parse_known_args(argv)
    etloptions = ETLOptions(pipeline_args).view_as(SetupOptions)
    etloptions.save_main_session = save_session
    bucket = etloptions.source.get().split("/")[0]
    folder = "/".join(etloptions.source.get().split("/")[1:])
    with beam.Pipeline(options=etloptions) as pipeline:
        uris = get_raw_data_uris(bucket, folder)
        _ = (
            pipeline
            | beam.Create([None])  # noqa: W503
            | "Options and arguments logging"  # noqa: W503
            >> beam.ParDo(LogValueProviderFn())  # noqa: W503
        )
        _ = (
            pipeline
            | "Create uris collection" >> beam.Create(uris)  # noqa: W503
            | "Data calibration"  # noqa: W503
            >> beam.ParDo(  # noqa: W503
                CalibrationFn(
                    etloptions.cutinf.get(),
                    etloptions.cutsup.get(),
                    etloptions.mask.get(),
                    etloptions.corr.get(),
                    etloptions.dark.get(),
                    etloptions.flat.get(),
                    etloptions.binning.get(),
                )
            )
            | "Collection merging"  # noqa: W503
            >> beam.CombineGlobally(CombineDataFn())  # noqa: W503
            | "Data saving"  # noqa: W503
            >> beam.Map(  # noqa: W503
                lambda x: save_dataset_to_tfrecords(
                    element=x,
                    uri=etloptions.output.get(),
                    output_signature=(
                        tf.TensorSpec(shape=None, dtype=tf.int64),
                        tf.TensorSpec(shape=None, dtype=tf.float64),
                        tf.TensorSpec(shape=None, dtype=tf.float64),
                        tf.TensorSpec(shape=None, dtype=tf.float64),
                    ),
                )
            )
        )


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    run_pipeline()
