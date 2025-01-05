import streamlit as st
import pandas as pd
import re
import zipfile
import io
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import emoji
import chardet
import random
import pyperclip

def detect_encoding(file_content):
    encodings = ['utf-8', 'utf-16', 'utf-16le', 'utf-16be', 'iso-8859-1']
    for encoding in encodings:
        try:
            return file_content.decode(encoding)
        except UnicodeDecodeError:
            continue
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
    # Updated pattern to handle both 12 and 24-hour formats with flexible separators
    pattern = r'(\d{1,2}/\d{1,2}/\d{2,4})(?:,\s*|\s+)(\d{1,2}:\d{2}(?:\u202f)?(?:\s)?(?:am|pm|AM|PM)?)\s*-\s*([^:]+): (.+)'
    
    dates, times, senders, messages_text = [], [], [], []
    current_message = ""

    date_formats = [
        '%d/%m/%y',     # 30/04/21
        '%m/%d/%y',     # 12/30/24
        '%d/%m/%Y',     # 30/04/2021
        '%m/%d/%Y'      # 12/30/2024
    ]
    
    time_formats = [
        '%I:%M %p',    # 9:46 am
        '%H:%M'        # 20:31
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
            
            # Try parsing date
            parsed_date = None
            for fmt in date_formats:
                try:
                    parsed_date = datetime.strptime(date_str, fmt).date()
                    break
                except ValueError:
                    continue
                    
            # Try parsing time
            parsed_time = None
            time_str = time_str.strip().lower()
            
            # Handle 24-hour format
            if 'am' not in time_str and 'pm' not in time_str:
                try:
                    parsed_time = datetime.strptime(time_str, '%H:%M').time()
                except ValueError:
                    # If 24-hour parse fails, try as 12-hour morning time
                    try:
                        parsed_time = datetime.strptime(time_str + ' am', '%I:%M %p').time()
                    except ValueError:
                        continue
            else:
                # Handle 12-hour format
                try:
                    parsed_time = datetime.strptime(time_str, '%I:%M %p').time()
                except ValueError:
                    continue

            if parsed_date and parsed_time:
                dates.append(parsed_date)
                times.append(parsed_time)
                senders.append(sender.strip())
                messages_text.append(text.strip())
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
    st.subheader("⏰ Sleep Schedule Awards")
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
    st.subheader("⚡ Response Style Awards")
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
    st.subheader("📅 Chat Schedule Awards")
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
    """
    🌅 Conversation Starter Analysis
    - Groups messages by date using df.groupby('date')
    - Gets first message each day with .first()
    - Counts how often each person starts conversations
    """
    df['date'] = pd.to_datetime(df['date'])
    first_messages = df.sort_values('time').groupby('date').first()
    first_message_counts = first_messages['sender'].value_counts()
    return first_message_counts

def analyze_response_times(df):
    """
    ⚡ Response Time Categories
    Classifies message response speeds:
    - Lightning: < 1 min
    - Quick: < 5 mins
    - Casual: < 30 mins  
    - Relaxed: < 2 hours
    - Internet Explorer: > 12 hours

    Steps:
    1. Sort messages by datetime
    2. Calculate time difference between messages
    3. Group by sender and categorize response speeds
    """
    # Define response categories
    response_categories = {
        'lightning': pd.Timedelta(minutes=1),
        'quick': pd.Timedelta(minutes=5),
        'casual': pd.Timedelta(minutes=30),
        'relaxed': pd.Timedelta(hours=2),
        'internet_explorer': pd.Timedelta(hours=12)
    }
    
    # Calculate response times
    df['datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str))
    df['response_time'] = df['datetime'].diff()
    
    # Categorize responses
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
    
    return response_styles

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

def process_uploaded_file(uploaded_file):
    """Process either a ZIP or TXT file and return the chat content."""
    if uploaded_file.name.endswith('.zip'):
        try:
            with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
                txt_files = [f for f in zip_ref.namelist() if f.endswith('.txt')]
                
                if not txt_files:
                    st.error("No .txt chat files found in the ZIP file.")
                    return None
                
                with zip_ref.open(txt_files[0]) as file:
                    return read_file_content(file)
        except Exception as e:
            st.error(f"Error processing ZIP file: {str(e)}")
            return None
    else:  # .txt file
        try:
            return read_file_content(uploaded_file)
        except Exception as e:
            st.error(f"Error processing TXT file: {str(e)}")
            return None
        
def create_sharable_text(df, insights, fun_insights, first_message_counts):
    text_parts = []
    
    text_parts.append("🎭 ULTIMATE CHUBBY BUDDY FRIENDSHIP REPORT 🎭\n")
    text_parts.append("(Generated by the Chubby Buddy Friendship Analyzer LOVE YOUR FRIEND 3000+)\n")
    
    # Message Count Stats
    text_parts.append("\n📱 THE BIG NUMBERS SHOWDOWN")
    text_parts.append("------------------------")
    for friend, count in insights['message_counts'].items():
        text_parts.append(f"🎯 {friend}: {count} messages sent to the friendship void")
    
    # First Message Hero
    text_parts.append("\n🌅 THE CONVERSATION STARTER AWARD")
    text_parts.append("--------------------------------")
    first_starter = first_message_counts.index[0]
    second_starter = first_message_counts.index[1]
    first_count = first_message_counts.iloc[0]
    second_count = first_message_counts.iloc[1]
    total_days = first_count + second_count
    
    text_parts.append(f"👑 {first_starter}: Started {first_count} conversations ({(first_count/total_days*100):.1f}%)")
    text_parts.append(f"🌟 {second_starter}: Started {second_count} conversations ({(second_count/total_days*100):.1f}%)")
    
    # Favorite Emojis Section
    text_parts.append("\n😊 EMOJI PERSONALITIES")
    text_parts.append("--------------------")
    for sender, emojis in insights['emoji_usage'].items():
        if emojis:
            # Get top 3 emojis for a cleaner display
            top_emojis = emojis[:3]
            emoji_text = ' | '.join([f"{emoji} ({count})" for emoji, count in top_emojis])
            text_parts.append(f"💝 {sender}'s top 3: {emoji_text}")
    
    # Message Length
    text_parts.append("\n📝 THE WORDSMITH AWARDS")
    text_parts.append("----------------------")
    for friend, length in insights['avg_message_length'].items():
        text_parts.append(f"✍️ {friend}: Wordsmith Score 📝 {length:.1f} characters")
    
    # Response Time Analysis
    text_parts.append("\n⚡ SPEED DEMONS & SLOW POKES")
    text_parts.append("---------------------------")
    for friend, (style, _) in fun_insights['response_styles'].items():
        style_emojis = {
            'lightning': '⚡ SONIC SPEED',
            'quick': '🏃 SPEEDY GONZALES',
            'casual': '🚶 TAKING IT EASY',
            'relaxed': '🧘 ZEN MASTER',
            'internet_explorer': '🐌 INTERNET EXPLORER MODE'
        }
        text_parts.append(f"{style_emojis.get(style, '📱')} {friend}")

    # Add explanations at the end
    text_parts.append("\n📊 HOW IT'S CALCULATED")
    text_parts.append("-------------------")
    text_parts.append("🌅 Conversation Kickstarter Awards 🌟: First message of each day")
    text_parts.append("😊 Emoji Personalities: Top 3 most used emojis")
    text_parts.append("⚡ Response Speed Categories:")
    text_parts.append("⚡ SONIC SPEED: < 1 min")
    text_parts.append("🏃 SPEEDY GONZALES: < 5 mins") 
    text_parts.append("🚶 TAKING IT EASY: < 30 mins")
    text_parts.append("🧘 ZEN MASTER: < 2 hours")
    text_parts.append("🐌 INTERNET EXPLORER MODE: > 12 hours")

    return "\n".join(text_parts)

def main():
    st.title("🤝 Chubby Buddy Chat Analyzer")
    st.write("Let's settle who's the better friend with data! 📊")
    
    uploaded_file = st.file_uploader("Drop Your Friendship Chronicles Here! 📱", type=['zip', 'txt'])
    
    if uploaded_file:
        content = process_uploaded_file(uploaded_file)
    
        if content:
            df = process_chat_file(content)
            if df.empty:
                st.error("No messages found! Are you sure this is a WhatsApp chat? 🤔")
                return
            
            insights = analyze_friendship(df)
            fun_insights = create_fun_insights(insights, df)
            first_message_counts = analyze_first_messages(df)
            share_text = create_sharable_text(df, insights, fun_insights, first_message_counts)
            
            # Main visualizations
            st.header("🏆 Friendship Stats!")
            
            # Add total messages count
            total_messages = insights['message_counts'].sum()
            st.metric("Message Mountain 📱 (Total Messages 💬)", f"{total_messages:,}")
            
            # Get top two participants
            winner = insights['message_counts'].index[0]
            runner_up = insights['message_counts'].index[1]
            winner_count = insights['message_counts'].iloc[0]
            runner_up_count = insights['message_counts'].iloc[1]
            
            st.subheader(f"And the Chattiest Friend Award goes to... 🥁")
            st.write(f"🥇 {winner} with {winner_count:,} messages!🎉🎉🎉")
            st.write(f"🥈 {runner_up} with {runner_up_count:,} messages!")

            
            fig_messages, fig_heatmap = create_visualizations(df, insights)
            st.plotly_chart(fig_messages)
            st.plotly_chart(fig_heatmap)
            
            first_message_counts = analyze_first_messages(df)
            st.subheader("🌅 The Conversation Kickstarter 🌟")
    
            # Get stats for both participants
            first_starter = first_message_counts.index[0]
            second_starter = first_message_counts.index[1]
            first_count = first_message_counts.iloc[0]
            second_count = first_message_counts.iloc[1]
    
            # Display both participants' stats
            st.write(f"👑 {first_starter} initiated {first_count} conversations")
            st.write(f"🌟 {second_starter} initiated {second_count} conversations")
    
            # Calculate and show percentages
            total_days = first_count + second_count
            first_percentage = (first_count / total_days) * 100
            second_percentage = (second_count / total_days) * 100
    
            st.write(f"\nPercentage breakdown:")
            st.write(f"- {first_starter}: {first_percentage:.1f}% of conversations")
            st.write(f"- {second_starter}: {second_percentage:.1f}% of conversations")
    
            fig_first_messages = create_first_message_chart(first_message_counts)
            st.plotly_chart(fig_first_messages)
            
            st.subheader("Favorite Emojis 😊")
            for sender, emojis in insights['emoji_usage'].items():
                if emojis:
                    emoji_text = ' '.join([f"{emoji} ({count})" for emoji, count in emojis])
                    st.write(f"{sender}'s top emojis: {emoji_text}")
            
            if not insights['night_owl'].empty:
                st.subheader("🦉 Night Owl Award")
                night_owl = insights['night_owl'].idxmax()
                st.write(f"{night_owl} is the night owl with {insights['night_owl'][night_owl]} late-night messages!")
            
            st.subheader("📝 Message Length Award")
            longest = insights['avg_message_length'].idxmax()
            st.write(f"{longest} writes the longest messages with an average of {insights['avg_message_length'][longest]:.1f} characters!")
            
            display_fun_insights(fun_insights)
            
            # Sharing section moved to end
            st.subheader("Share Your Friendship Stats!")
            st.code(share_text)
            
            # JavaScript for copy functionality
            js_code = f"""
            <script>
            function copyToClipboard() {{
                const text = `{share_text}`;
                navigator.clipboard.writeText(text)
                    .then(() => alert('Friendship stats copied! Ready to share! 🎉'))
                    .catch(err => console.error('Failed to copy:', err));
            }}
            </script>
            <button onclick="copyToClipboard()" style="background-color: #FF4B4B; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer;">📋 Copy Friendship Stats</button>
            """
            st.components.v1.html(js_code, height=50)

if __name__ == "__main__":
    main()
