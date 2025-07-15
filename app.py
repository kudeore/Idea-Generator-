# === Backend Flask App with Real-Time Streaming (app.py) ===

import os
import re
import operator
import dotenv
import json
import time
from typing import TypedDict, Annotated, List, Sequence
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, AIMessage, BaseMessage, ToolMessage
from langchain_groq import ChatGroq
from langchain_community.tools import GoogleSearchRun
from langchain_community.utilities import GoogleSearchAPIWrapper
from langchain.tools import tool
from langgraph.graph import StateGraph, END
from langchain.prompts import PromptTemplate
from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS

# --- Load .env Keys ---
dotenv.load_dotenv()

groq_key = os.getenv("GROK_API")
gsearch_key = os.getenv("GOOGLE_SEARCH_API_KEY")
gsearch_cx = os.getenv("GOOGLE_SEARCH_CSE_ID")

# --- Tools ---
search_api = GoogleSearchAPIWrapper(google_api_key=gsearch_key, google_cse_id=gsearch_cx)
search_tool = GoogleSearchRun(api_wrapper=search_api)


# --- Prompt Templates ---
# UPDATED: Prompt now asks for a specific JSON structure.
subniche_prompt = PromptTemplate(
    input_variables=["topic"],
    template="""
You are a seasoned market analyst. Your goal is to explore the market topic: "{topic}"
Break it down into at least 5 interesting and distinct sub-niches that might hold unique commercial potential.
For each niche, provide a title and a one-sentence description.
Return this as a JSON object with a single key "subniches" which is an array of objects, each with "title" and "description" keys.
Example: {{"subniches": [{{"title": "Niche 1", "description": "A short description."}}]}}
"""
)

researcher_prompt_template = PromptTemplate(
    input_variables=["sub_niches", "validated_niche"],
    template="""
You are a multi-skilled researcher. Your current task is determined by the inputs provided.

**TASK 1: Demand Validation**
If you receive a list of 'sub_niches', your goal is to validate them. For each of the following sub-niches:
{sub_niches}
Do the following:
1. Use the 'google_search' tool to find information on whether each niche is growing, stable, or declining. Search for terms like `"sub-niche name market trend"`.
2. Use the 'google_search' tool to identify community discussions and product saturation for each sub-niche.
3. Based on your research, determine which single sub-niche has the highest unmet demand.
Your final answer for this task MUST be only the name of the best sub-niche.

**TASK 2: Pain Point Gathering**
If you have already validated a niche ('{validated_niche}'), your new goal is to find user pain points for it. Use the 'google_search' tool with queries like:
- site:reddit.com "{validated_niche}" problem
- site:reddit.com "{validated_niche}" frustration
Based on the search results, summarize the key user complaints and challenges in a concise paragraph. This summary will be your final answer for this task.
"""
)


copywriting_prompt = PromptTemplate(
    input_variables=["reddit_data", "validated_niche"],
    template="""
You are a founder and copywriter. Based on the following pain point summary from the niche "{validated_niche}":

{reddit_data}

Do the following:
1. List top 3-5 user pain points.
2. Generate a unique business idea to solve these issues. Give it a name.
3. Write landing page copy:
   - Headline
   - Subheadline
   - Features (3 bullets)
   - FAQ (2-3 questions)
Return a single, well-formatted markdown document with the complete report.
"""
)

# --- State ---
# UPDATED: sub_niches is now a list of dictionaries.
class AgentState(TypedDict):
    topic: str
    sub_niches: List[dict]
    validated_niche: str
    reason: str
    reddit_data: str
    final_report: str
    messages: Annotated[Sequence[BaseMessage], operator.add]

# --- LLM & Tools ---
llm = ChatGroq(model_name="llama3-70b-8192", groq_api_key=groq_key)
# Re-introduced a dedicated LLM for enforcing JSON output.
json_llm = ChatGroq(
    model_name="llama3-70b-8192",
    groq_api_key=groq_key,
    temperature=0.1,
    model_kwargs={"response_format": {"type": "json_object"}},
)
tools = [search_tool]

# --- Graph Node Functions ---
# UPDATED: This node now uses the JSON LLM for reliable, structured output.
def market_analyst_node(state: AgentState):
    print("--- Executing Market Analyst ---")
    prompt = subniche_prompt.format(topic=state['topic'])
    response = json_llm.invoke([SystemMessage(content="You are a market analyst that only responds in JSON."), HumanMessage(content=prompt)])
    data = json.loads(response.content)
    print(f"    [Analyst found niches: {data['subniches']}]")
    return {"sub_niches": data['subniches']}

def prepare_researcher_node(state: AgentState):
    """Prepares the prompt for the researcher based on the current state."""
    print("--- Preparing for Researcher ---")
    if not state.get('validated_niche'):
        print("    [Task: Preparing for Demand Validation]")
        # Pass the sub-niches as a JSON string for the prompt
        sub_niches_str = json.dumps(state['sub_niches'], indent=2)
        prompt = researcher_prompt_template.format(sub_niches=sub_niches_str, validated_niche="")
    else:
        print("    [Task: Preparing for Pain Point Gathering]")
        prompt = researcher_prompt_template.format(sub_niches="", validated_niche=state.get('validated_niche'))
    
    return {"messages": [HumanMessage(content=prompt)]}

def researcher_node(state: AgentState):
    """This node invokes the LLM with the current message state."""
    print("--- Executing Researcher ---")
    response = llm.bind_tools(tools).invoke(state['messages'])
    return {"messages": [response]}


def idea_generator_node(state: AgentState):
    print("--- Executing Idea Generator ---")
    reddit_data = state.get("reddit_data", "No pain points found.")
    validated_niche = state.get("validated_niche")
    prompt = copywriting_prompt.format(validated_niche=validated_niche, reddit_data=reddit_data)
    response = llm.invoke([SystemMessage(content="You are a founder and copywriter."), HumanMessage(content=prompt)])
    return {"final_report": response.content}

def call_tool_node(state: AgentState):
    """This runs the tools requested by the agent."""
    print("--- Calling Tools ---")
    last_message = state['messages'][-1]
    tool_calls = last_message.tool_calls
    tool_messages = []
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_to_call = None
        for t in tools:
            if t.name == tool_name:
                tool_to_call = t
                break
        if tool_to_call:
            try:
                output = tool_to_call.invoke(tool_call["args"])
                output_str = str(output)
            except Exception as e:
                output_str = f"Error running tool {tool_name}: {e}"
            tool_messages.append(ToolMessage(content=output_str, tool_call_id=tool_call["id"]))
    return {"messages": tool_messages}

def save_validated_niche_node(state: AgentState):
    """Saves the validated niche to the state and clears messages for the next task."""
    print("--- Saving Validated Niche ---")
    last_message = state['messages'][-1]
    validated_niche = last_message.content.strip()
    print(f"    [Saving niche: {validated_niche}]")
    return {"validated_niche": validated_niche, "reason": "Determined by AI researcher.", "messages": []}

def save_pain_points_node(state: AgentState):
    """Saves the pain points to the state."""
    print("--- Saving Pain Points ---")
    last_message = state['messages'][-1]
    reddit_data = last_message.content.strip()
    print(f"    [Saving pain points: {reddit_data[:100]}...]")
    return {"reddit_data": reddit_data}

def router(state: AgentState):
    """Router logic to decide the next step."""
    print("--- Routing ---")
    last_message = state['messages'][-1]
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "call_tool"
    if not state.get('validated_niche'):
        return "save_niche"
    else:
        return "save_pain_points"

# --- Graph Definition ---
workflow = StateGraph(AgentState)
workflow.add_node("market_analyst", market_analyst_node)
workflow.add_node("prepare_researcher", prepare_researcher_node)
workflow.add_node("researcher", researcher_node)
workflow.add_node("idea_generator", idea_generator_node)
workflow.add_node("call_tool", call_tool_node)
workflow.add_node("save_niche", save_validated_niche_node)
workflow.add_node("save_pain_points", save_pain_points_node)

workflow.set_entry_point("market_analyst")
workflow.add_edge("market_analyst", "prepare_researcher")
workflow.add_edge("prepare_researcher", "researcher")
workflow.add_edge("save_niche", "prepare_researcher")
workflow.add_edge("save_pain_points", "idea_generator")
workflow.add_edge("idea_generator", END)
workflow.add_conditional_edges(
    "researcher",
    router,
    {
        "call_tool": "call_tool",
        "save_niche": "save_niche",
        "save_pain_points": "save_pain_points",
    },
)
workflow.add_edge("call_tool", "researcher")
langgraph_app = workflow.compile()

# --- Flask API Server ---
app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['GET', 'POST'])
def generate_idea():
    if request.method == 'GET':
        topic = request.args.get('topic')
    else:
        data = request.get_json()
        topic = data.get('topic')

    if not topic:
        return jsonify({"error": "No topic provided"}), 400
    
    def stream_events():
        inputs = {"topic": topic, "messages": []}
        try:
            for step in langgraph_app.stream(inputs):
                step_name = list(step.keys())[0]
                data = step[step_name]
                
                if step_name in ["researcher", "call_tool", "prepare_researcher"]:
                    event_data = {"step": step_name, "data": {}}
                else:
                    event_data = {"step": step_name, "data": data}
                
                yield f"data: {json.dumps(event_data)}\n\n"
                time.sleep(1)
            
            yield f"data: {json.dumps({'step': 'done'})}\n\n"

        except Exception as e:
            print(f"Error during generation stream: {e}")
            error_event = {"step": "error", "data": {"error": str(e)}}
            yield f"data: {json.dumps(error_event)}\n\n"

    return Response(stream_events(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
