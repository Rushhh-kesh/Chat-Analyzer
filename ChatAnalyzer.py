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

def compare_chats(dataframes, names):
    """Compare multiple chat analyses with emoji metrics"""
    comparison = {}
    
    # Message Volume by Participant
    participant_messages = {}
    for name, df in dataframes.items():
        participant_messages[name] = df['sender'].value_counts().to_dict()
    comparison['participant_messages'] = participant_messages
    
    # Daily Chat Energy Level
    daily_averages = {
        name: len(df) / len(df['date'].unique())
        for name, df in dataframes.items()
    }
    comparison['daily_averages'] = daily_averages
    
    # Daily Activity Patterns
    hourly_patterns = {}
    for name, df in dataframes.items():
        df['hour'] = df['time'].apply(lambda x: x.hour)
        hourly_patterns[name] = df.groupby('hour').size()
    comparison['hourly_patterns'] = hourly_patterns
    
    # Emoji Analysis
    def extract_emojis(text):
        return ''.join(c for c in str(text) if c in emoji.EMOJI_DATA)
    
    emoji_usage = {}
    emoji_rates = {}
    for name, df in dataframes.items():
        emoji_usage[name] = {}
        total_emojis = 0
        total_messages = len(df)
        
        for sender in df['sender'].unique():
            sender_messages = df[df['sender'] == sender]['message']
            emojis = []
            for msg in sender_messages:
                msg_emojis = list(extract_emojis(msg))
                emojis.extend(msg_emojis)
                total_emojis += len(msg_emojis)
            emoji_usage[name][sender] = Counter(emojis).most_common(5)
        
        emoji_rates[name] = total_emojis / total_messages if total_messages > 0 else 0
    
    comparison['emoji_usage'] = emoji_usage
    comparison['emoji_rates'] = emoji_rates
    
    # Weekend Analysis
    weekend_rates = {}
    for name, df in dataframes.items():
        df['is_weekend'] = df['date'].apply(lambda x: x.weekday() >= 5)
        weekend_rates[name] = df['is_weekend'].mean()
    comparison['weekend_rates'] = weekend_rates
    
    # Interesting Facts
    facts = {}
    for name, df in dataframes.items():
        facts[name] = {
            'busiest_day': df.groupby('date').size().idxmax(),
            'busiest_day_messages': df.groupby('date').size().max(),
            'most_active_hour': df['hour'].mode().iloc[0],
            'longest_message_length': df['message'].str.len().max(),
            'avg_message_length': df['message'].str.len().mean(),
            'total_days': len(df['date'].unique()),
            'participant_stats': {
                sender: {
                    'total_messages': len(df[df['sender'] == sender]),
                    'avg_length': df[df['sender'] == sender]['message'].str.len().mean(),
                    'messages_per_day': len(df[df['sender'] == sender]) / len(df['date'].unique())
                }
                for sender in df['sender'].unique()
            }
        }
    comparison['facts'] = facts
    
    return comparison

def create_comparison_charts(comparison):
    """Create visualizations for chat comparisons"""
    charts = []
    
    # Message Volume by Participant
    participant_data = []
    for chat_name, participants in comparison['participant_messages'].items():
        for participant, count in participants.items():
            participant_data.append({
                'Chat': chat_name,
                'Participant': participant,
                'Messages': count
            })
    
    df_participants = pd.DataFrame(participant_data)
    fig_participants = px.bar(
        df_participants,
        x='Chat',
        y='Messages',
        color='Participant',
        title="👥 Message Count by Participant",
        barmode='group'
    )
    charts.append(fig_participants)
    
    # Daily Activity Patterns
    hourly_data = pd.DataFrame(comparison['hourly_patterns'])
    fig_hourly = px.line(
        hourly_data,
        title="📊 When We're In Our Element ⚡️",
        labels={'value': 'Message Count', 'index': 'Hour of Day'},
        markers=True
    )
    fig_hourly.update_layout(
        xaxis_title="Hour of Day",
        yaxis_title="Message Count",
        showlegend=True
    )
    charts.append(fig_hourly)
    
    return charts

def create_comparison_summary(comparison):
    """Create updated summary with emoji stats"""
    summary = []
    summary.append("🌟 SQUAD SHOWDOWN INSIGHTS 🌟\n")
    
    # Participant Message Counts and Stats
    for chat_name, facts in comparison['facts'].items():
        summary.append(f"\n📱 {chat_name} Squad Breakdown:")
        for participant, stats in facts['participant_stats'].items():
            summary.append(f"\n{participant}:")
            summary.append(f"- 💬 Total messages: {stats['total_messages']:,}")
            summary.append(f"- 📊 Messages per day: {stats['messages_per_day']:.1f}")
            summary.append(f"- 📝 Average length: {stats['avg_length']:.1f} characters")
            
            # Add emoji stats
            if chat_name in comparison['emoji_usage'] and participant in comparison['emoji_usage'][chat_name]:
                emoji_stats = comparison['emoji_usage'][chat_name][participant]
                if emoji_stats:
                    emoji_text = ' '.join([f"{emoji}({count})" for emoji, count in emoji_stats[:3]])
                    summary.append(f"- 😊 Top emojis: {emoji_text}")
    
    # General Chat Stats
    summary.append("\n🎯 Main Character Moments ✨")
    for name, facts in comparison['facts'].items():
        summary.append(f"\n{name}:")
        summary.append(f"- When We Popped Off 💅✨: {facts['busiest_day'].strftime('%Y-%m-%d')} ({facts['busiest_day_messages']} messages)")
        summary.append(f"- ⏰ Peak activity: {facts['most_active_hour']:02d}:00")
        summary.append(f"- 📅 Total days: {facts['total_days']}")
    
    return "\n".join(summary)

def display_chat_highlights(highlights):
    """Display Main Character Moments ✨ in the Streamlit interface."""
    st.header("🎯 Main Character Moments ✨!")
    
    # Most Active Day
    if 'most_active_day' in highlights:
        active = highlights['most_active_day']
        st.write("\nWhen We Popped Off 💅✨")
        st.write(f"- 📅 Date: {active['date'].strftime('%B %d, %Y')}")
        st.write(f"- 💬 Message Count: {active['messages']:,} messages")
        st.write(f"- 👥 Squad Members: {', '.join(active['participants'])}")
    
    # Longest Conversation
    if 'longest_conversation' in highlights:
        convo = highlights['longest_conversation']
        st.write("\nNon-Stop Bestie Hours 🔄✨")
        st.write(f"- 💫 {convo['messages']:,} messages in {convo['duration'].total_seconds()/60:.0f} minutes!")
        st.write(f"- 📅 Date: {convo['date'].strftime('%B %d, %Y')}")
        st.write(f"- 👥 Squad Members: {', '.join(convo['participants'])}")
    
    # Longest Messages Champions
    if 'longest_messages' in highlights:
        st.write("\n📝 Message Length Champions")
        for sender, msg_data in highlights['longest_messages'].items():
            st.write(f"- ✨ {sender}: {msg_data['length']:,} characters on {msg_data['date'].strftime('%B %d, %Y')}")

def analyze_chat_highlights(df):
    """Analyze notable moments and patterns in chat history."""
    highlights = {}
    
    # Longest conversation (most back-and-forth in 30 min window)
    df['datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str))
    df['timediff'] = df['datetime'].diff()
    conversation_window = pd.Timedelta(minutes=30)
    
    current_convo = []
    conversations = []
    
    for i in range(1, len(df)):
        if df['timediff'].iloc[i] <= conversation_window:
            if not current_convo:
                current_convo.append(df.iloc[i-1])
            current_convo.append(df.iloc[i])
        else:
            if current_convo:
                conversations.append(current_convo)
                current_convo = []
    
    if current_convo:
        conversations.append(current_convo)
    
    if conversations:
        longest_convo = max(conversations, key=len)
        highlights['longest_conversation'] = {
            'messages': len(longest_convo),
            'date': longest_convo[0]['date'],
            'duration': (longest_convo[-1]['datetime'] - longest_convo[0]['datetime']),
            'participants': list(set(msg['sender'] for msg in longest_convo))
        }
    
    # Most active day
    daily_counts = df.groupby('date').size()
    most_active_day = daily_counts.idxmax()
    highlights['most_active_day'] = {
        'date': most_active_day,
        'messages': daily_counts[most_active_day],
        'participants': list(df[df['date'] == most_active_day]['sender'].unique())
    }
    
    # Longest message by each participant
    longest_messages = {}
    for sender in df['sender'].unique():
        sender_messages = df[df['sender'] == sender]
        longest_idx = sender_messages['message'].str.len().idxmax()
        longest_messages[sender] = {
            'message': df.loc[longest_idx, 'message'],
            'length': len(df.loc[longest_idx, 'message']),
            'date': df.loc[longest_idx, 'date']
        }
    highlights['longest_messages'] = longest_messages
    
    return highlights

def analyze_extended_metrics(df):
    """
    Analyze additional chat metrics including typing marathons, funny messages,
    speed records, and longest gaps.
    """
    extended_metrics = {}
    
    # Prepare datetime for analysis
    df['datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str))
    df['timediff'] = df['datetime'].diff()
    
    # 1. Longest Typing Marathon (messages in quick succession by same person)
    marathon_window = pd.Timedelta(minutes=5)  # Define quick succession as within 5 minutes
    current_marathon = []
    marathons = []
    
    for i in range(1, len(df)):
        current_sender = df.iloc[i]['sender']
        prev_sender = df.iloc[i-1]['sender']
        
        if (current_sender == prev_sender and 
            df['timediff'].iloc[i] <= marathon_window):
            if not current_marathon:
                current_marathon.append(df.iloc[i-1])
            current_marathon.append(df.iloc[i])
        else:
            if current_marathon:
                marathons.append(current_marathon)
                current_marathon = []
    
    if marathons:
        longest_marathon = max(marathons, key=len)
        extended_metrics['typing_marathon'] = {
            'sender': longest_marathon[0]['sender'],
            'messages': len(longest_marathon),
            'date': longest_marathon[0]['date'],
            'duration': (longest_marathon[-1]['datetime'] - longest_marathon[0]['datetime'])
        }
    
    # 3. Longest Time Without Reply
    max_gap = df['timediff'].max()
    gap_idx = df['timediff'].idxmax()
    if pd.notnull(max_gap):
        extended_metrics['longest_gap'] = {
            'duration': max_gap,
            'date': df.loc[gap_idx, 'date'],
            'next_sender': df.loc[gap_idx, 'sender'],
            'prev_sender': df.loc[gap_idx-1, 'sender'] if gap_idx > 0 else None
        }
    
    # 4. Funny Messages (messages with 'haha', 'lol', '😂', etc.)
    funny_indicators = ['haha', 'lol', '😂', '🤣', 'lmao', 'rofl']
    funny_messages = {}
    
    for sender in df['sender'].unique():
        sender_messages = df[df['sender'] == sender]['message']
        funny_count = 0
        for msg in sender_messages:
            if any(indicator in msg.lower() for indicator in funny_indicators):
                funny_count += 1
        
        if funny_count > 0:
            funny_messages[sender] = {
                'count': funny_count,
                'percentage': (funny_count / len(sender_messages)) * 100
            }
    
    extended_metrics['funny_messages'] = funny_messages
    
    return extended_metrics

def display_extended_metrics(extended_metrics):
    """Display the extended metrics in a friendly format."""
    st.header("🎯 More Fun Chat Stats!")
    
    # 1. Typing Marathon
    if 'typing_marathon' in extended_metrics:
        marathon = extended_metrics['typing_marathon']
        st.subheader("Speed Typer Supreme 🏃‍♂️💨")
        st.write(f"🏃 {marathon['sender']} went on a typing spree with {marathon['messages']} messages")
        st.write(f"📅 Date: {marathon['date'].strftime('%B %d, %Y')}")
        st.write(f"⏱️ Duration: {marathon['duration'].total_seconds() / 60:.1f} minutes")
    
    # 2. Speed Records
    if 'speed_records' in extended_metrics:
        st.subheader("⚡ Speed Demons (Fastest Replies)")
        for sender, record in extended_metrics['speed_records'].items():
            seconds = record['time'].total_seconds()
            st.write(f"🏃 {sender}: {seconds:.1f} seconds")
            st.write(f"📅 Achievement unlocked on: {record['date'].strftime('%B %d, %Y')}")
    
    # 3. Longest Gap
    if 'longest_gap' in extended_metrics:
        gap = extended_metrics['longest_gap']
        st.subheader("🕒 Ghost Mode Timeline 👻⏰")
        days = gap['duration'].total_seconds() / (24 * 3600)
        st.write(f"⏳ {days:.1f} days of silence")
        st.write(f"📅 Ended: {gap['date'].strftime('%B %d, %Y')}")
        if gap['prev_sender'] and gap['next_sender']:
            st.write(f"👥 From {gap['prev_sender']} to {gap['next_sender']}")
    
    # 4. Funny Messages
    if 'funny_messages' in extended_metrics:
        st.subheader("Bestie Humor Check (Real Tea) 💅😂")
        for sender, stats in extended_metrics['funny_messages'].items():
            st.write(f"😄 {sender}:")
            st.write(f"- 🎯 {stats['count']} funny messages")
            st.write(f"- 📊 {stats['percentage']:.1f}% of their messages contain laughter")
                    
def create_sharable_text(df, insights, fun_insights, first_message_counts):
    # First, get the extended metrics
    extended_metrics = analyze_extended_metrics(df)
    
    text_parts = []
    
    text_parts.append("ULTIMATE ChatWrap FRIENDSHIP REPORT\n")
    text_parts.append("(Powered by ChatWrap Friendship Analyzer LOVE YOUR FRIEND 3000+)\n")
    
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
            text_parts.append(f"🤌🏼 {sender}'s top 3: {emoji_text}")
    
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

    # Add Main Character Moments ✨ Section
    highlights = analyze_chat_highlights(df)
    text_parts.append("\n🎯 Main Character Moments ✨")
    text_parts.append("✨💖✨💖✨💖✨💖✨💖✨")
    text_parts.append("       ")
    
    # Most Active Day
    if 'most_active_day' in highlights:
        active = highlights['most_active_day']
        text_parts.append(f"🔥 Most Active Day: {active['date'].strftime('%B %d, %Y')} with {active['messages']} messages")

    # Longest Conversation
    if 'longest_conversation' in highlights:
        convo = highlights['longest_conversation']
        text_parts.append(f"🗣️ Longest Conversation: {convo['messages']} messages over {convo['duration'].total_seconds() // 60:.0f} minutes on {convo['date'].strftime('%B %d, %Y')}")

    # Longest Messages Champions
    if 'longest_messages' in highlights:
        text_parts.append("\n📝 Longest Messages")
        for sender, msg_data in highlights['longest_messages'].items():
            text_parts.append(f"- ✨ {sender}: {msg_data['length']} characters on {msg_data['date'].strftime('%B %d, %Y')}")

    if extended_metrics:
        text_parts.append("\n🎯 Extra Tea ☕️ (Basically The Receipts 🧾)")
        text_parts.append("💫🌟💫🌟💫🌟💫🌟💫🌟💫")

        # 1. Typing Marathon Stats
        text_parts.append("\n⚡️ BESTIE WENT BERZERK FR FR")
        text_parts.append("             ")
        if 'typing_marathon' in extended_metrics:
            marathon = extended_metrics['typing_marathon']
            text_parts.append(f"🏃 Marathon Champion: {marathon['sender']}")
            text_parts.append(f"📊 Epic Stats:")
            text_parts.append(f"   - Messages in streak: {marathon['messages']}")
            text_parts.append(f"   - Duration: {marathon['duration'].total_seconds() / 60:.1f} minutes")
            text_parts.append(f"   - Date: {marathon['date'].strftime('%B %d, %Y')}")
            text_parts.append(f"   - Messages per minute: {marathon['messages'] / (marathon['duration'].total_seconds() / 60):.1f}")

        # 3. Chat Gaps Analysis
        text_parts.append("\n🕒 Ghost Mode Timeline 👻⏰")
        if 'longest_gap' in extended_metrics:
            gap = extended_metrics['longest_gap']
            days = gap['duration'].total_seconds() / (24 * 3600)
            hours = (days - int(days)) * 24
            text_parts.append(f"\n⏳ Longest Gap Details:")
            text_parts.append(f"   - Duration: {int(days)} days and {int(hours)} hours")
            text_parts.append(f"   - Ended: {gap['date'].strftime('%B %d, %Y')}")
            if gap['prev_sender'] and gap['next_sender']:
                text_parts.append(f"   - Last message by: {gap['prev_sender']}")
                text_parts.append(f"   - Silence broken by: {gap['next_sender']}")

        # 4. Laughter and Fun Analysis
        text_parts.append("\n😂 Bestie LOL Report 🤣💅")
        if 'funny_messages' in extended_metrics:
            text_parts.append("\n🤣 COMEDY KING/QUEEN BEHAVIOUR")
            for sender, stats in extended_metrics['funny_messages'].items():
                text_parts.append(f"\n😄 {sender}'s Fun Stats:")
                text_parts.append(f"   - Total fun messages: {stats['count']}")
                text_parts.append(f"   - Fun percentage: {stats['percentage']:.1f}%")
                text_parts.append(f"   - That's {stats['count'] / len(df[df['sender'] == sender]) * 100:.1f}% of their total messages!")
                
        # 5. Time Distribution Analysis
        text_parts.append("\n⏰ Clock Check (AKA When We're In Our Element) ⏰✨")
        # Get all unique participants
        participants = df['sender'].unique()
        
        for sender in participants:
            sender_df = df[df['sender'] == sender]
            sender_df['hour'] = sender_df['time'].apply(lambda x: x.hour)
            
            # Peak hour analysis
            hour_counts = sender_df['hour'].value_counts()
            peak_hour = hour_counts.index[0]
            peak_count = hour_counts.iloc[0]
            
            text_parts.append(f"\n🌟 {sender}'s Time Profile:")
            text_parts.append(f"   - Peak activity hour: {peak_hour:02d}:00")
            text_parts.append(f"   - Messages at peak hour: {peak_count}")
            
            # Morning/Night ratio with fixed calculation
            total_messages = len(sender_df)
            morning_messages = len(sender_df[sender_df['hour'].between(6, 11)])
            # Fixed night messages calculation
            night_messages = len(sender_df[
                (sender_df['hour'] >= 22) | (sender_df['hour'] <= 5)
            ])
            
            morning_percentage = (morning_messages/total_messages*100) if total_messages > 0 else 0
            night_percentage = (night_messages/total_messages*100) if total_messages > 0 else 0
            
            text_parts.append(f"   - Morning person score: {morning_percentage:.1f}%")
            text_parts.append(f"   - Night owl score: {night_percentage:.1f}%")


        # 6. Message Length Analysis
        text_parts.append("\n💅 TEXTING STYLE REPORT (NO CAP)")
        for sender in df['sender'].unique():
            sender_messages = df[df['sender'] == sender]['message']
            lengths = [len(msg) for msg in sender_messages]
            
            text_parts.append(f"\n✍️ {sender}'s Writing Style:")
            text_parts.append(f"   - Longest message: {max(lengths)} characters")
            text_parts.append(f"   - Average length: {sum(lengths)/len(lengths):.1f} characters")
            text_parts.append(f"   - Short messages (<50 chars): {sum(1 for l in lengths if l < 50)} messages")
            text_parts.append(f"   - Long messages (>200 chars): {sum(1 for l in lengths if l > 200)} messages")
        
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
    st.title("🤝 ChatWrap Chat Analyzer")
    st.write("Let's see who's winning at friendship! 📊")
    
    analysis_mode = st.selectbox(
        "Choose Your Friendship Analysis Adventure! 🎮",
        ["Single Squad Vibe Check 👥✨", "Squad vs Squad Battle Royale 🎮💥"]
    )
    
    if analysis_mode == "Single Squad Vibe Check 👥✨":
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
                
                st.subheader("Emoji Personality Check 😊")
                for sender, emojis in insights['emoji_usage'].items():
                    if emojis:
                        emoji_text = ' '.join([f"{emoji} ({count})" for emoji, count in emojis])
                        st.write(f"✨ {sender}'s emoji favorites: {emoji_text}")
                
                if not insights['night_owl'].empty:
                    st.subheader("🦉 Night Owl Champion")
                    night_owl = insights['night_owl'].idxmax()
                    st.write(f"🌙 {night_owl} is our nocturnal chat champion with {insights['night_owl'][night_owl]} late-night messages!")
                
                st.subheader("📝 Wordsmith Champion")
                longest = insights['avg_message_length'].idxmax()
                st.write(f"✍️ {longest} is our storyteller with an average of {insights['avg_message_length'][longest]:.1f} characters per message!")
                
                display_fun_insights(fun_insights)               
                highlights = analyze_chat_highlights(df)
                display_chat_highlights(highlights)
                extended_metrics = analyze_extended_metrics(df)    
                display_extended_metrics(extended_metrics)  
                                
                # Sharing section
                st.subheader("📲 Share Your Friendship Story!")
                st.code(share_text)
                st.components.v1.html(
                    f"""
                    <button
                        onclick="navigator.clipboard.writeText(`{share_text}`);this.innerHTML='Copied! 🎉';"
                        style="
                            background-color: #FF4B4B;
                            color: white;
                            padding: 10px 20px;
                            border: none;
                            border-radius: 5px;
                            cursor: pointer;
                            margin: 10px 0;
                        "
                    >
                        📋 Copy Friendship Stats
                    </button>
                    """,
                    height=50
                )
                
    else:  # Squad vs Squad Battle Royale 🎮💥 mode
        st.write("Time for the Ultimate Friendship Squad Showdown! 🎭")
        uploaded_files = st.file_uploader(
            "Upload Your Squad Chronicles! 📱",
            type=['zip', 'txt'],
            accept_multiple_files=True
        )
        
        if uploaded_files and len(uploaded_files) >= 2:
            dataframes = {}
            
            # Process each file
            for file in uploaded_files:
                content = process_uploaded_file(file)
                if content:
                    df = process_chat_file(content)
                    if not df.empty:
                        chat_name = st.text_input(
                            f"Give a fun name to {file.name}'s squad! 🎭",
                            value=file.name.split('.')[0]
                        )
                        dataframes[chat_name] = df
            
            if len(dataframes) >= 2:
                st.header("🎭 Squad Showdown Results!")
                
                # Run comparison analysis
                comparison = compare_chats(dataframes, list(dataframes.keys()))
                
                # Display total messages comparison
                st.subheader("📊 Message Mountain Comparison")
                total_messages = {name: len(df) for name, df in dataframes.items()}
                champion = max(total_messages.items(), key=lambda x: x[1])
                st.write(f"👑 Chat Champion: {champion[0]} with {champion[1]:,} messages!")
                
                # Display comparison charts
                charts = create_comparison_charts(comparison)
                for chart in charts:
                    st.plotly_chart(chart)
                
                # Display fun summary
                st.header("📊 The Ultimate Friendship Showdown!")
                summary = create_comparison_summary(comparison)
                st.markdown(summary)
                
                # Special achievements section
                st.subheader("🏆 Special Squad Achievements!")
                
                # Most consistent squad
                most_consistent = min(comparison['daily_averages'].items(), 
                                    key=lambda x: abs(x[1] - sum(comparison['daily_averages'].values()) / len(comparison['daily_averages'])))
                st.write(f"🎯 Most Consistent Squad: {most_consistent[0]}")
                
                # Emoji party champion
                emoji_champion = max(comparison['emoji_rates'].items(), key=lambda x: x[1])
                st.write(f"🎨 Emoji Party Champion: {emoji_champion[0]}")
                
                # Weekend warrior
                weekend_champion = max(comparison['weekend_rates'].items(), key=lambda x: x[1])
                st.write(f"🎉 Weekend Warrior Squad: {weekend_champion[0]}")
                
                # Add sharing option
                st.subheader("Share the Squad Showdown! 🎉")
                st.code(summary)
                st.components.v1.html(
                    f"""
                    <button
                        onclick="navigator.clipboard.writeText(`{summary}`);this.innerHTML='Copied! 🎉';"
                        style="
                            background-color: #FF4B4B;
                            color: white;
                            padding: 10px 20px;
                            border: none;
                            border-radius: 5px;
                            cursor: pointer;
                            margin: 10px 0;
                        "
                    >
                        📋 Copy Squad Showdown Stats
                    </button>
                    """,
                    height=50
                )
        elif uploaded_files:
            st.warning("Hey buddy! We need at least 2 chat files for a proper Squad Showdown! 🎭")

if __name__ == "__main__":
    main()
