import tensorflow as tf
import json
import os
import numpy as np


def model_fn(model_dir):
    """Load the Keras model and character mappings."""
    model = tf.keras.models.load_model(os.path.join(model_dir, "superheromodel_v2.keras"))

    with open(os.path.join(model_dir, "char_to_index.json"), "r") as f:
        char_to_index = json.load(f)

    with open(os.path.join(model_dir, "index_to_char.json"), "r") as f:
        index_to_char = json.load(f)

    return {
        "model": model,
        "char_to_index": char_to_index,
        "index_to_char": index_to_char,
    }


def input_fn(request_body, request_content_type):
    """Parse incoming request."""
    if request_content_type == "application/json":
        return json.loads(request_body)
    raise ValueError(f"Unsupported content type: {request_content_type}")


def predict_fn(input_data, model_dict):
    """Generate a superhero name from the seed string."""
    model = model_dict["model"]
    char_to_index = model_dict["char_to_index"]
    index_to_char = model_dict["index_to_char"]

    seed = input_data.get("seed", "").lower()
    max_len = 33

    def name_to_seq(name):
        return [char_to_index[char] for char in name if char in char_to_index]

    for _ in range(33):
        seq = name_to_seq(seed)
        padded = tf.keras.preprocessing.sequence.pad_sequences(
            [seq], maxlen=max_len - 1, padding="pre", truncating="pre"
        )
        pred = model.predict(padded, verbose=0)[0]
        pred_char = index_to_char[str(tf.argmax(pred).numpy())]
        seed += pred_char

        if pred_char == "\t":
            break

    return {"name": seed.strip()}


def output_fn(prediction, accept):
    """Format the output."""
    return json.dumps(prediction), "application/json"
