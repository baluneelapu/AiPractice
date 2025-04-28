import os
import streamlit as st
import logging
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.identity import ClientSecretCredential
from azure.ai.projects.models import MessageRole

# Load environment variables
load_dotenv()

# Disable verbose connection logs
logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
logger.setLevel(logging.WARNING)

# Initialize Azure client
AIPROJECT_CONNECTION_STRING = os.getenv("AIPROJECT_CONNECTION_STRING")
AGENT_ID = os.getenv("AGENT_ID")
# Load service principal credentials from environment variables
TENANT_ID = os.getenv("AZURE_TENANT_ID")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")

credential = ClientSecretCredential(tenant_id=TENANT_ID, client_id=CLIENT_ID, client_secret=CLIENT_SECRET)

project_client = AIProjectClient.from_connection_string(
    conn_str=AIPROJECT_CONNECTION_STRING,
    credential=credential
)

# Streamlit app configuration
st.set_page_config(page_title="Azure Chat Agent")
st.title("Azure Chat Agent")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    thread = project_client.agents.create_thread()
    st.session_state.thread_id = thread.id
    st.toast(f"New chat session started: {thread.id}")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input and processing
if prompt := st.chat_input("Type your message"):
    # Add user message to UI
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        # Add user message to Azure thread
        project_client.agents.create_message(
            thread_id=st.session_state.thread_id,
            role="user",
            content=prompt
        )

        # Process message with spinner
        with st.spinner("Processing..."):
            run = project_client.agents.create_and_process_run(
                thread_id=st.session_state.thread_id,
                agent_id=AGENT_ID
            )

            if run.status == "failed":
                raise Exception(run.last_error)

            # Get agent response
            messages = project_client.agents.list_messages(st.session_state.thread_id)
            last_msg = messages.get_last_text_message_by_role(MessageRole.AGENT)
            
            if not last_msg:
                raise Exception("No response from the agent")

            response = last_msg.text.value

        # Add assistant response to UI
        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        st.session_state.messages.append({"role": "assistant", "content": error_msg})
        with st.chat_message("assistant"):
            st.markdown(error_msg)
