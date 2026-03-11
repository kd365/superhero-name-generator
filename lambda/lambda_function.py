import json
import boto3
import base64

sagemaker_runtime = boto3.client("sagemaker-runtime", region_name="us-east-1")
bedrock_runtime = boto3.client("bedrock-runtime", region_name="us-east-1")

SAGEMAKER_ENDPOINT = "superhero-lstm-endpoint"

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


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
    response = sagemaker_runtime.invoke_endpoint(
        EndpointName=SAGEMAKER_ENDPOINT,
        ContentType="application/json",
        Body=json.dumps({"seed": seed}),
    )

    result = json.loads(response["Body"].read().decode("utf-8"))
    return {"mode": "classic", "name": result["name"], "seed": seed}


def generate_bedrock(seed):
    """Generate a superhero name, backstory, and portrait using Bedrock."""
    # Step 1: Generate name + backstory with Nova Lite
    prompt = (
        f'Create a unique superhero character inspired by the seed word "{seed}". '
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
    image_prompt = (
        f"A heroic portrait of a superhero called {hero_name}. "
        f"Comic book style, bold colors, dynamic pose, "
        f"dramatic lighting, full upper body shot. "
        f"{backstory}"
    )

    image_response = bedrock_runtime.invoke_model(
        modelId="amazon.titan-image-generator-v2:0",
        body=json.dumps(
            {
                "textToImageParams": {"text": image_prompt},
                "imageGenerationConfig": {
                    "numberOfImages": 1,
                    "width": 512,
                    "height": 512,
                    "quality": "standard",
                },
            }
        ),
    )

    image_result = json.loads(image_response["body"].read())
    image_base64 = image_result["images"][0]

    return {
        "mode": "bedrock",
        "name": hero_name,
        "backstory": backstory,
        "imageData": image_base64,
        "seed": seed,
    }
