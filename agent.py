import os
from dotenv import load_dotenv
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    CodeInterpreterTool,
    CodeInterpreterToolAuto,
)


def main():

    # Clear console
    os.system("cls" if os.name == "nt" else "clear")

    # Load environment variables
    load_dotenv()
    project_endpoint = os.getenv("PROJECT_ENDPOINT")
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")

    # File path (same folder as this script)
    script_dir = Path(__file__).parent
    file_path = script_dir / "interview-transcript.txt"

    if not file_path.exists():
        print(f"File not found: {file_path}")
        return

    print(f"Reading file: {file_path}")

    # Connect to Azure AI Project
    with DefaultAzureCredential(
        exclude_environment_credential=True,
        exclude_managed_identity_credential=True,
    ) as credential, AIProjectClient(
        endpoint=project_endpoint, credential=credential
    ) as project_client, project_client.get_openai_client() as openai_client:

        # Upload file
        uploaded_file = openai_client.files.create(
            file=open(file_path, "rb"),
            purpose="assistants",
        )

        print(f"Uploaded file: {uploaded_file.filename}")

        # Create Code Interpreter tool
        code_interpreter = CodeInterpreterTool(
            container=CodeInterpreterToolAuto(file_ids=[uploaded_file.id])
        )

        # Create agent
        agent = project_client.agents.create_version(
            agent_name="interview-evaluator-agent",
            definition=PromptAgentDefinition(
                model=model_deployment,
                instructions=(
                    "You are an AI HR evaluator. "
                    "Read the uploaded interview transcript carefully. "
                    "Analyze technical skills, communication, problem-solving, "
                    "and culture fit. "
                    "Clearly state whether the candidate is FIT or NOT FIT for the role "
                    "and explain your reasoning."
                ),
                tools=[code_interpreter],
            ),
        )

        print(f"Using agent: {agent.name}")

        # Create conversation
        conversation = openai_client.conversations.create()

        # Send evaluation request
        openai_client.conversations.items.create(
            conversation_id=conversation.id,
            items=[
                {
                    "type": "message",
                    "role": "user",
                    "content": "Please analyze the uploaded file and determine if the candidate is fit for the role.",
                }
            ],
        )

        # Get response
        response = openai_client.responses.create(
            conversation=conversation.id,
            extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
            input="",
        )

        if response.status == "failed":
            print(f"Response failed: {response.error}")
        else:
            print("\n===== EVALUATION RESULT =====\n")
            print(response.output_text)

        # Conversation log
        print("\nConversation Log:\n")
        items = openai_client.conversations.items.list(
            conversation_id=conversation.id
        )

        for item in items:
            if item.type == "message":
                role = item.role.upper()
                content = item.content[0].text
                print(f"{role}: {content}\n")


if __name__ == "__main__":
    main()