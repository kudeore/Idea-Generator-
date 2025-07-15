# === Agentic Market Gap Explorer (Corrected with Proper Agent Loop) ===

import os
import re
import operator
import dotenv
from typing import TypedDict, Annotated, List, Sequence
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, AIMessage, BaseMessage, ToolMessage
from langchain_groq import ChatGroq
from langchain_community.tools import GoogleSearchRun
from langchain_community.utilities import GoogleSearchAPIWrapper
from langchain.tools import tool
from langgraph.graph import StateGraph, END
from langchain.prompts import PromptTemplate

# --- Load .env Keys ---
dotenv.load_dotenv()

groq_key = os.getenv("GROK_API")
gsearch_key = os.getenv("GOOGLE_SEARCH_API_KEY")
gsearch_cx = os.getenv("GOOGLE_SEARCH_CSE_ID")

# --- Tools ---
search_api = GoogleSearchAPIWrapper(google_api_key=gsearch_key, google_cse_id=gsearch_cx)
search_tool = GoogleSearchRun(api_wrapper=search_api)


# --- Prompt Templates ---
subniche_prompt = PromptTemplate(
    input_variables=["topic"],
    template="""
You are a seasoned market analyst. Your goal is to explore the market topic: "{topic}"
Break it down into at least 5 interesting and distinct sub-niches that might hold unique commercial potential.
For each niche, provide a title in markdown bold (e.g., **1. Niche Name**).
IMPORTANT: Do not add any conversational text, introductions, or summaries. Your entire response must be only the numbered list of sub-niches.
"""
)

# COMBINED prompt for the new researcher agent
# CORRECTED: Rephrased the instruction to avoid the KeyError: 'niche'
researcher_prompt_template = PromptTemplate(
    input_variables=["sub_niches", "validated_niche"],
    template="""
You are a multi-skilled researcher. Your current task is determined by the inputs provided.

**TASK 1: Demand Validation**
If you receive a list of 'sub_niches', your goal is to validate them.
For each of the following sub-niches:
{sub_niches}

Do the following:
1. Use the 'google_search' tool to find information on whether each niche is growing, stable, or declining. For each sub-niche, search for terms like `"sub-niche name market trend"`.
2. Use the 'google_search' tool to identify community discussions (e.g., on Reddit) and product saturation for each sub-niche.
3. Based on your research, determine which single sub-niche has the highest unmet demand.
Your final answer for this task MUST be only the name of the best sub-niche.

**TASK 2: Pain Point Gathering**
If you have already validated a niche ('{validated_niche}'), your new goal is to find user pain points for it.
Use the 'google_search' tool with queries like:
- site:reddit.com "{validated_niche}" problem
- site:reddit.com "{validated_niche}" frustration

Based on the search results, summarize the key user complaints and challenges in a concise paragraph. This summary will be your final answer for this task.
"""
)


copywriting_prompt = PromptTemplate(
    input_variables=["reddit_data", "validated_niche"],
    template="""
Based on the following pain point summary from the niche "{validated_niche}":

{reddit_data}

Do the following:
1. List top 3-5 user pain points.
2. Generate a unique business idea to solve these issues. Give it a name.
3. Write landing page copy:
   - Headline
   - Subheadline
   - Features (3 bullets)
   - FAQ (2-3 questions)
"""
)

# --- State ---
class AgentState(TypedDict):
    topic: str
    sub_niches: List[str]
    validated_niche: str
    reddit_data: str
    final_report: str
    messages: Annotated[Sequence[BaseMessage], operator.add]

# --- LLM & Tools ---
llm = ChatGroq(model_name="llama3-70b-8192", groq_api_key=groq_key)
# UPDATED: Removed google_trends tool
tools = [search_tool]

# --- Graph Node Functions ---
def market_analyst_node(state: AgentState):
    print("--- Executing Market Analyst ---")
    prompt = subniche_prompt.format(topic=state['topic'])
    response = llm.invoke([SystemMessage(content="You are a market analyst."), HumanMessage(content=prompt)])
    content = response.content
    niches = re.findall(r'\*\*\d\.\s*(.*?)\*\*', content)
    if not niches:
        niches = re.findall(r'^\s*\d\.\s+(.*)', content, re.MULTILINE)
    cleaned_niches = [n.strip().replace('**', '').replace(':', '') for n in niches]
    print(f"    [Analyst found niches: {cleaned_niches}]")
    # Start the conversation history for the next agent
    return {"sub_niches": [n for n in cleaned_niches if n], "messages": []}

def prepare_researcher_node(state: AgentState):
    """Prepares the prompt for the researcher based on the current state."""
    print("--- Preparing for Researcher ---")
    if not state.get('validated_niche'):
        print("    [Task: Preparing for Demand Validation]")
        prompt = researcher_prompt_template.format(sub_niches="\n".join(state['sub_niches']), validated_niche="")
        messages = [HumanMessage(content=prompt)]
    else:
        print("    [Task: Preparing for Pain Point Gathering]")
        prompt = researcher_prompt_template.format(sub_niches="", validated_niche=state.get('validated_niche'))
        messages = [HumanMessage(content=prompt)]
    # This clears previous messages and sets the new task
    return {"messages": messages}

def researcher_node(state: AgentState):
    """This node invokes the LLM with the current message state."""
    print("--- Executing Researcher ---")
    # The agent loop will now use the message history correctly
    response = llm.bind_tools(tools).invoke(state['messages'])
    return {"messages": [response]}


def idea_generator_node(state: AgentState):
    print("--- Executing Idea Generator ---")
    # The final data is the content of the last message
    reddit_data = state['messages'][-1].content
    validated_niche = state.get("validated_niche")
    prompt = copywriting_prompt.format(validated_niche=validated_niche, reddit_data=reddit_data)
    response = llm.invoke([SystemMessage(content="You are a founder and copywriter."), HumanMessage(content=prompt)])
    return {"final_report": response.content}

# --- Tool Execution Node (Re-implemented to remove dependency) ---
def call_tool_node(state: AgentState):
    """This runs the tools requested by the agent. No ToolExecutor needed."""
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
    return {"validated_niche": validated_niche, "messages": []} # Clear messages

# --- Conditional Router ---
def router(state: AgentState):
    """Router logic to decide the next step."""
    print("--- Routing ---")
    last_message = state['messages'][-1]
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "call_tool"
    
    if not state.get('validated_niche'):
        return "save_niche"
    
    else:
        return "continue_to_generator"

# --- Graph Definition ---
workflow = StateGraph(AgentState)

# Define the nodes
workflow.add_node("market_analyst", market_analyst_node)
workflow.add_node("prepare_researcher", prepare_researcher_node)
workflow.add_node("researcher", researcher_node)
workflow.add_node("idea_generator", idea_generator_node)
workflow.add_node("call_tool", call_tool_node)
workflow.add_node("save_niche", save_validated_niche_node)

# Define the edges
workflow.set_entry_point("market_analyst")
workflow.add_edge("market_analyst", "prepare_researcher")
workflow.add_edge("prepare_researcher", "researcher")
workflow.add_edge("idea_generator", END)

# The main research loop
workflow.add_conditional_edges(
    "researcher",
    router,
    {
        "call_tool": "call_tool",
        "save_niche": "save_niche",
        "continue_to_generator": "idea_generator",
    },
)
workflow.add_edge("call_tool", "researcher")
workflow.add_edge("save_niche", "prepare_researcher") # Loop back to prepare for the next task


app = workflow.compile()

if __name__ == "__main__":
    if not all([groq_key, gsearch_key, gsearch_cx]):
        print("🔴 Missing API keys in .env")
    else:
        topic = "Wealth"
        final_state = None
        for step in app.stream({"topic": topic, "messages": []}):
            step_name = list(step.keys())[0]
            print(f"✅ Finished Step: {step_name}")
            final_state = step

        print("\n--- Final Output ---\n")
        print(final_state["idea_generator"]["final_report"])
