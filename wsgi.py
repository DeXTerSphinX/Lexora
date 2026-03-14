import spacy
from api.app import app

# Pre-load the spaCy model at startup
try:
    spacy.load("en_core_web_md")
except OSError:
    import subprocess
    subprocess.check_call(["python", "-m", "spacy", "download", "en_core_web_md"])
    spacy.load("en_core_web_md")

if __name__ == "__main__":
    app.run()
