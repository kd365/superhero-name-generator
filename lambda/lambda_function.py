import json
import math
import boto3
import time
import random

sagemaker_runtime = boto3.client("sagemaker-runtime", region_name="us-east-1")
bedrock_runtime = boto3.client("bedrock-runtime", region_name="us-east-1")

SAGEMAKER_ENDPOINT = "superhero-lstm-endpoint"

# Character mappings for the LSTM model (28-char vocabulary)
CHAR_TO_INDEX = {
    "\t": 1, "a": 2, "e": 3, "r": 4, "o": 5, "n": 6, "i": 7, " ": 8,
    "t": 9, "s": 10, "l": 11, "m": 12, "h": 13, "d": 14, "c": 15,
    "u": 16, "g": 17, "k": 18, "b": 19, "p": 20, "y": 21, "w": 22,
    "f": 23, "v": 24, "j": 25, "z": 26, "x": 27, "q": 28,
}
INDEX_TO_CHAR = {v: k for k, v in CHAR_TO_INDEX.items()}
MAX_SEQ_LEN = 32  # max_len - 1

# Words Titan commonly flags even in innocent contexts
FLAGGED_TERMS = {
    "shadow", "dark", "venom", "doom", "strike", "blaze",
    "storm", "fury", "rage", "chaos", "void", "death",
    "blood", "fire", "war", "clash", "fist", "punch",
    "killer", "destroy", "wrath", "terror", "phantom",
    "night", "evil", "demon", "reaper", "savage",
}

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def sanitize_for_image(name):
    """Remove words that Titan's content filter commonly flags."""
    words = name.split()
    safe_words = [w for w in words if w.lower() not in FLAGGED_TERMS]
    return " ".join(safe_words) if safe_words else "Captain Sunshine"


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        body = json.loads(event.get("body", "{}"))
        seed = body.get("seed", "").strip()
        mode = body.get("mode", "classic")

        if not seed:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Seed text is required"}),
            }

        if len(seed) > 100:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Seed must be 100 characters or less"}),
            }

        if mode == "classic":
            result = generate_classic(seed)
        elif mode == "bedrock":
            result = generate_bedrock(seed)
        else:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Invalid mode. Use 'classic' or 'bedrock'"}),
            }

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps(result),
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": str(e)}),
        }


def predict_next_char(padded_seq):
    """Call SageMaker endpoint and return predictions array."""
    response = sagemaker_runtime.invoke_endpoint(
        EndpointName=SAGEMAKER_ENDPOINT,
        ContentType="application/json",
        Body=json.dumps({"instances": [padded_seq]}),
    )
    result = json.loads(response["Body"].read().decode("utf-8"))
    return result["predictions"][0]


def generate_name_from_seed(seed_text, temperature=0.8):
    """Run the LSTM generation loop with temperature sampling and tab suppression.

    Improvements:
    1. Auto-append space for word seeds (4+ chars) to encourage compound names
    2. Tab suppression — force at least MIN_GENERATED chars before allowing stop
    3. Temperature sampling — sample from distribution instead of argmax
    """
    TAB_INDEX = 1
    MIN_GENERATED = 3

    name = seed_text
    # Word seeds get a space appended so the model generates a second word
    # (e.g., "shadow " → "shadow stark" instead of immediately stopping)
    if len(name) >= 4 and not name.endswith(" "):
        name += " "

    iterations = 0
    total_confidence = 0.0
    generated_count = 0

    for i in range(40):
        seq = [CHAR_TO_INDEX[c] for c in name if c in CHAR_TO_INDEX]

        if len(seq) >= MAX_SEQ_LEN:
            padded = seq[-MAX_SEQ_LEN:]
        else:
            padded = [0] * (MAX_SEQ_LEN - len(seq)) + seq

        predictions = predict_next_char(padded)
        iterations += 1

        # Tab suppression: prevent early stopping before meaningful generation
        if generated_count < MIN_GENERATED:
            predictions[TAB_INDEX] = 0.0

        # Temperature sampling: scale logits and sample from distribution
        preds = [max(p, 1e-10) for p in predictions]
        log_preds = [math.log(p) / temperature for p in preds]
        max_lp = max(log_preds)
        exp_preds = [math.exp(lp - max_lp) for lp in log_preds]
        total = sum(exp_preds)
        probs = [ep / total for ep in exp_preds]

        # Weighted random selection
        r = random.random()
        cumulative = 0.0
        pred_index = 0
        for idx, prob in enumerate(probs):
            cumulative += prob
            if r <= cumulative:
                pred_index = idx
                break

        confidence = predictions[pred_index]
        total_confidence += confidence
        generated_count += 1

        pred_char = INDEX_TO_CHAR.get(pred_index, "")

        if pred_char == "\t":
            break

        name += pred_char

    avg_confidence = total_confidence / iterations if iterations > 0 else 0
    return name, iterations, avg_confidence


def generate_classic(seed):
    """Generate a superhero name using the LSTM model on SageMaker."""
    start_time = time.time()

    seed_lower = seed.lower()

    # generate_name_from_seed now handles word seeds natively via
    # auto-space, tab suppression, and temperature sampling —
    # no more truncation fallback needed
    name, iterations, avg_confidence = generate_name_from_seed(seed_lower)

    elapsed = time.time() - start_time
    final_name = name.strip().title()

    seed_retained = seed.lower()[:3] in final_name.lower()

    return {
        "mode": "classic",
        "name": final_name,
        "seed": seed,
        "metrics": {
            "latency_ms": round(elapsed * 1000),
            "iterations": iterations,
            "avg_confidence": round(avg_confidence, 3),
            "chars_generated": len(final_name) - len(seed),
            "name_length": len(final_name),
            "seed_retained": seed_retained,
            "model_params": "16,229",
            "model_type": "LSTM (character-level)",
        },
    }


def generate_bedrock(seed):
    """Generate a superhero name, backstory, and portrait using Bedrock."""
    start_time = time.time()

    # Step 1: Generate name + backstory with Nova Lite
    prompt = (
        f'Create a unique superhero character inspired by the seed word "{seed}". '
        f"Be creative and interesting — the character can be quirky, mysterious, funny, or unconventional. "
        f"Avoid graphic violence or weapons, but the character can have flaws, face real challenges, "
        f"or have an unusual origin. Boring or overly sweet characters are discouraged. "
        f"Respond in this exact JSON format and nothing else:\n"
        f'{{"name": "The Superhero Name", "backstory": "A 2-3 sentence origin story."}}'
    )

    text_response = bedrock_runtime.converse(
        modelId="us.amazon.nova-lite-v1:0",
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 300, "temperature": 0.8},
    )

    text_time = time.time() - start_time

    response_text = text_response["output"]["message"]["content"][0]["text"]
    input_tokens = text_response["usage"]["inputTokens"]
    output_tokens = text_response["usage"]["outputTokens"]

    # Parse the JSON from the response
    try:
        character = json.loads(response_text)
    except json.JSONDecodeError:
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start != -1 and end > start:
            character = json.loads(response_text[start:end])
        else:
            character = {"name": f"The {seed.title()}", "backstory": response_text}

    hero_name = character.get("name", f"The {seed.title()}")
    backstory = character.get("backstory", "A mysterious hero emerges.")

    # Step 2: Generate hero portrait with Titan Image Generator
    safe_name = sanitize_for_image(hero_name)
    image_start = time.time()

    image_prompts = [
        (
            f"A dynamic comic book illustration of {safe_name}. "
            f"Vibrant colors, expressive character design, "
            f"cityscape background, vintage comic book style."
        ),
        (
            "A vibrant comic book illustration of a costumed character. "
            "Bold colors, expressive design, cityscape background, "
            "vintage comic book art style."
        ),
    ]

    image_base64 = None
    image_generated = False
    for img_prompt in image_prompts:
        try:
            image_response = bedrock_runtime.invoke_model(
                modelId="amazon.titan-image-generator-v2:0",
                body=json.dumps(
                    {
                        "taskType": "TEXT_IMAGE",
                        "textToImageParams": {"text": img_prompt[:512]},
                        "imageGenerationConfig": {
                            "numberOfImages": 1,
                            "width": 512,
                            "height": 512,
                            "cfgScale": 7.0,
                        },
                    }
                ),
            )
            image_result = json.loads(image_response["body"].read())
            image_base64 = image_result["images"][0]
            image_generated = True
            break
        except Exception as e:
            if "blocked" in str(e).lower() or "content" in str(e).lower():
                print(f"Image prompt blocked, trying fallback: {str(e)}")
                continue
            raise

    image_time = time.time() - image_start
    total_time = time.time() - start_time

    seed_retained = seed.lower()[:3] in hero_name.lower()

    result = {
        "mode": "bedrock",
        "name": hero_name,
        "backstory": backstory,
        "seed": seed,
        "metrics": {
            "latency_ms": round(total_time * 1000),
            "text_latency_ms": round(text_time * 1000),
            "image_latency_ms": round(image_time * 1000) if image_generated else None,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "name_length": len(hero_name),
            "seed_retained": seed_retained,
            "image_generated": image_generated,
            "model_type": "Nova Lite (foundation model)",
        },
    }
    if image_base64:
        result["imageData"] = image_base64

    return result
