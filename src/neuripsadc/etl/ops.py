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
from collections import defaultdict
from typing import Any

import tensorflow as tf

from neuripsadc.utilis import list_blobs, save_to_tfrecords


def group_by_key(key_value: list[tuple[Any, Any]]) -> list[list[Any]]:
    """
    Group a list of key-value pairs by key.

    Args:
        key_value (List[Tuple[Any, Any]]): List of tuples where each tuple contains a\
              key and a value.

    Returns:
        List[List[Any]]: A list of lists where each sublist contains the key and a list\
              of associated values.
    """
    grouped_data = defaultdict(list)
    for key, value in key_value:
        grouped_data[key].append(value)
    return [[key, values] for key, values in grouped_data.items()]


def split_key_value(path: str) -> tuple[str, str | None]:
    """Retrieve key-value from a GCS URIS.

    Args:
        path (str): A GCS object uri.

    Returns:
        tuple[str, str | None]: _description_
    """
    splitted_path = path.split("/")
    if len(splitted_path) <= 5:
        return (
            splitted_path[3],
            "/".join(splitted_path) if splitted_path[4] != "" else None,
        )
    else:
        return (splitted_path[5], "/".join(splitted_path))


def get_raw_data_uris(
    bucket_name: str, folder: str | None = None
) -> list[tuple[str, list[str]]]:
    """
    Get the data URIs in the Google Cloud Storage bucket.

    Args:
        bucket_name (str): Bucket to consider.
        floder (str): Folder to whose elements to list. Defaults to None.

    Returns:
        list[tuple[str, list[str]]]: List of tuples where each tuple has the planet ID\
              as the key and its data as the value.
    """
    paths = list_blobs(bucket_name, folder)
    key_value_pairs = [split_key_value(path=path) for path in paths]
    raw_data = [
        item[1] for item in key_value_pairs if item[0] == "raw" and item[1] is not None
    ]
    non_raw_data = [item for item in key_value_pairs if item[0] != "raw"]
    grouped_data = group_by_key(non_raw_data)
    result = [(key, value + raw_data) for key, value in grouped_data]
    return result


def make_example(pid: int, airs: tf.Tensor, fgs: tf.Tensor, target: tf.Tensor):
    """Return a serialized tf.train.Example.

    Args:
        pid (int): Planet's ID
        airs (tf.Tensor): Calibrated AIRS data
        fgs (tf.Tensor): Calibrated AIRS data
        target (tf.Tensor): The ML task target
    """
    id_ft = tf.train.Feature(int64_list=tf.train.Int64List(value=[pid]))
    airs_ft = tf.train.Feature(
        bytes_list=tf.train.BytesList(
            value=[
                tf.io.serialize_tensor(airs).numpy(),
            ]
        )
    )
    fgs_ft = tf.train.Feature(
        bytes_list=tf.train.BytesList(
            value=[
                tf.io.serialize_tensor(fgs).numpy(),
            ]
        )
    )
    target_ft = tf.train.Feature(
        bytes_list=tf.train.BytesList(value=[tf.io.serialize_tensor(target).numpy()])
    )
    features = tf.train.Features(
        feature={"id": id_ft, "airs": airs_ft, "fgs": fgs_ft, "target": target_ft}
    )
    example = tf.train.Example(features=features)
    return example.SerializeToString()


def save_dataset_to_tfrecords(
    element: list[Any],
    uri: str,
    output_signature: tuple[Any, Any, Any, Any] | None = None,
):
    """Creates a tf.data.Dataset form a PCollection and save it to a TFRecord.

    Args:
        element (list): _description_
        uri (str): Location to save the data. Can be a filesystem or a (GCS) bucket.
        output_signature (tuple | None, optional): Tensorflow Output type\
              specification. Defaults to None.
    """
    examples = element[0]
    dataset = tf.data.Dataset.from_generator(
        lambda: iter(examples),
        # output signature important car sans ça TF essaye de concatener tous
        # les éléments du tuple dans un unique tensor ce qui crée des erreurs.
        output_signature=output_signature,
    )
    dataset = dataset.map(
        lambda id, airs, fgs, target: tf.py_function(
            func=make_example, inp=[id, airs, fgs, target], Tout=tf.string
        )
    )
    save_to_tfrecords(dataset, uri)
