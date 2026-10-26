import re
from collections import Counter
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="GroupDNA | WhatsApp Chat Analyzer", page_icon="🧬", layout="wide")

st.title("🧬 GroupDNA")
st.subheader("WhatsApp Chat Analyzer")
st.write("Upload a WhatsApp `.txt` chat export to explore message counts, activity, and common words.")
st.caption("Privacy: this demo analyzes the uploaded file in the running app. Avoid uploading chats you do not have permission to analyze.")

STOP_WORDS = set("""
a an the is am are was were be been being this that these those it its i me my mine
you your yours he she his her we our they them and or but if so because as at by for from
in into on of to with about as at not no yes hai ka ki ke ko me mein ho na kya kaise
""".split())

# WhatsApp exports commonly use either 24-hour or 12-hour timestamps.
MESSAGE_START = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?:\s?[APap][Mm])?)\s+-\s+(.*)$"
)

def parse_timestamp(date_text, time_text):
    date_text = date_text.strip()
    time_text = time_text.strip().upper().replace(" AM", "AM").replace(" PM", "PM")
    formats = [
        "%d/%m/%y %H:%M", "%d/%m/%Y %H:%M",
        "%m/%d/%y %H:%M", "%m/%d/%Y %H:%M",
        "%d/%m/%y %I:%M%p", "%d/%m/%Y %I:%M%p",
        "%m/%d/%y %I:%M%p", "%m/%d/%Y %I:%M%p",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(f"{date_text} {time_text}", fmt)
        except ValueError:
            pass
    return None

def parse_chat(raw_text):
    parsed = []
    current = None
    for line in raw_text.splitlines():
        match = MESSAGE_START.match(line)
        if match:
            if current is not None:
                parsed.append(current)
            date_text, time_text, remainder = match.groups()
            dt = parse_timestamp(date_text, time_text)
            if ": " in remainder:
                sender, message = remainder.split(": ", 1)
                current = {
                    "timestamp": dt,
                    "sender": sender.strip(),
                    "text": message.strip(),
                }
            else:
                # System messages such as "X added Y" are not counted as chat messages.
                current = None
        elif current is not None and line.strip():
            # Join WhatsApp messages that wrap onto multiple lines.
            current["text"] += "\n" + line.strip()
    if current is not None:
        parsed.append(current)
    return [m for m in parsed if m["timestamp"] is not None and m["sender"] and m["text"]]

def words_from_messages(messages):
    counts = Counter()
    for msg in messages:
        for word in re.findall(r"[A-Za-z0-9']+", msg["text"].lower()):
            if len(word) > 1 and word not in STOP_WORDS:
                counts[word] += 1
    return counts

uploaded_file = st.file_uploader("Choose your WhatsApp chat export (.txt)", type=["txt"])

if uploaded_file is None:
    st.info("To begin: open WhatsApp → open the chat → Export chat → Without media → upload the `.txt` file here.")
    st.markdown("### What you'll see")
    st.markdown("- Total messages and participants\n- Messages per participant\n- Message activity by hour\n- Top words after basic stop-word filtering")
    st.stop()

try:
    raw_text = uploaded_file.getvalue().decode("utf-8-sig")
except UnicodeDecodeError:
    raw_text = uploaded_file.getvalue().decode("utf-8", errors="replace")

messages = parse_chat(raw_text)
if not messages:
    st.error("I couldn't find any messages in this file. Please upload a WhatsApp-exported `.txt` file and check the date/time format.")
    st.stop()

df = pd.DataFrame(messages)
df["hour"] = df["timestamp"].dt.hour
df["date"] = df["timestamp"].dt.date
counts = df["sender"].value_counts().rename_axis("Participant").reset_index(name="Messages")
participants = int(df["sender"].nunique())
total_messages = len(df)

c1, c2, c3 = st.columns(3)
c1.metric("Total messages", f"{total_messages:,}")
c2.metric("Participants", f"{participants:,}")
c3.metric("Days covered", f"{df['date'].nunique():,}")

st.divider()
left, right = st.columns(2)
with left:
    st.subheader("🏆 Message leaderboard")
    fig = px.bar(counts.sort_values("Messages"), x="Messages", y="Participant", orientation="h",
                 title="Messages sent by participant", text="Messages")
    fig.update_layout(yaxis_title="", xaxis_title="Number of messages")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(counts, use_container_width=True, hide_index=True)

with right:
    st.subheader("🕒 Chat activity by hour")
    hourly = df.groupby("hour").size().reindex(range(24), fill_value=0).rename_axis("Hour").reset_index(name="Messages")
    fig = px.bar(hourly, x="Hour", y="Messages", title="When the group chats")
    fig.update_xaxes(dtick=1)
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("💬 Top words")
word_counts = words_from_messages(messages)
if word_counts:
    top_words = pd.DataFrame(word_counts.most_common(10), columns=["Word", "Count"])
    fig = px.bar(top_words.sort_values("Count"), x="Count", y="Word", orientation="h",
                 title="10 most frequent words")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(top_words, use_container_width=True, hide_index=True)
else:
    st.write("No words to display after basic filtering.")

st.subheader("📅 Daily message volume")
daily = df.groupby("date").size().rename_axis("Date").reset_index(name="Messages")
fig = px.line(daily, x="Date", y="Messages", markers=True, title="Messages per day")
st.plotly_chart(fig, use_container_width=True)

st.download_button(
    "Download participant counts as CSV",
    data=counts.to_csv(index=False).encode("utf-8"),
    file_name="groupdna_participant_counts.csv",
    mime="text/csv",
)

with st.expander("How this compares with your notebook"):
    st.write(
        "This web version keeps the same core idea as your notebook: it parses WhatsApp messages, "
        "counts messages per sender, filters common words, and analyzes message activity by hour. "
        "It replaces the notebook's fixed `/content/hostel_bois.txt` path with an upload control. "
        "Your notebook's response-time, silent-streak, and personality sections are not included yet; "
        "we can add those after this first website runs."
    )
