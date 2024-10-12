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

import tensorflow as tf
from google.cloud import storage


def list_blobs(bucket_name: str, folder: str | None = None) -> list[str]:
    """List the object in the bucket (folder).

    Args:
        bucket_name (str): Bucket to consider.
        folder (str | None, optional): Folder to whose elements to list.\
            Defaults to None.

    Returns:
        list[str]: Listed objects' uris.
    """
    storage_client = storage.Client()
    blobs = storage_client.list_blobs(bucket_name)
    if folder:
        folder_objects = []
        for blob in blobs:
            if blob.name.startswith(folder):
                folder_objects.append("gs://" + bucket_name + "/" + blob.name)
        return folder_objects
    else:
        return ["gs://" + bucket_name + "/" + blob.name for blob in blobs]


def save_to_tfrecords(dataset: tf.data.Dataset, path: str) -> None:
    """Save a dataset to TFRecord.

    Args:
        dataset (tf.data.Dataset): A Tensorflow Dataset
        path (str): Path to save the dataset
    """
    with tf.io.TFRecordWriter(path) as file_writer:
        for record in dataset:
            try:
                file_writer.write(record.numpy())
            except AttributeError:
                file_writer.write(record)
