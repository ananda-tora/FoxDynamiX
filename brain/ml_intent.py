from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression

# ===== DATA LATIHAN =====
training_sentences = [
    # currency
    "mata uang thailand",
    "mata uang jepang",
    "mata uang brazil",
    "mata uang nigeria",
    "mata uang korea",
    "mata uang malaysia",
    "mata uang india",
    "currency indonesia",
    "uang singapura",
    "mata uang vietnam",
    # capital
    "ibu kota indonesia",
    "ibu kota thailand",
    "ibukota jepang",
    "capital malaysia",
    "ibu kota brazil",
    "ibukota nigeria",
    "capital korea",
    "ibu kota vietnam",
    "ibu kota india",
    "capital china",
]

training_labels = [
    "currency",
    "currency",
    "currency",
    "currency",
    "currency",
    "currency",
    "currency",
    "currency",
    "currency",
    "currency",
    "capital",
    "capital",
    "capital",
    "capital",
    "capital",
    "capital",
    "capital",
    "capital",
    "capital",
    "capital",
]

# ===== MODEL =====
vectorizer = CountVectorizer()
X = vectorizer.fit_transform(training_sentences)

model = LogisticRegression()
model.fit(X, training_labels)


def predict_intent(text: str) -> str:
    X_input = vectorizer.transform([text])
    prediction = model.predict(X_input)
    return prediction[0]
