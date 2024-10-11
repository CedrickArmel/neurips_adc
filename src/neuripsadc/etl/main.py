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
# noqa: W503

import argparse
import logging

import apache_beam as beam
import tensorflow as tf
from apache_beam.options.pipeline_options import PipelineOptions, SetupOptions

from neuripsadc.etl.ops import get_raw_data_uris, save_dataset_to_tfrecords
from neuripsadc.etl.transforms import CalibrationFn, CombineDataFn


def run_pipeline(argv: list | None = None, save_session: bool = True):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=str,
        required=True,
        help="Data source location. eg: bucket/folder",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output location uri for the TFRecord dataset",
    )
    parser.add_argument("--cutinf", type=int, required=False, default=39, help="")
    parser.add_argument("--cutsup", type=int, required=False, default=321, help="")
    parser.add_argument("--mask", required=False, action="store_true", help="")
    parser.add_argument("--corr", required=False, action="store_true", help="")
    parser.add_argument("--dark", required=False, action="store_true", help="")
    parser.add_argument("--flat", required=False, action="store_true", help="")
    parser.add_argument("--binning", type=int, required=False, default=30, help="")
    known_args, pipeline_args = parser.parse_known_args(argv)
    bucket = known_args.source.split("/")[0]
    folder = "/".join(known_args.source.split("/")[1:])
    options = PipelineOptions(pipeline_args)
    options.view_as(SetupOptions).save_main_session = save_session
    with beam.Pipeline(options=options) as pipeline:
        uris = get_raw_data_uris(bucket, folder)
        _ = (
            pipeline
            | "Create uris collection" >> beam.Create(uris)  # noqa: W503
            | "Data calibration"  # noqa: W503
            >> beam.ParDo(  # noqa: W503
                CalibrationFn(
                    known_args.cutinf,
                    known_args.cutsup,
                    known_args.mask,
                    known_args.corr,
                    known_args.dark,
                    known_args.flat,
                    known_args.binning,
                )
            )
            | "Collection merging"  # noqa: W503
            >> beam.CombineGlobally(CombineDataFn())  # noqa: W503
            | "Data saving"  # noqa: W503
            >> beam.Map(  # noqa: W503
                lambda x: save_dataset_to_tfrecords(
                    element=x,
                    uri=known_args.output,
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
