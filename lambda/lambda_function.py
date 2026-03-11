import json
import boto3
import base64

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


def generate_classic(seed):
    """Generate a superhero name using the LSTM model on SageMaker."""
    name = seed.lower()

    for _ in range(33):
        # Convert characters to indices
        seq = [CHAR_TO_INDEX[c] for c in name if c in CHAR_TO_INDEX]

        # Pad sequence to MAX_SEQ_LEN (pre-padding with zeros)
        if len(seq) >= MAX_SEQ_LEN:
            padded = seq[-MAX_SEQ_LEN:]
        else:
            padded = [0] * (MAX_SEQ_LEN - len(seq)) + seq

        # Call SageMaker endpoint (TF Serving format)
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=SAGEMAKER_ENDPOINT,
            ContentType="application/json",
            Body=json.dumps({"instances": [padded]}),
        )

        result = json.loads(response["Body"].read().decode("utf-8"))
        predictions = result["predictions"][0]

        # Argmax to get predicted character index
        pred_index = max(range(len(predictions)), key=lambda i: predictions[i])
        pred_char = INDEX_TO_CHAR.get(pred_index, "")

        if pred_char == "\t":
            break

        name += pred_char

    return {"mode": "classic", "name": name.strip().title(), "seed": seed}


def generate_bedrock(seed):
    """Generate a superhero name, backstory, and portrait using Bedrock."""
    # Step 1: Generate name + backstory with Nova Lite
    prompt = (
        f'Create a unique superhero character inspired by the seed word "{seed}". '
        f"Choose a cheerful, nature-inspired, or whimsical name (avoid dark, violent, or edgy names). "
        f"The backstory should be family-friendly and focus on positive themes like "
        f"courage, kindness, discovery, or protecting nature. Avoid any violence, "
        f"weapons, darkness, or conflict in the backstory. "
        f"Respond in this exact JSON format and nothing else:\n"
        f'{{"name": "The Superhero Name", "backstory": "A 2-3 sentence origin story."}}'
    )

    text_response = bedrock_runtime.converse(
        modelId="us.amazon.nova-lite-v1:0",
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 300, "temperature": 0.8},
    )

    response_text = text_response["output"]["message"]["content"][0]["text"]

    # Parse the JSON from the response
    try:
        character = json.loads(response_text)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start != -1 and end > start:
            character = json.loads(response_text[start:end])
        else:
            character = {"name": f"The {seed.title()}", "backstory": response_text}

    hero_name = character.get("name", f"The {seed.title()}")
    backstory = character.get("backstory", "A mysterious hero emerges.")

    # Step 2: Generate hero portrait with Titan Image Generator
    # Sanitize the hero name to avoid content filter triggers
    safe_name = sanitize_for_image(hero_name)

    # Try multiple prompts with increasing safety
    image_prompts = [
        (
            f"A colorful cartoon illustration of a friendly character named {safe_name}. "
            f"Wearing a bright costume, smiling, arms at sides, "
            f"sunny sky background, children's book art style, "
            f"safe for all ages, positive and cheerful."
        ),
        (
            "A colorful cartoon of a friendly costumed character. "
            "Bright primary colors, big smile, cape, sunny sky, "
            "children's book illustration style."
        ),
    ]

    image_base64 = None
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
            break
        except Exception as e:
            if "blocked" in str(e).lower() or "content" in str(e).lower():
                print(f"Image prompt blocked, trying fallback: {str(e)}")
                continue
            raise

    result = {
        "mode": "bedrock",
        "name": hero_name,
        "backstory": backstory,
        "seed": seed,
    }
    if image_base64:
        result["imageData"] = image_base64

    return result
