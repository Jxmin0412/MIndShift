import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import datetime
import plotly.graph_objects as go
import openai

# Set OpenAI API key securely
openai.api_key = st.secrets["openai.api_key"]
if not openai.api_key:
    st.error("OpenAI API Key is missing. Set it in the .env file.")

# Download NLTK resources
nltk.download("punkt", quiet=True)
nltk.download("stopwords", quiet=True)


# Function to clean text
def clean_text(text):
    words = word_tokenize(text.lower())
    stop_words = set(stopwords.words("english"))
    filtered_words = [
        word for word in words if word not in stop_words and word.isalpha()
    ]
    return " ".join(filtered_words)


# Function to scrape course content
def scrape_course(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None, "Failed to fetch content"

    soup = BeautifulSoup(response.text, "html.parser")
    what_you_learn = []
    learn_section = soup.find("section", {"class": "css-1t957yb"})
    if learn_section:
        what_you_learn = [item.text.strip() for item in learn_section.find_all("li")]

    skills_section = soup.find("div", {"class": "css-1m3kxpf"})
    skills = (
        [skill.text.strip() for skill in skills_section.find_all("span")]
        if skills_section
        else []
    )

    cleaned_data = {
        "What You'll Learn": [clean_text(item) for item in what_you_learn],
        "Skills You'll Gain": [clean_text(skill) for skill in skills],
    }
    return cleaned_data, None


# Function to fetch questions using OpenAI API
# @st.cache_data
def fetch_questions(text_content, quiz_level):
    prompt = f"""
    Generate 7 multiple-choice questions (MCQs) and true/false questions based on this content:
    Level: {quiz_level}
    Content: {text_content}
    Format as JSON:
    [
        {{"mcq": "...", "options": {{"a": "...", "b": "...", "c": "...", "d": "..."}}, "correct": "a"}},
        ...
    ]
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000,
        )
        response_text = response.choices[0].message.content

        try:
            questions = json.loads(response_text)
            # Skip malformed questions
            valid_questions = [
                question
                for question in questions
                if isinstance(question, dict)
                and "mcq" in question
                and isinstance(question["mcq"], str)
                and "options" in question
                and isinstance(question["options"], dict)
                and "correct" in question
                and question["correct"] in question["options"]
            ]
            if not valid_questions:
                st.warning(
                    "No valid questions were generated. OpenAI may have returned malformed data."
                )
            return valid_questions
        except json.JSONDecodeError as e:
            st.error(f"Error parsing JSON from OpenAI: {e}")
            return []

    except Exception as e:
        st.error(f"Error generating quiz: {e}")
        return []

def generate_post_learning_quiz(roadmap_content, quiz_level):
    prompt = f"""
    Based on this roadmap content: {roadmap_content}, create a set of 7 post-learning questions with a mix of MCQs and True/False. 
    Level: {quiz_level}
    Format as JSON:
    [
        {{"type": "mcq", "question": "...", "options": {{"a": "...", "b": "...", "c": "...", "d": "..."}}, "correct": "a"}},
        {{"type": "true_false", "question": "...", "correct": true}}
    ]
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000,
        )
        response_text = response.choices[0].message.content

        try:
            questions = json.loads(response_text)
            # Filter out malformed questions
            valid_questions = [
                question
                for question in questions
                if (
                    question["type"] == "mcq"
                    and "options" in question
                    and question["correct"] in question["options"]
                )
                or (
                    question["type"] == "true_false"
                    and "correct" in question
                    and isinstance(question["correct"], bool)
                )
            ]
            return valid_questions
        except json.JSONDecodeError as e:
            st.error(f"Error parsing JSON from OpenAI: {e}")
            return []
    except Exception as e:
        st.error(f"Error generating post-learning quiz: {e}")
        return []



# Streamlit App
def main():

    # global variables
    course_data = {}

    st.title("Welcome to MindShift!")
    st.subheader("Your Personalized Learning Platform")

    # Footer
    st.markdown("---")
    st.markdown("### Ready to shift your mind? Let's get started!")

    # Initialize session state
    if "course_topics" not in st.session_state:
        st.session_state["course_topics"] = []
    if "quizzes" not in st.session_state:
        st.session_state["quizzes"] = []

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Home", "Pre-learning Quiz", "Roadmap", "Post-learning Quiz"])

    # Home Tab
    with tab1:
        st.subheader("Input Course URL")
        course_url = st.text_input("Enter the course URL:")
        if course_url:
            data, error = scrape_course(course_url)
            if error:
                st.error(error)
            else:
                course_data = data # your data on a global var
                st.json(data)
                st.session_state["course_topics"] = data.get("What You'll Learn", [])

    # Quizzes Tab
    with tab2:
        st.subheader("Generate a Quiz")
        text_content = str(course_data) + st.text_area("Enter additional topics:")
        quiz_level = st.selectbox("Select quiz level:", ["Easy", "Medium", "Hard"])

        if st.button("Generate Quiz"):
            if text_content.strip():
                # Generate questions using OpenAI
                questions = fetch_questions(text_content, quiz_level)
                if questions:
                    st.success("Quiz generated successfully!")
                    st.session_state["current_quiz"] = questions
                    st.session_state["selected_answers"] = {}
                    st.session_state["quiz_submitted"] = False
                else:
                    st.error("Failed to generate questions. Try again.")
            else:
                st.warning("Enter some text to generate a quiz.")

        # If questions are available, display them
        if "current_quiz" in st.session_state and st.session_state["current_quiz"]:
            for idx, question in enumerate(st.session_state["current_quiz"]):
                st.write(f"Q{idx + 1}: {question['mcq']}")
                options = question["options"]
                selected = st.radio(
                    "Choose your answer:",
                    list(options.values()),
                    key=f"question_{idx}",
                    index=1,
                )
                # Store selected answers in session state
                st.session_state["selected_answers"][idx] = selected

            if not st.session_state.get("quiz_submitted", False) and st.button(
                "Submit Answers"
            ):
                # Evaluate answers and calculate score
                st.session_state["quiz_submitted"] = True
                score = 0
                for idx, question in enumerate(st.session_state["current_quiz"]):
                    correct_option = question["options"][question["correct"]]
                    user_answer = st.session_state["selected_answers"].get(idx)
                    if user_answer == correct_option:
                        score += 1

                st.session_state["last_quiz_score"] = score

            # Display results after submission
            if st.session_state.get("quiz_submitted", False):
                st.subheader("Quiz Results")
                score = st.session_state["last_quiz_score"]
                total_questions = len(st.session_state["current_quiz"])
                st.write(f"Your score: {score}/{total_questions}")

                # Show correct answers and explanations
                for idx, question in enumerate(st.session_state["current_quiz"]):
                    if "mcq" in question and isinstance(question["mcq"], str):
                        st.write(f"Q{idx + 1}: {question['mcq']}")
                    else:
                        st.warning(
                            f"Question {idx + 1} is invalid or missing required keys. Skipping."
                        )

                    correct_option = question["options"][question["correct"]]
                    user_answer = st.session_state["selected_answers"].get(idx)
                    if user_answer == correct_option:
                        st.success(f"Your answer: {user_answer} (Correct)")
                    else:
                        st.error(f"Your answer: {user_answer} (Incorrect)")
                        st.write(f"Correct answer: {correct_option}")

                # Add quiz result to session history
                if "quizzes" not in st.session_state:
                    st.session_state["quizzes"] = []
                st.session_state["quizzes"].append(
                    {
                        "date": datetime.date.today(),
                        "score": score,
                        "total": total_questions,
                    }
                )

    # Roadmap Tab
    with tab3:
        st.subheader("Personalized Learning Roadmap")

        # Check if quiz results and course topics are available
        if (
            "last_quiz_score" in st.session_state
            and "course_topics" in st.session_state
        ):
            user_score = st.session_state["last_quiz_score"]
            total_questions = len(st.session_state["current_quiz"])

            # Determine performance level based on quiz score
            performance_level = (
                "Beginner"
                if user_score <= total_questions * 0.5
                else (
                    "Intermediate"
                    if user_score <= total_questions * 0.8
                    else "Advanced"
                )
            )

            st.write(f"Your Score: {user_score}/{total_questions}")
            st.write(f"Performance Level: {performance_level}")

            # User input for roadmap customization
            st.markdown("### Customize Your Roadmap")
            duration = st.slider("Learning duration (in weeks):", 1, 52, 4)

            # Generate roadmap
            if st.button("Generate Roadmap"):
                with st.spinner("Generating your roadmap..."):
                    try:
                        # Fetch topics from session state
                        all_topics = course_data # assigning data 

                        # Prepare a detailed roadmap prompt for OpenAI
                        roadmap_prompt = f"""
                       f"Create a detailed learning roadmap for the topic: {all_topics}. "
                       f"Skill level: {performance_level}. Duration: {duration} weeks."
                       """
                        # Request OpenAI API for roadmap generation
                        response = openai.ChatCompletion.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {
                                    "role": "system",
                                    "content": "You are an expert education planner.",
                                },
                                {"role": "user", "content": roadmap_prompt},
                            ],
                            max_tokens=1000,
                        )

                        # Extract the roadmap content from OpenAI response
                        roadmap = response.choices[0].message["content"]
                        st.session_state["roadmap"] = roadmap

                        st.success("Roadmap generated!")
                        st.markdown(roadmap)

                    except Exception as e:
                        st.error(f"Error generating roadmap: {e}")
        else:
            st.warning(
                "Complete a quiz in the Quizzes tab to unlock the roadmap feature."
            )

    with tab4:
        st.subheader("Generate Post-learning Quiz")

        if "roadmap" not in st.session_state or not st.session_state["roadmap"]:
            st.warning("Generate a roadmap first to create a post-learning quiz.")
        else:
            roadmap_content = st.session_state["roadmap"]
            quiz_level = st.selectbox(
                "Select quiz level:", ["Easy", "Medium", "Hard"], key="post_learning_quiz_level"
            )

            if st.button("Generate Post-learning Quiz"):
                post_questions = generate_post_learning_quiz(roadmap_content, quiz_level)
                if post_questions:
                    st.success("Post-learning Quiz generated successfully!")
                    st.session_state["post_quiz"] = post_questions
                    st.session_state["post_quiz_answers"] = {}
                    st.session_state["post_quiz_submitted"] = False
                else:
                    st.error("Failed to generate post-learning questions. Try again.")

        if "post_quiz" in st.session_state and st.session_state["post_quiz"]:
            for idx, question in enumerate(st.session_state["post_quiz"]):
                if question["type"] == "mcq":
                    st.write(f"Q{idx + 1}: {question['question']}")
                    options = question["options"]
                    selected = st.radio(
                        "Choose your answer:",
                        list(options.values()),
                        key=f"post_question_{idx}",
                    )
                    st.session_state["post_quiz_answers"][idx] = selected

                elif question["type"] == "true_false":
                    st.write(f"Q{idx + 1}: {question['question']}")
                    selected = st.radio(
                        "True or False:", ["True", "False"], key=f"post_question_{idx}"
                    )
                    st.session_state["post_quiz_answers"][idx] = selected == "True"

            if not st.session_state.get("post_quiz_submitted", False) and st.button(
                "Submit Post-learning Quiz"
            ):
                st.session_state["post_quiz_submitted"] = True
                score = 0
                for idx, question in enumerate(st.session_state["post_quiz"]):
                    correct_answer = question["correct"]
                    user_answer = st.session_state["post_quiz_answers"].get(idx)
                    if user_answer == correct_answer:
                        score += 1
                st.session_state["last_post_quiz_score"] = score

            if st.session_state.get("post_quiz_submitted", False):
                st.subheader("Post-learning Quiz Results")
                score = st.session_state["last_post_quiz_score"]
                total_questions = len(st.session_state["post_quiz"])
                st.write(f"Your score: {score}/{total_questions}")
                for idx, question in enumerate(st.session_state["post_quiz"]):
                    st.write(f"Q{idx + 1}: {question['question']}")
                    correct_answer = question["correct"]
                    user_answer = st.session_state["post_quiz_answers"].get(idx)
                    if user_answer == correct_answer:
                        st.success(f"Your answer: {user_answer} (Correct)")
                    else:
                        st.error(f"Your answer: {user_answer} (Incorrect)")
                        st.write(f"Correct answer: {correct_answer}")






if __name__ == "__main__":
    main()
