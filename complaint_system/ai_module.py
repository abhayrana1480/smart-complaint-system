"""
AI Module for Smart Complaint Management System
This file keeps all AI/ML logic in one place so the Flask routes stay clean.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline


# 40 hand-written training samples across 4 categories.
# This is a small educational dataset: enough for a college demo project.
TRAINING_SAMPLES: List[Tuple[str, str]] = [
    # Technical (10)
    ("App crashes when I click submit complaint", "Technical"),
    ("Website is very slow and pages take forever to load", "Technical"),
    ("I cannot log in even with correct password", "Technical"),
    ("The mobile view is broken on my browser", "Technical"),
    ("Error 500 appears when uploading attachment", "Technical"),
    ("Password reset link is not working", "Technical"),
    ("Server timeout when opening dashboard", "Technical"),
    ("Complaint status page shows blank screen", "Technical"),
    ("System logs me out automatically every minute", "Technical"),
    ("Unable to save profile due to unknown technical error", "Technical"),
    # Billing (10)
    ("I was charged twice for the same monthly subscription", "Billing"),
    ("Please refund the extra payment from last week", "Billing"),
    ("Invoice amount is incorrect and too high", "Billing"),
    ("Payment failed but money was deducted", "Billing"),
    ("Why is there an additional hidden fee in my bill", "Billing"),
    ("I need my tax invoice for this month", "Billing"),
    ("Auto debit happened after I cancelled service", "Billing"),
    ("My discount coupon was not applied to billing", "Billing"),
    ("The receipt email for payment was not sent", "Billing"),
    ("Outstanding balance is wrong in my account", "Billing"),
    # Service (10)
    ("Support team is not responding to my issue", "Service"),
    ("Very rude behavior from the customer care executive", "Service"),
    ("My request has been pending for many days", "Service"),
    ("The technician arrived late and did not fix anything", "Service"),
    ("I am unhappy with the service quality", "Service"),
    ("No one called back after raising complaint", "Service"),
    ("Resolution time is too long for simple requests", "Service"),
    ("The staff did not provide clear information", "Service"),
    ("Customer support closed ticket without solving", "Service"),
    ("Bad service experience with your field team", "Service"),
    # General (10)
    ("How can I update my contact details", "General"),
    ("I want to know office working hours", "General"),
    ("Please share process to track my complaint", "General"),
    ("Need help understanding account settings", "General"),
    ("Where can I download the user manual", "General"),
    ("How do I change my registered phone number", "General"),
    ("I have a question about available plans", "General"),
    ("Can you explain how the dashboard works", "General"),
    ("I need guidance to submit a new request", "General"),
    ("Just checking status and general information", "General"),
]


# Global model and analyzer are initialized once and reused.
_CLASSIFIER_MODEL: Pipeline | None = None
_SENTIMENT_ANALYZER: SentimentIntensityAnalyzer | None = None


# Urgency keywords used for simple priority boosting logic.
URGENCY_WORDS = {
    "urgent",
    "immediately",
    "asap",
    "critical",
    "emergency",
    "right now",
    "today",
}


RESPONSE_TEMPLATES: Dict[str, Dict[str, str]] = {
    "Technical": {
        "negative": "We are very sorry about the issue: \"{title}\". Our technical team has prioritized it and will update you soon.",
        "neutral": "Thank you for reporting \"{title}\". Our technical team is reviewing it and will share an update shortly.",
        "positive": "Thanks for the clear report: \"{title}\". Our technical team will review and resolve it quickly.",
    },
    "Billing": {
        "negative": "We understand your concern regarding \"{title}\". Our billing team is investigating this on priority.",
        "neutral": "We received your billing concern \"{title}\". Our billing team will verify and respond soon.",
        "positive": "Thank you for raising \"{title}\". Our billing team will check the details and assist you.",
    },
    "Service": {
        "negative": "We apologize for your service experience in \"{title}\". A manager will review and contact you shortly.",
        "neutral": "Thank you for sharing your service feedback: \"{title}\". We are reviewing it now.",
        "positive": "Thank you for your feedback on \"{title}\". We appreciate it and will follow up soon.",
    },
    "General": {
        "negative": "We are sorry for the inconvenience around \"{title}\". We will guide you with the right next steps.",
        "neutral": "Thanks for your query \"{title}\". We will provide the required information shortly.",
        "positive": "Thank you for your message \"{title}\". We are happy to help with your request.",
    },
}


FAQ_INTENTS: Dict[str, Dict[str, List[str] | str]] = {
    "track_complaint": {
        "keywords": ["track", "status", "progress", "complaint status"],
        "response": "You can track your complaint from the 'My Complaints' page after login.",
    },
    "create_complaint": {
        "keywords": ["new complaint", "submit", "register complaint", "file complaint"],
        "response": "Go to 'Submit Complaint' on your dashboard, fill the form, and click submit.",
    },
    "login_help": {
        "keywords": ["login", "password", "sign in", "cannot log in"],
        "response": "Please verify your email/password. For demo use: user@college.com / user123.",
    },
    "response_time": {
        "keywords": ["how long", "when", "response time", "resolve"],
        "response": "Managers review complaints based on priority. High-priority complaints are handled first.",
    },
    "contact_support": {
        "keywords": ["support", "help", "contact", "call"],
        "response": "You can submit a complaint and our manager team will respond from the manager dashboard.",
    },
}


# What this does (student-friendly):
# TF-IDF converts text into numbers based on important words.
# Naive Bayes uses those numbers to guess the most likely category.
def _build_classifier_model() -> Pipeline:
    """Create and train a TF-IDF + Multinomial Naive Bayes text classifier."""
    texts = [sample[0] for sample in TRAINING_SAMPLES]
    labels = [sample[1] for sample in TRAINING_SAMPLES]

    model = Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    stop_words="english",
                    ngram_range=(1, 2),
                ),
            ),
            ("naive_bayes", MultinomialNB(alpha=0.3)),
        ]
    )
    model.fit(texts, labels)
    return model


# What this does (student-friendly):
# We lazily initialize the model once so we do not retrain on every complaint.
def _get_classifier_model() -> Pipeline:
    """Return a trained classifier model, creating it once when first needed."""
    global _CLASSIFIER_MODEL
    if _CLASSIFIER_MODEL is None:
        _CLASSIFIER_MODEL = _build_classifier_model()
    return _CLASSIFIER_MODEL


# What this does (student-friendly):
# Sentiment analysis predicts emotional tone (positive/neutral/negative) from text.
# VADER is useful for short, real-world messages like complaints and chat text.
def _get_sentiment_analyzer() -> SentimentIntensityAnalyzer:
    """Return a VADER analyzer, downloading the lexicon once if required."""
    global _SENTIMENT_ANALYZER
    if _SENTIMENT_ANALYZER is None:
        try:
            nltk.data.find("sentiment/vader_lexicon.zip")
        except LookupError:
            nltk.download("vader_lexicon", quiet=True)
        _SENTIMENT_ANALYZER = SentimentIntensityAnalyzer()
    return _SENTIMENT_ANALYZER


# What this does (student-friendly):
# This function predicts complaint category and confidence score (0.0 to 1.0).
def classify_complaint(text: str) -> Tuple[str, float]:
    """Classify complaint text into a category with confidence."""
    clean_text = (text or "").strip()
    if not clean_text:
        return "General", 0.0

    model = _get_classifier_model()
    predicted_label = model.predict([clean_text])[0]
    probabilities = model.predict_proba([clean_text])[0]
    confidence = float(max(probabilities))
    return predicted_label, confidence


# What this does (student-friendly):
# It calculates sentiment score with VADER and maps it to a label.
# Then it sets priority: negative + urgency words => high, otherwise medium/low.
def analyze_sentiment_and_priority(title: str, description: str) -> Tuple[str, float, str]:
    """Analyze sentiment and derive complaint priority."""
    full_text = f"{title or ''} {description or ''}".strip().lower()
    if not full_text:
        return "neutral", 0.0, "low"

    analyzer = _get_sentiment_analyzer()
    compound_score = analyzer.polarity_scores(full_text)["compound"]

    if compound_score > 0.05:
        sentiment = "positive"
    elif compound_score < -0.05:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    has_urgency_word = any(keyword in full_text for keyword in URGENCY_WORDS)
    if sentiment == "negative" and has_urgency_word:
        priority = "high"
    elif sentiment == "negative":
        priority = "medium"
    elif sentiment == "neutral" and has_urgency_word:
        priority = "medium"
    else:
        priority = "low"

    return sentiment, float(compound_score), priority


# What this does (student-friendly):
# This is a rule-based NLP method: category + sentiment picks a response template.
# It is a simple stepping stone before using advanced LLM-based systems.
def generate_ai_response(title: str, category: str, sentiment: str) -> str:
    """Generate a suggested response using template + keyword logic."""
    safe_title = (title or "your complaint").strip()
    safe_category = category if category in RESPONSE_TEMPLATES else "General"
    safe_sentiment = sentiment if sentiment in ("negative", "neutral", "positive") else "neutral"

    template = RESPONSE_TEMPLATES[safe_category][safe_sentiment]
    return template.format(title=safe_title)


# What this does (student-friendly):
# Intent detection means guessing what the user wants from keywords.
# A simple chatbot can map detected intent to a prepared response.
def get_chatbot_response(message: str) -> str:
    """Return a FAQ chatbot response using keyword intent matching."""
    text = (message or "").strip().lower()
    if not text:
        return "Please type your question. I am here to help."

    for intent_data in FAQ_INTENTS.values():
        keywords = intent_data["keywords"]
        if any(keyword in text for keyword in keywords):
            return str(intent_data["response"])

    return (
        "I can help with complaint status, complaint submission, login help, and response time. "
        "Please ask in simple words."
    )


# What this does (student-friendly):
# This helper runs all AI steps together for a complaint form submission.
def process_complaint_with_ai(title: str, description: str) -> Dict[str, object]:
    """Run category, sentiment, priority, and suggestion in one call."""
    category, confidence = classify_complaint(f"{title} {description}")
    sentiment, sentiment_score, priority = analyze_sentiment_and_priority(title, description)
    ai_response = generate_ai_response(title, category, sentiment)

    return {
        "category": category,
        "confidence": confidence,
        "sentiment": sentiment,
        "sentiment_score": sentiment_score,
        "priority": priority,
        "ai_response": ai_response,
    }

