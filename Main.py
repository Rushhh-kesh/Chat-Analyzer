import streamlit as st
import pandas as pd
import re
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import emoji
import chardet

def detect_encoding(file_content):
    result = chardet.detect(file_content)
    return result['encoding'] if result['encoding'] else 'utf-8'

def read_file_content(file_object):
    content = file_object.read()
    try:
        # Try UTF-8 first
        return content.decode('utf-8')
    except UnicodeDecodeError:
        # If UTF-8 fails, try other encodings
        try:
            encoding = detect_encoding(content)
            return content.decode(encoding)
        except UnicodeDecodeError:
            # If all else fails, use replace for invalid characters
            return content.decode('utf-8', errors='replace')

def process_chat_file(content):
    messages = content.split('\n')
    pattern = r'(\d{1,2}/\d{1,2}/\d{2,4})(?:,\s*|\s+)(\d{1,2}:\d{2}(?:\u202f)?(?:\s)?(?:am|pm|AM|PM)) - ([^:]+): (.+)'

    dates, times, senders, messages_text = [], [], [], []
    current_message = ""

    date_formats = [
        '%m/%d/%y %I:%M %p',  # 12/30/24 8:31 PM
        '%d/%m/%y %I:%M %p',  # 30/12/24 8:31 PM
        '%m/%d/%Y %I:%M %p',  # 12/30/2024 8:31 PM
        '%d/%m/%Y %I:%M %p',  # 30/12/2024 8:31 PM
        '%d/%m/%Y %H:%M'      # 30/12/2024 20:31
    ]

    for message in messages:
        message = message.strip()
        if not message or "Messages and calls are end-to-end encrypted" in message:
            continue

        match = re.match(pattern, message, re.IGNORECASE)
        if match:
            if current_message and messages_text:
                messages_text[-1] += f" {current_message.strip()}"
                current_message = ""

            date_str, time_str, sender, text = match.groups()
            
            # Standardize time format
            time_str = time_str.strip().upper()
            if 'AM' not in time_str and 'PM' not in time_str:
                time_str += ' PM' if int(time_str.split(':')[0]) >= 8 else ' AM'
            
            date_time_str = f"{date_str} {time_str}"

            parsed = False
            for fmt in date_formats:
                try:
                    dt = datetime.strptime(date_time_str, fmt)
                    dates.append(dt.date())
                    times.append(dt.time())
                    senders.append(sender.strip())
                    messages_text.append(text.strip())
                    parsed = True
                    break
                except ValueError:
                    continue

            if not parsed:
                st.warning(f"Skipping message with invalid format: {date_time_str}")

        else:
            if messages_text and not message.startswith("Messages and calls are end-to-end encrypted"):
                current_message += f" {message}"

    if not dates:
        st.error("No messages could be parsed. Please check your chat format.")
        return pd.DataFrame()

    return pd.DataFrame({
        'date': dates,
        'time': times,
        'sender': senders,
        'message': messages_text
    }).drop_duplicates()

def analyze_friendship(df):
    insights = {}
    
    # Message count analysis
    message_counts = df['sender'].value_counts()
    insights['message_counts'] = message_counts
    
    # Time analysis
    df['hour'] = df['time'].apply(lambda x: x.hour)
    night_owl_messages = df[df['hour'].between(22, 5)].groupby('sender').size()
    insights['night_owl'] = night_owl_messages
    
    # Emoji analysis
    def extract_emojis(text):
        return ''.join(c for c in str(text) if c in emoji.EMOJI_DATA)
    
    emoji_by_sender = {}
    for sender in df['sender'].unique():
        sender_messages = df[df['sender'] == sender]['message']
        emojis = []
        for msg in sender_messages:
            emojis.extend(list(extract_emojis(msg)))
        emoji_by_sender[sender] = Counter(emojis).most_common(5)
    
    insights['emoji_usage'] = emoji_by_sender
    
    # Response time analysis
    df['datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str))
    df['response_time'] = df['datetime'].diff()
    avg_response = df.groupby('sender')['response_time'].mean()
    insights['avg_response'] = avg_response
    
    # Message length analysis
    df['message_length'] = df['message'].str.len()
    avg_length = df.groupby('sender')['message_length'].mean()
    insights['avg_message_length'] = avg_length
    
    return insights

def create_visualizations(df, insights):
    # Message count visualization
    fig_messages = px.bar(
        x=insights['message_counts'].index,
        y=insights['message_counts'].values,
        title="Who's the Chattier Friend? 🗣️",
        labels={'x': 'Friend', 'y': 'Number of Messages'},
        color=insights['message_counts'].values,
        color_continuous_scale='Peach'  # Using a soft, friendly color scale
    )
    
    # Daily activity heatmap
    activity_by_hour = df.groupby(['sender', 'hour']).size().unstack(fill_value=0)
    fig_heatmap = px.imshow(
        activity_by_hour,
        title="When Do We Chat? 🕒",
        labels={'x': 'Hour of Day', 'y': 'Friend', 'color': 'Messages'},
        color_continuous_scale='YlGnBu'  # Using a light and friendly color scale
    )
    
    return fig_messages, fig_heatmap

def create_fun_insights(insights, df):
    fun_insights = {}
    
    # Early Bird vs Night Owl Analysis
    df['hour'] = df['time'].apply(lambda x: x.hour)
    early_bird_messages = df[df['hour'].between(5, 9)].groupby('sender').size()
    night_owl_messages = df[df['hour'].between(22, 5)].groupby('sender').size()
    
    early_bird = early_bird_messages.idxmax() if not early_bird_messages.empty else None
    night_owl = night_owl_messages.idxmax() if not night_owl_messages.empty else None
    
    fun_insights['sleep_schedule'] = {
        'early_bird': {
            'name': early_bird,
            'count': early_bird_messages.get(early_bird, 0),
            'message': "☀️ Early Bird Award: {} is up with the sun, sending {} messages before 9 AM!"
        },
        'night_owl': {
            'name': night_owl,
            'count': night_owl_messages.get(night_owl, 0),
            'message': "🦉 Night Owl Award: {} keeps the chat alive with {} late-night messages!"
        }
    }
    
    # Response Time Categories
    response_categories = {
        'lightning': pd.Timedelta(minutes=1),
        'quick': pd.Timedelta(minutes=5),
        'casual': pd.Timedelta(minutes=30),
        'relaxed': pd.Timedelta(hours=2),
        'internet_explorer': pd.Timedelta(hours=12)
    }
    
    response_styles = {}
    for sender in df['sender'].unique():
        sender_responses = df[df['sender'] == sender]['response_time']
        response_counts = {
            'lightning': len(sender_responses[sender_responses < response_categories['lightning']]),
            'quick': len(sender_responses[sender_responses < response_categories['quick']]),
            'casual': len(sender_responses[sender_responses < response_categories['casual']]),
            'relaxed': len(sender_responses[sender_responses < response_categories['relaxed']]),
            'internet_explorer': len(sender_responses[sender_responses >= response_categories['relaxed']])
        }
        response_styles[sender] = max(response_counts.items(), key=lambda x: x[1])
    
    fun_insights['response_styles'] = response_styles
    
    # Weekend Warriors vs Workday Champions
    df['is_weekend'] = df['date'].apply(lambda x: x.weekday() >= 5)
    weekend_ratio = df.groupby('sender')['is_weekend'].mean()
    weekend_warrior = weekend_ratio.idxmax()
    workday_champion = weekend_ratio.idxmin()
    
    fun_insights['chat_schedule'] = {
        'weekend_warrior': {
            'name': weekend_warrior,
            'ratio': weekend_ratio[weekend_warrior],
            'message': "🎉 Weekend Warrior: {} loves weekend chats ({:.1%} of their messages)!"
        },
        'workday_champion': {
            'name': workday_champion,
            'ratio': 1 - weekend_ratio[workday_champion],
            'message': "💼 Workday Champion: {} keeps it professional ({:.1%} workday messages)!"
        }
    }
    
    return fun_insights

def display_fun_insights(fun_insights):
    st.header("🎭 Fun Friendship Awards!")
    
    # Sleep Schedule Awards
    sleep_data = fun_insights['sleep_schedule']
    st.subheader("⏰ Sleep Schedule Analysis")
    if sleep_data['early_bird']['count'] > 0:
        st.write(sleep_data['early_bird']['message'].format(
            sleep_data['early_bird']['name'],
            sleep_data['early_bird']['count']
        ))
    if sleep_data['night_owl']['count'] > 0:
        st.write(sleep_data['night_owl']['message'].format(
            sleep_data['night_owl']['name'],
            sleep_data['night_owl']['count']
        ))
    
    # Response Style Awards
    st.subheader("⚡ Response Style Analysis")
    style_emojis = {
        'lightning': '⚡',
        'quick': '🏃',
        'casual': '🚶',
        'relaxed': '🧘',
        'internet_explorer': '🐌'
    }
    
    for sender, (style, count) in fun_insights['response_styles'].items():
        emoji = style_emojis.get(style, '📱')
        style_name = style.replace('_', ' ').title()
        st.write(f"{emoji} {sender} is a {style_name} Responder!")
    
    # Chat Schedule Awards
    st.subheader("📅 Chat Schedule Analysis")
    schedule_data = fun_insights['chat_schedule']
    st.write(schedule_data['weekend_warrior']['message'].format(
        schedule_data['weekend_warrior']['name'],
        schedule_data['weekend_warrior']['ratio']
    ))
    st.write(schedule_data['workday_champion']['message'].format(
        schedule_data['workday_champion']['name'],
        schedule_data['workday_champion']['ratio']
    ))
    
def analyze_first_messages(df):
    # Group messages by date and get the first message for each day
    df['date'] = pd.to_datetime(df['date'])
    first_messages = df.sort_values('time').groupby('date').first()
    first_message_counts = first_messages['sender'].value_counts()
    
    return first_message_counts

def create_first_message_chart(first_message_counts):
    fig = px.bar(
        x=first_message_counts.index,
        y=first_message_counts.values,
        title="Who Starts the Conversation? 🌅",
        labels={'x': 'Friend', 'y': 'Number of Days'},
        color=first_message_counts.values,
        color_continuous_scale='Viridis'
    )
    return fig

def main():
    st.title("🤝 Friendship Chat Analyzer")
    st.write("Let's settle who's the better friend with data! 📊")
    
    uploaded_file = st.file_uploader("Upload your WhatsApp chat!", type=['txt'])
    
    if uploaded_file:
        try:
            content = read_file_content(uploaded_file)
            
            # Debug information
            st.write("First few lines of the file:")
            st.code(content.split('\n')[:5])
            
            df = process_chat_file(content)
            
            if df.empty:
                st.error("No messages found! Are you sure this is a WhatsApp chat? 🤔")
                return
            
            st.success(f"Successfully processed {len(df)} messages!")
            
            # Display sample of processed data
            st.write("Sample of processed messages:")
            st.dataframe(df.head())
            
            insights = analyze_friendship(df)
            
            st.header("🏆 Friendship Stats!")
            
            # Message count comparison
            winner = insights['message_counts'].index[0]
            st.subheader(f"And the Chattiest Friend Award goes to... 🥁")
            st.write(f"🎉 {winner} with {insights['message_counts'].iloc[0]} messages!")
            
            # Create visualizations
            fig_messages, fig_heatmap = create_visualizations(df, insights)
            st.plotly_chart(fig_messages)
            st.plotly_chart(fig_heatmap)
            
            first_message_counts = analyze_first_messages(df)
            st.subheader("🌅 Early Bird Analysis")
            st.write(f"👑 {first_message_counts.index[0]} starts the most conversations, initiating {first_message_counts.iloc[0]} days!")
            fig_first_messages = create_first_message_chart(first_message_counts)
            st.plotly_chart(fig_first_messages)
            
            # Emoji analysis
            st.subheader("Favorite Emojis 😊")
            for sender, emojis in insights['emoji_usage'].items():
                if emojis:
                    emoji_text = ' '.join([f"{emoji} ({count})" for emoji, count in emojis])
                    st.write(f"{sender}'s top emojis: {emoji_text}")
            
            # Night owl analysis
            if not insights['night_owl'].empty:
                st.subheader("🦉 Night Owl Award")
                night_owl = insights['night_owl'].idxmax()
                st.write(f"{night_owl} is the night owl with {insights['night_owl'][night_owl]} late-night messages!")
            
            # Average message length
            st.subheader("📝 Message Length Award")
            longest = insights['avg_message_length'].idxmax()
            st.write(f"{longest} writes the longest messages with an average of {insights['avg_message_length'][longest]:.1f} characters!")
            
            # Fun insights display
            fun_insights = create_fun_insights(insights, df)
            display_fun_insights(fun_insights)
            
        except Exception as e:
            st.error(f"Oops! Something went wrong: {str(e)}")
            st.exception(e)

if __name__ == "__main__":
    main()
