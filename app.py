
import streamlit as st
import sqlite3
import requests
import uuid

from typing import TypedDict, Annotated

# LangChain imports
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage

# LangGraph imports
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.message import add_messages
from langgraph.graph.state import START, END, StateGraph

# Tavily import
from langchain_tavily import TavilySearch


# =====================================================
# 1. STREAMLIT CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="AI Travel Assistant",
    page_icon="🚆",
    layout="wide"
)


# =====================================================
# 2. API KEYS
# =====================================================
# Add these values in Streamlit Community Cloud > App settings > Secrets.
GROQ_API_KEY = "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"
#weather_api_key = "b65988ddae944bf993993731262105"
WEATHER_API_KEY = "bdf551fa5200464392c154616261111"
IRCTC_API_KEY = "re_live_27cb751a2d64cba6d8f75f664eb4ef66"
TAVILY_API_KEY = "tvly-4eT6lE-NVyOg8k50jhsmE0Z4yqr0HEIPlQJsMkfZi9D3l5YqX"

# =====================================================
# 2. API KEYS
# =====================================================

GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
WEATHER_API_KEY = st.secrets["WEATHER_API_KEY"]
IRCTC_API_KEY = st.secrets["IRCTC_API_KEY"]
TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]


# =====================================================
# 3. GROQ MODEL
# =====================================================

model = ChatGroq(
    model="openai/gpt-oss-120b",
    groq_api_key=GROQ_API_KEY
)


# =====================================================
# 4. SQLITE CHECKPOINTER
# =====================================================

@st.cache_resource
def get_checkpointer():

    conn = sqlite3.connect(
        "my_db.db",
        check_same_thread=False
    )

    checkpointer = SqliteSaver(conn)

    checkpointer.setup()

    return checkpointer


checkpointer = get_checkpointer()


# =====================================================
# 5. WEATHER TOOL
# =====================================================


import requests
import streamlit as st
from langchain_core.tools import tool

# Store your regenerated key in Streamlit secrets.
WEATHER_API_KEY  = WEATHER_API_KEY


def get_station_location(station_code: str):
    """
    Convert an Indian railway station code into station name and state.
    """

    url = f"https://api.dharun.dev/v1/stations/{station_code.upper()}"

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    result = response.json()
    station = result.get("data")

    if not station:
        raise ValueError(f"Station code {station_code} was not found.")

    return {
        "station_code": station.get("code"),
        "station_name": station.get("name"),
        "state": station.get("state")
    }



# =====================================================
# 5. STATION LOOKUP + WEATHER TOOL
# =====================================================

def get_station_location(station_code: str):
    """
    Convert an Indian railway station code into station name and state.
    """

    station_code = station_code.strip().upper()

    if not station_code:
        raise ValueError("Station code cannot be empty.")

    url = f"https://api.dharun.dev/v1/stations/{station_code}"

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    result = response.json()
    station = result.get("data")

    if not station:
        raise ValueError(
            f"Station code {station_code} was not found."
        )

    return {
        "station_code": station.get("code") or station_code,
        "station_name": station.get("name"),
        "state": station.get("state")
    }


@tool
def weather_tool(to_city: str):
    """
    Get current weather using an Indian railway station code.
    """

    try:
        # STEP 1: Resolve station code
        station = get_station_location(to_city)

        station_name = station.get("station_name")
        state = station.get("state")

        if not station_name:
            return {"error": "Station name was not available."}

        # STEP 2: Build location query
        location_query = (
            f"{station_name}, {state}, India"
            if state else f"{station_name}, India"
        )

        # STEP 3: Call WeatherAPI
        url = "https://api.weatherapi.com/v1/current.json"

        params = {
            "key": WEATHER_API_KEY,
            "q": location_query
        }

        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        # STEP 4: Return weather information
        return {
            "Station_code": station["station_code"],
            "Station_name": station_name,
            "City": data["location"]["name"],
            "Region": data["location"]["region"],
            "Country": data["location"]["country"],
            "Temperature": data["current"]["temp_c"],
            "Condition": data["current"]["condition"]["text"],
            "Condition_icon": data["current"]["condition"]["icon"],
            "Humidity": data["current"]["humidity"]
        }

    except requests.exceptions.RequestException as e:
        return {
            "error": f"API request error: {str(e)}"
        }

    except (KeyError, ValueError, TypeError) as e:
        return {
            "error": f"Location or weather data error: {str(e)}"
        }


# =====================================================
# 6. TRAIN SEARCH TOOL
# =====================================================

@tool
def train_tool(from_city: str, to_city: str):
    """
    Search for trains between two stations.

    Args:
        from_city: Source station code or city.
        to_city: Destination station code or city.
    """

    url = "https://api.irctc.dev/api/v1/trains/search"

    params = {
        "from": from_city,
        "to": to_city
    }

    headers = {
        "x-api-key": IRCTC_API_KEY,
        "accept": "application/json"
    }

    try:

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=20
        )

        response.raise_for_status()

        result = response.json()

        train_data = result.get("data", [])

        trains = []

        for train in train_data:

            trains.append({

                "train_number": train.get("trainNo"),
                "train_name": train.get("trainName"),
                "train_type": train.get("trainType"),

                "from_station": train.get("fromStationName"),
                "from_code": train.get("fromStation"),

                "to_station": train.get("toStationName"),
                "to_code": train.get("toStation"),

                "departure": train.get("departure"),
                "arrival": train.get("arrival"),

                "duration": train.get("durationStr"),
                "duration_minutes": train.get("durationMin"),

                "running_days": train.get("runningDays", []),
                "classes": train.get("classes", []),

                "distance_km": train.get("distance"),
                "estimated_fare": train.get("estimatedFare"),

                "halts": train.get("halts")

            })

        return {
            "source": from_city,
            "destination": to_city,
            "total_trains": len(trains),
            "trains": trains
        }

    except requests.exceptions.RequestException as e:

        return {
            "source": from_city,
            "destination": to_city,
            "error": f"Train API error: {str(e)}",
            "total_trains": 0,
            "trains": []
        }


# =====================================================
# 7. TAVILY SEARCH
# =====================================================

search = TavilySearch(
    tavily_api_key=TAVILY_API_KEY,
    max_results=5,
    topic="general"
)


# =====================================================
# 8. HOTEL SEARCH TOOL
# =====================================================

@tool
def hotel_tool(to_city: str):
    """
    Find hotels in a given city.
    """

    prompt = f"""
    Find hotels in {to_city}, India.

    Provide:

    1. Hotel names
    2. Hotel addresses or locations
    3. Contact phone numbers, if available
    4. Official website, if available
    5. Approximate price range, if available

    Return relevant and useful hotel information.
    Do not invent contact numbers or prices.
    """

    try:

        response = search.invoke({
            "query": prompt
        })

        return {
            "hotel_information": response
        }

    except Exception as e:

        return {
            "error": f"Hotel search error: {str(e)}"
        }


# =====================================================
# 9. CITY INFORMATION TOOL
# =====================================================

@tool
def city_tool(to_city: str):
    """
    Give details about culture, history, people,
    food and tourist places of a given city.
    """

    prompt = f"""
    Give me a detailed guide about {to_city}.

    Cover these topics:

    1. Culture
    2. History
    3. People and languages
    4. Famous food and local cuisine
    5. Tourist places and attractions

    Use clear headings and bullet points.
    """

    try:

        response = search.invoke({
            "query": prompt
        })

        return {
            "city_information": response
        }

    except Exception as e:

        return {
            "error": f"City search error: {str(e)}"
        }


# =====================================================
# 10. LANGGRAPH STATE
# =====================================================

class ChatState(TypedDict):

    messages: Annotated[list[BaseMessage], add_messages]

    from_city: str
    to_city: str

    train_result: dict
    weather_result: dict
    hotel_result: dict
    city_result: dict

    final_result: str


# =====================================================
# 11. TRAIN NODE
# =====================================================

def train_node(state: ChatState):

    from_city = state["from_city"]
    to_city = state["to_city"]

    response = train_tool.invoke({
        "from_city": from_city,
        "to_city": to_city
    })

    return {
        "train_result": response
    }


# =====================================================
# 12. HOTEL NODE
# =====================================================

def hotel_node(state: ChatState):

    to_city = state["to_city"]

    response = hotel_tool.invoke({
        "to_city": to_city
    })

    return {
        "hotel_result": response
    }


# =====================================================
# 13. CITY NODE
# =====================================================

def city_node(state: ChatState):

    to_city = state["to_city"]

    response = city_tool.invoke({
        "to_city": to_city
    })

    return {
        "city_result": response
    }


# =====================================================
# 14. WEATHER NODE
# =====================================================

def weather_node(state: ChatState):

    to_city = state["to_city"]

    response = weather_tool.invoke({
        "to_city": to_city
    })

    return {
        "weather_result": response
    }


# =====================================================
# 15. FINAL NODE
# =====================================================

def final_tool(state: ChatState):

    prompt = f"""
    You are a professional travel guide.

    Generate detailed train information:

    {state['train_result']}

    Generate detailed hotel information:

    {state['hotel_result']}

    City Information:

    {state['city_result']}

    Weather Information:

    {state['weather_result']}

    Prepare a comprehensive travel guide.

    Include:

    1. Train details
    2. Departure and arrival time
    3. Train duration and fare, if available
    4. Hotel details
    5. Current weather
    6. Culture
    7. History
    8. People and languages
    9. Famous food
    10. Tourist destinations

    Use clear headings and bullet points.

    Do not invent train schedules, fares or hotel contact details.
    Mention when information is unavailable.
    """

    response = model.invoke(prompt)

    return {
        "final_result": response.content,
        "messages": [
            AIMessage(content=response.content)
        ]
    }


# =====================================================
# 16. LANGGRAPH WORKFLOW
# =====================================================

graph = StateGraph(ChatState)

graph.add_node("train_node", train_node)
graph.add_node("hotel_node", hotel_node)
graph.add_node("city_node", city_node)
graph.add_node("weather_node", weather_node)
graph.add_node("final_tool", final_tool)

graph.add_edge(START, "train_node")
graph.add_edge("train_node", "hotel_node")
graph.add_edge("hotel_node", "city_node")
graph.add_edge("city_node", "weather_node")
graph.add_edge("weather_node", "final_tool")
graph.add_edge("final_tool", END)

app = graph.compile(
    checkpointer=checkpointer
)


# =====================================================
# 17. PROFESSIONAL STREAMLIT TRAVEL DASHBOARD
# =====================================================

st.markdown("""
<style>
    .block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
    .hero {
        padding: 2rem 2.1rem; border-radius: 18px;
        background: linear-gradient(115deg, #102f43 0%, #176b78 55%, #3c8d83 100%);
        color: white; margin-bottom: 1.4rem;
    }
    .hero h1 {color: white; font-size: 2.25rem; margin-bottom: .35rem;}
    .hero p {color: #e0f2f1; margin-bottom: 0;}
    .section-note {color: #64748b; margin-top: -.55rem;}
    .info-card {
        border: 1px solid rgba(120,130,145,.25); border-radius: 14px;
        padding: 1rem 1.1rem; margin-bottom: .7rem;
        background: var(--secondary-background-color);
    }
    .muted {color: #718096; font-size: .88rem;}
    .big-value {font-size: 1.55rem; font-weight: 700;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <h1>✈️ AI Travel Assistant</h1>
  <p>Your intelligent travel companion — trains, stays, weather and destination discovery.</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("🧭 Travel planner")
    st.caption("Create a travel guide for your next journey.")
    st.info("Enter railway station codes, for example MLDT and HWH.")
    st.markdown("---")
    st.caption("Powered by LangGraph · Groq · Tavily · WeatherAPI")

# Keep the same session-state approach and LangGraph invocation.
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "travel_result" not in st.session_state:
    st.session_state.travel_result = None

st.subheader("Plan your journey")
st.markdown('<p class="section-note">Choose your departure and destination stations to gather travel information.</p>', unsafe_allow_html=True)

with st.container(border=True):
    input_col1, swap_col, input_col2 = st.columns([5, 1, 5])
    with input_col1:
        from_city = st.text_input(
            "From station",
            placeholder="e.g. MLDT",
            help="Enter the source station code or city."
        )
    with swap_col:
        st.markdown("<div style='height: 1.9rem'></div>", unsafe_allow_html=True)
        st.markdown("<div style='text-align:center;font-size:1.5rem'>⇄</div>", unsafe_allow_html=True)
    with input_col2:
        to_city = st.text_input(
            "To station",
            placeholder="e.g. HWH",
            help="Enter the destination station code or city."
        )

    generate_col, reset_col = st.columns([3, 1])
    with generate_col:
        generate_clicked = st.button(
            "🚀 Generate my travel plan",
            type="primary",
            use_container_width=True
        )
    with reset_col:
        reset_clicked = st.button(
            "New journey",
            use_container_width=True
        )

if reset_clicked:
    st.session_state.travel_result = None
    st.session_state.thread_id = str(uuid.uuid4())
    st.rerun()

if generate_clicked:
    if not from_city.strip() or not to_city.strip():
        st.warning("Please enter both departure and destination station codes.")
    elif from_city.strip().upper() == to_city.strip().upper():
        st.warning("Departure and destination stations must be different.")
    else:
        with st.status("Preparing your travel plan...", expanded=True) as status:
            try:
                st.write("Searching trains, hotels, destination information and weather.")
                result = app.invoke(
                    {
                        "messages": [
                            HumanMessage(
                                content=f"I want to go from {from_city.strip().upper()} to {to_city.strip().upper()}"
                            )
                        ],
                        "from_city": from_city.strip().upper(),
                        "to_city": to_city.strip().upper()
                    },
                    config={
                        "configurable": {
                            "thread_id": st.session_state.thread_id
                        }
                    }
                )
                st.session_state.travel_result = result
                status.update(label="Your travel plan is ready!", state="complete", expanded=False)
                st.success("Travel information has been collected.")
            except Exception as e:
                status.update(label="Unable to complete the travel plan", state="error")
                st.error(f"Something went wrong: {e}")

# Helpers for displaying the existing tool outputs without changing graph state.
def _extract_tavily_results(payload):
    """Return Tavily result entries when the response has a results list."""
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            return payload["results"]
        info = payload.get("hotel_information") or payload.get("city_information")
        if isinstance(info, dict) and isinstance(info.get("results"), list):
            return info["results"]
    return []

def _show_search_cards(payload, empty_message):
    entries = _extract_tavily_results(payload)
    if entries:
        for item in entries:
            if not isinstance(item, dict):
                st.write(item)
                continue
            title = item.get("title") or item.get("url") or "Search result"
            content = item.get("content") or item.get("snippet") or ""
            url = item.get("url")
            with st.container(border=True):
                st.markdown(f"**{title}**")
                if content:
                    st.write(content)
                if url:
                    st.markdown(f"[Open source]({url})")
    elif isinstance(payload, dict) and payload.get("error"):
        st.warning(payload["error"])
    else:
        st.info(empty_message)
        st.json(payload)

def _geocode_city(city_name):
    """Best-effort city lookup for the map; returns None if unavailable."""
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{city_name}, India", "format": "json", "limit": 1},
            headers={"User-Agent": "AI-Travel-Assistant/1.0"},
            timeout=10
        )
        response.raise_for_status()
        places = response.json()
        if places:
            return {
                "lat": float(places[0]["lat"]),
                "lon": float(places[0]["lon"])
            }
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None
    return None

# =====================================================
# 18. DASHBOARD RESULTS
# =====================================================

if st.session_state.travel_result is not None:
    result = st.session_state.travel_result
    train_result = result.get("train_result", {}) or {}
    hotel_result = result.get("hotel_result", {}) or {}
    weather_result = result.get("weather_result", {}) or {}
    city_result = result.get("city_result", {}) or {}
    trains = train_result.get("trains", []) if isinstance(train_result, dict) else []

    st.markdown("---")
    st.header("Your journey dashboard")
    st.caption(
        f"{train_result.get('source', from_city or 'Source')}  →  "
        f"{train_result.get('destination', to_city or 'Destination')}"
    )

    # Weather overview cards
    st.subheader("🌤️ Destination weather")
    if isinstance(weather_result, dict) and not weather_result.get("error"):
        w1, w2, w3, w4 = st.columns(4)
        w1.metric("Temperature", f"{weather_result.get('Temperature', 'N/A')} °C")
        w2.metric("Condition", weather_result.get("Condition", "N/A"))
        w3.metric("Humidity", f"{weather_result.get('Humidity', 'N/A')}%")
        w4.metric("City", weather_result.get("City", "N/A"))
        if weather_result.get("Condition_icon"):
            icon_url = weather_result["Condition_icon"]
            if icon_url.startswith("//"):
                icon_url = "https:" + icon_url
            st.image(icon_url, width=64)
    else:
        st.warning(
            weather_result.get("error", "Weather information is unavailable.")
            if isinstance(weather_result, dict) else "Weather information is unavailable."
        )

    st.markdown("---")
    trains_tab, hotels_tab, map_tab, guide_tab, raw_tab = st.tabs(
        ["🚆 Trains", "🏨 Hotels", "📍 Destination map", "✨ AI travel guide", "🔎 Raw data"]
    )

    with trains_tab:
        st.subheader("Available train options")
        if isinstance(train_result, dict) and train_result.get("error"):
            st.error(train_result["error"])
        elif trains:
            st.caption(f"{len(trains)} train option(s) returned by the train API.")
            for train in trains:
                train_name = train.get("train_name") or "Train name unavailable"
                train_number = train.get("train_number") or "Number unavailable"
                with st.container(border=True):
                    title_col, type_col = st.columns([4, 1])
                    with title_col:
                        st.markdown(f"### 🚆 {train_name}")
                        st.caption(f"Train no. {train_number}")
                    with type_col:
                        st.caption(train.get("train_type") or "Train")
                    dep_col, arrow_col, arr_col = st.columns([4, 1, 4])
                    with dep_col:
                        st.markdown(f"**{train.get('departure') or 'N/A'}**")
                        st.caption(f"{train.get('from_station') or 'Source'} ({train.get('from_code') or ''})")
                    with arrow_col:
                        st.markdown("<div style='text-align:center;padding-top:.3rem'>→</div>", unsafe_allow_html=True)
                    with arr_col:
                        st.markdown(f"**{train.get('arrival') or 'N/A'}**")
                        st.caption(f"{train.get('to_station') or 'Destination'} ({train.get('to_code') or ''})")
                    d1, d2, d3, d4 = st.columns(4)
                    d1.caption("Duration")
                    d1.write(train.get("duration") or "N/A")
                    d2.caption("Distance")
                    d2.write(f"{train.get('distance_km')} km" if train.get("distance_km") is not None else "N/A")
                    d3.caption("Estimated fare")
                    d3.write(str(train.get("estimated_fare") or "Not provided"))
                    d4.caption("Classes")
                    classes = train.get("classes") or []
                    d4.write(", ".join(map(str, classes)) if classes else "N/A")
                    running_days = train.get("running_days") or []
                    if running_days:
                        st.caption("Running days: " + ", ".join(map(str, running_days)))
        else:
            st.info("The train API did not return train options for this route.")
            if isinstance(train_result, dict):
                st.json(train_result)

    with hotels_tab:
        st.subheader("Stay options")
        _show_search_cards(
            hotel_result,
            "The hotel search did not return individually structured results. Raw search information is shown below when available."
        )

    with map_tab:
        st.subheader("Explore the destination")
        destination_name = (
            weather_result.get("City")
            if isinstance(weather_result, dict) else None
        ) or to_city
        st.caption(f"Map location lookup for {destination_name}, India.")
        if destination_name:
            with st.spinner("Finding destination coordinates..."):
                coordinates = _geocode_city(destination_name)
            if coordinates:
                st.map(
                    [{"latitude": coordinates["lat"], "longitude": coordinates["lon"]}],
                    zoom=10,
                    use_container_width=True
                )
                st.caption("Map marker shows the destination city, not individual tourist attractions.")
            else:
                st.info("A map location could not be found. You can still explore the destination details in the AI guide.")
        st.markdown("**Destination research**")
        _show_search_cards(city_result, "No separate destination search results were returned.")

    with guide_tab:
        st.subheader("Your AI-generated travel guide")
        st.markdown(result.get("final_result", "No travel guide was generated."))

    with raw_tab:
        st.caption("Original tool outputs from your existing LangGraph workflow.")
        with st.expander("Train API response"):
            st.json(train_result)
        with st.expander("Hotel search response"):
            st.json(hotel_result)
        with st.expander("Weather API response"):
            st.json(weather_result)
        with st.expander("City search response"):
            st.json(city_result)

    st.markdown("---")
    if st.button("🔄 Plan another journey", use_container_width=True):
        st.session_state.travel_result = None
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()

st.markdown("---")
st.caption("AI Travel Assistant · LangGraph + Groq + Tavily + WeatherAPI + IRCTC API")
